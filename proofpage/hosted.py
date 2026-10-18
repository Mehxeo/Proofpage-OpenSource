"""Single-node hosted edition. One process owns a private persistent data volume."""
import asyncio
import json
import os
import sqlite3
import threading
import time
import urllib.parse
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from .accounts import Accounts, PLANS, hashed
from .assets import read_asset
from .core import Store, MAX_BYTES
from . import service, crawl, mcp
from .billing import Billing

STATIC = Path(__file__).parent / 'static'
READ_TOOLS = {'proofpage_list_sources','proofpage_get_source_access','proofpage_get_run','proofpage_search',
              'proofpage_get_item','proofpage_get_evidence','proofpage_list_changes','proofpage_get_context',
              'proofpage_get_crawl','proofpage_list_recipes'}


class HostedStore(Store):
    def __init__(self, accounts, user_id):
        self.accounts, self.user_id = accounts, user_id
        # IDs come only from authenticated database rows, never a URL or submitted path.
        self.max_bytes = PLANS[accounts.plan(user_id)]['storage']
        super().__init__(accounts.root / 'workspaces' / user_id)

    @contextmanager
    def db(self):
        with super().db() as db:
            page_size = db.execute('PRAGMA page_size').fetchone()[0]
            db.execute('PRAGMA max_page_count='+str(max(128,self.max_bytes//page_size)))
            yield db

    def collect(self, source_id, target_url=None, render=False):
        if render:
            raise ValueError('Browser rendering is available in local mode only.')
        sources = self.rows("SELECT location FROM sources WHERE id=? AND kind='web'",(source_id,))
        if not sources:
            raise ValueError('Source not found.')
        host = urllib.parse.urlsplit(sources[0]['location']).hostname.lower().rstrip('.')
        local = self.rows('SELECT until FROM cooldowns WHERE origin=?',(host,))
        if local and local[0]['until'] > time.time():
            raise ValueError('This host is cooling down.')
        # Charge attempts, not extracted records. Failed starts may consume an attempt.
        self.accounts.reserve_host(host,self.user_id)
        try:
            return super().collect(source_id,target_url=target_url,render=False)
        finally:
            local = self.rows('SELECT until FROM cooldowns WHERE origin=?',(host,))
            if local:
                with self.accounts.db() as db:
                    db.execute('UPDATE host_limits SET next_attempt=MAX(next_attempt,?) WHERE host=?',(local[0]['until'],host))


def create_app(root=None, origin=None, development=False, scheduler=True, billing_client=None):
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, Response, RedirectResponse
    from starlette.concurrency import run_in_threadpool
    root = root or os.environ.get('PROOFPAGE_HOSTED_HOME','~/.proofpage-hosted')
    origin = (origin or os.environ.get('PROOFPAGE_PUBLIC_URL','')).rstrip('/')
    parsed = urllib.parse.urlsplit(origin)
    development = development or os.environ.get('PROOFPAGE_DEVELOPMENT') == 'true'
    if (parsed.scheme != 'https' and not (development and parsed.scheme=='http' and parsed.hostname in ('localhost','127.0.0.1'))) or parsed.path or parsed.query or parsed.fragment or parsed.username or not parsed.hostname:
        raise ValueError('Set PROOFPAGE_PUBLIC_URL to the HTTPS origin. Loopback HTTP requires explicit development mode.')
    accounts, locks = Accounts(root), {}
    exports_root=accounts.root/'exports'
    exports_root.mkdir(exist_ok=True,mode=0o700)
    last_billing_check = [0.0]
    billing = Billing(accounts,origin,billing_client)
    locks_guard = threading.Lock()
    def lock_for(uid):
        with locks_guard:
            return locks.setdefault(uid,threading.RLock())

    def scheduled_tick():
        if billing.configured and time.time()-last_billing_check[0]>3600:
            last_billing_check[0]=time.time()
            with accounts.db() as db:
                customers=[r['id'] for r in db.execute('SELECT id FROM users WHERE customer IS NOT NULL')]
            for uid in customers:
                try: billing.reconcile(uid)
                except Exception: accounts.audit(uid,'billing.retry_required')
        with accounts.db() as db:
            users = [r['id'] for r in db.execute('SELECT id FROM users ORDER BY created')]
        for uid in users:
            lock = lock_for(uid)
            if not lock.acquire(blocking=False):
                continue
            try:
                store = HostedStore(accounts,uid)
                jobs = store.rows("SELECT id FROM crawl_jobs WHERE state IN ('queued','running') AND next_attempt<=? LIMIT 1",(time.time(),))
                if jobs:
                    crawl.step_job(store,jobs[0]['id'])
                else:
                    sources = store.rows("SELECT id FROM sources WHERE kind='web' AND interval_seconds>0 AND next_run<=? LIMIT 1",(time.time(),))
                    if sources:
                        try:
                            store.collect(sources[0]['id'])
                        except ValueError:
                            with store.db() as db:
                                db.execute('UPDATE sources SET next_run=? WHERE id=?',(time.time()+300,sources[0]['id']))
            except Exception:
                # Only operational metadata; no source contents or credentials in logs.
                accounts.audit(uid,'scheduler.retry_required')
            finally:
                lock.release()

    @asynccontextmanager
    async def lifespan(app):
        import fcntl
        handle = (accounts.root/'hosted.lock').open('a')
        try:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            raise RuntimeError('This hosted volume already has a server. Use one worker per volume.')
        async def loop():
            while True:
                await asyncio.sleep(5)
                await run_in_threadpool(scheduled_tick)
        task = asyncio.create_task(loop()) if scheduler else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
            fcntl.flock(handle,fcntl.LOCK_UN)
            handle.close()

    app = FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)
    app.state.accounts, app.state.billing = accounts, billing
    app.state.tick = scheduled_tick
    cookie = 'proofpage_session' if development else '__Host-proofpage_session'

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        return JSONResponse({'error':str(exc)},status_code=400)

    @app.exception_handler(PermissionError)
    async def unauthorized(request, exc):
        return JSONResponse({'error':str(exc)},status_code=401)

    @app.exception_handler(KeyError)
    @app.exception_handler(TypeError)
    async def invalid_fields(request, exc):
        return JSONResponse({'error':'Missing or invalid request fields.'},status_code=400)

    import stripe
    @app.exception_handler(stripe.StripeError)
    async def provider_error(request, exc):
        return JSONResponse({'error':'Billing provider is temporarily unavailable or misconfigured. No local entitlement was granted.'},status_code=502)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        return JSONResponse({'error':'Workspace storage is full or temporarily busy. Export existing data or contact the operator.'},status_code=503)

    @app.middleware('http')
    async def boundary(request: Request, call_next):
        if request.headers.get('host') != parsed.netloc:
            return JSONResponse({'error':'Invalid host.'},status_code=403)
        if request.headers.get('origin') not in (None,origin) or request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'error':'Cross-origin access denied.'},status_code=403)
        # Bound even chunked bodies before parsing, including webhook payloads.
        if request.method in ('POST','PUT','PATCH'):
            body = bytearray()
            async for part in request.stream():
                body.extend(part)
                if len(body)>MAX_BYTES*2:
                    return JSONResponse({'error':'Request exceeds 16 MiB.'},status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin',
                                 'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})
        if not development:
            response.headers['Strict-Transport-Security']='max-age=31536000'
        return response

    def identity(request, mutation=False):
        session = accounts.authenticate(request.cookies.get(cookie,''))
        if mutation:
            import hmac
            submitted = request.headers.get('authorization','').removeprefix('Bearer ')
            if request.headers.get('origin') != origin or not hmac.compare_digest(submitted,session['csrf']):
                raise PermissionError('A same-origin session token is required.')
        return session['user_id'], session['csrf']

    async def data(request):
        try: result = await request.json()
        except Exception: raise ValueError('Expected a JSON object.') from None
        if not isinstance(result,dict): raise ValueError('Expected a JSON object.')
        return result

    def auth_attempt(request, email):
        if request.headers.get('origin') != origin:
            raise PermissionError('Use the sign-in page on this server.')
        ip = request.client.host if request.client else 'unknown'
        accounts.rate_limit('auth-ip:'+hashed(ip),30)
        accounts.rate_limit('auth-email:'+hashed(str(email).lower()),10)

    def result(value):
        status, body, mime = value
        return JSONResponse(body,status_code=status) if mime=='application/json' else Response(body,status_code=status,media_type=mime)

    @app.get('/healthz')
    def health():
        with accounts.db() as db: db.execute('SELECT 1')
        return {'status':'ok'}

    @app.get('/login')
    def login_page():
        return Response((STATIC/'login.html').read_text(encoding='utf-8'),media_type='text/html')

    @app.post('/auth/{operation}')
    async def authentication(operation: str, request: Request):
        payload = await data(request)
        if operation=='logout':
            uid,_ = identity(request,True)
            with accounts.db() as db: db.execute('DELETE FROM sessions WHERE hash=?',(hashed(request.cookies.get(cookie,'')),))
            response=JSONResponse({'signed_out':True});response.delete_cookie(cookie,path='/');return response
        auth_attempt(request,payload.get('email'))
        if operation=='register':
            uid,recovery = await run_in_threadpool(accounts.register,payload.get('email'),payload.get('password'),payload.get('invite',''))
            session,csrf = accounts.session(uid)
        elif operation=='login':
            session,csrf = await run_in_threadpool(accounts.login,payload.get('email'),payload.get('password'))
            recovery=None
        elif operation=='recover':
            recovery = await run_in_threadpool(accounts.recover,payload.get('email'),payload.get('recovery',''),payload.get('password'))
            return {'recovery_code':recovery,'detail':'Password changed. Old sessions and agent keys revoked. Save the new recovery code, then sign in.'}
        else:
            return JSONResponse({'error':'Not found.'},status_code=404)
        response = JSONResponse({'token':csrf,'recovery_code':recovery})
        response.set_cookie(cookie,session,max_age=7*86400,httponly=True,secure=not development,samesite='strict',path='/')
        return response

    @app.get('/api/session')
    def session(request: Request):
        uid,csrf = identity(request)
        return {'token':csrf,'mode':'hosted','account':accounts.account(uid)}

    @app.get('/api/account/audit')
    def audit_log(request: Request):
        uid,_=identity(request)
        with accounts.db() as db:
            return [dict(r) for r in db.execute('SELECT action,created FROM audit WHERE user_id=? ORDER BY id DESC LIMIT 100',(uid,))]

    @app.get('/api/account')
    def account(request: Request):
        uid,_=identity(request)
        return accounts.account(uid)

    @app.get('/api/account/export')
    async def export_account(request: Request):
        import tempfile
        from fastapi.responses import FileResponse
        from starlette.background import BackgroundTask
        from .backup import backup
        uid,_=identity(request)
        accounts.rate_limit('export:'+uid,5)
        def prepare():
            with lock_for(uid):
                directory=Path(tempfile.mkdtemp(prefix='proofpage-export-',dir=exports_root))
                target=directory/'workspace.sqlite3'
                try: backup(HostedStore(accounts,uid),target)
                except Exception:
                    directory.rmdir()
                    raise
                return directory,target
        directory,target=await run_in_threadpool(prepare)
        def cleanup():
            target.unlink(missing_ok=True);directory.rmdir()
        return FileResponse(target,filename='proofpage-workspace.sqlite3',media_type='application/octet-stream',background=BackgroundTask(cleanup))

    @app.post('/api/keys')
    async def new_key(request: Request):
        uid,_=identity(request,True);payload=await data(request)
        return accounts.create_key(uid,payload.get('name'),payload.get('scope'))

    @app.post('/api/keys/revoke')
    async def revoke_key(request: Request):
        uid,_=identity(request,True);payload=await data(request)
        with accounts.db() as db: db.execute('DELETE FROM keys WHERE id=? AND user_id=?',(payload.get('id'),uid))
        accounts.audit(uid,'key.revoked')
        return {'revoked':True}

    @app.get('/api/billing')
    async def billing_info(request: Request):
        identity(request)
        return await run_in_threadpool(billing.price)

    @app.post('/api/billing/{operation}')
    async def billing_action(operation: str, request: Request):
        uid,_=identity(request,True)
        accounts.rate_limit('billing:'+uid,20)
        methods={'checkout':billing.checkout,'portal':billing.portal,'refresh':billing.reconcile}
        if operation not in methods: return JSONResponse({'error':'Not found.'},status_code=404)
        return await run_in_threadpool(methods[operation],uid)

    @app.post('/webhooks/stripe')
    async def webhook(request: Request):
        return await run_in_threadpool(billing.webhook,await request.body(),request.headers.get('stripe-signature',''))

    @app.post('/agent')
    async def remote_agent(request: Request):
        principal=accounts.authenticate_key(request.headers.get('authorization','').removeprefix('Bearer '))
        uid=principal['user_id'];accounts.rate_limit('agent:'+uid,300)
        payload=await data(request)
        def dispatch():
            mid=payload.get('id');method=payload.get('method')
            if method=='initialize':
                response={'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'proofpage-hosted','version':'0.1.0'}}
            elif method=='tools/list':
                response={'tools':[{'name':name,'description':desc,'inputSchema':{'type':'object','properties':{k:{'type':v} for k,v in fields.items()},'required':list(fields),'additionalProperties':False}} for name,(desc,fields) in mcp.TOOLS.items() if principal['scope']=='collect' or name in READ_TOOLS]}
            elif method=='tools/call':
                params=payload.get('params',{});name=params.get('name')
                if principal['scope']=='read' and name not in READ_TOOLS:
                    raise PermissionError('This key only permits read tools.')
                with lock_for(uid):
                    if name not in READ_TOOLS: accounts.consume(uid,'writes')
                    store=HostedStore(accounts,uid)
                    value=mcp.call(store,name,params.get('arguments',{}))
                response={'content':[{'type':'text','text':json.dumps(value)}],'isError':False}
            elif method=='ping': response={}
            elif method=='notifications/initialized': return None
            else: return {'jsonrpc':'2.0','id':mid,'error':{'code':-32601,'message':'Method not found'}}
            return {'jsonrpc':'2.0','id':mid,'result':response}
        value=await run_in_threadpool(dispatch)
        return Response(status_code=204) if value is None else JSONResponse(value)

    @app.api_route('/api/{path:path}',methods=['GET','POST'])
    async def workspace(path: str, request: Request):
        uid,_=identity(request,request.method=='POST')
        accounts.rate_limit('workspace:'+uid,600)
        payload=await data(request) if request.method=='POST' else None
        # No browser request may read server-side folders or select another account's data path.
        if path.startswith(('watch','watches')):
            raise ValueError('Folder watches run on your own computer in local mode. Upload an archive here.')
        def dispatch():
            with lock_for(uid):
                store=HostedStore(accounts,uid)
                if request.method=='GET':
                    value=service.get(store,'/api/'+path,urllib.parse.parse_qs(request.url.query))
                    if path=='workbench' and value[0]==200:
                        value[1]['model']={'configured':bool(os.environ.get('PROOFPAGE_MODEL_URL') and os.environ.get('PROOFPAGE_MODEL_NAME')),'model':os.environ.get('PROOFPAGE_MODEL_NAME',''),'url':'the hosted operator’s model endpoint','detail':'Explicit sends use the operator’s configured model. Review private data before sending.'}
                    return value
                accounts.consume(uid,'writes')
                if payload.get('render'): raise ValueError('Browser rendering is local-only.')
                if path=='model-assist': accounts.consume(uid,'models')
                value=service.post(store,'/api/'+path,payload)
                if value[0]==200: accounts.audit(uid,'workspace.'+path.split('/')[0])
                return value
        return result(await run_in_threadpool(dispatch))

    @app.get('/{path:path}')
    def static(path: str, request: Request):
        asset=read_asset(path)
        if asset:
            return Response(asset[0],media_type=asset[1])
        if path=='':
            try:identity(request)
            except PermissionError:return RedirectResponse('/login',status_code=303)
            html=(STATIC/'index.html').read_text(encoding='utf-8').replace('</head>','<script src="/hosted.js" defer></script></head>').replace('>Local storage<','>Hosted workspace<').replace('>Local workspace<','>Hosted workspace<').replace('Stored on this computer.','Stored in your hosted account.')
            return Response(html,media_type='text/html')
        return JSONResponse({'error':'Not found.'},status_code=404)
    return app
