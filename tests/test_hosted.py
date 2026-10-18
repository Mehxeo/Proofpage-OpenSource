import base64
import hashlib
import hmac
import importlib.util
import json
import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

AVAILABLE = all(importlib.util.find_spec(name) for name in ('fastapi','httpx','stripe'))


@unittest.skipUnless(AVAILABLE,'Install .[hosted,test] for hosted integration tests.')
class HostedTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from proofpage.hosted import create_app
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'PROOFPAGE_STRIPE_KEY':'','PROOFPAGE_STRIPE_PRICE_ID':'','PROOFPAGE_STRIPE_WEBHOOK_SECRET':''})
        self.env.start()
        self.app=create_app(self.temp.name,'https://testserver',scheduler=False)
        self.accounts=self.app.state.accounts
        self.client=TestClient(self.app,base_url='https://testserver')
        self.client.__enter__()
        self.a=self.register('alice@example.test')

    def tearDown(self):
        self.client.__exit__(None,None,None)
        self.env.stop();self.temp.cleanup()

    def register(self,email):
        self.client.cookies.clear()
        invitation=self.accounts.invite(email)
        r=self.client.post('/auth/register',json={'email':email,'password':'long fixture password','invite':invitation},headers={'Origin':'https://testserver'})
        self.assertEqual(r.status_code,200,r.text)
        return {'csrf':r.json()['token'],'recovery':r.json()['recovery_code'],'cookie':self.client.cookies.get('__Host-proofpage_session'),'email':email}

    def use(self,account):
        self.client.cookies.clear();self.client.cookies.set('__Host-proofpage_session',account['cookie'])
        self.client.headers.update({'Authorization':'Bearer '+account['csrf'],'Origin':'https://testserver'})

    def post(self,path,data=None):
        return self.client.post(path,json=data or {})

    def evidence(self,account):
        self.use(account)
        profile=self.post('/api/profiles',{'name':'Fixture','provider':'fixture','account':account['email'],'adapter':'generic'}).json()
        r=self.post('/api/import',{'filename':'fixture.txt','data':base64.b64encode(b'Hosted fixture contains sunlight evidence.').decode(),'selected':['fixture.txt'],'profile_id':profile['id']})
        self.assertEqual(r.status_code,200,r.text)
        return self.client.get('/api/state').json()['items'][0]

    def test_auth_cookies_csrf_and_host(self):
        self.use(self.a)
        r=self.client.get('/api/session')
        self.assertEqual(r.json()['mode'],'hosted')
        self.assertEqual(self.client.get('/api/state',headers={'Host':'evil.test'}).status_code,403)
        self.assertEqual(self.post('/api/profiles',{}).status_code,400)
        self.client.headers.pop('Authorization')
        self.assertEqual(self.post('/api/profiles',{}).status_code,401)
        self.assertEqual(self.client.get('/api/state',headers={'Origin':'https://evil.test'}).status_code,403)
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/session').status_code,401)
        r=self.client.get('/',follow_redirects=False)
        self.assertEqual(r.headers['location'],'/login')

    def test_workspace_page_and_assets(self):
        self.use(self.a)
        page=self.client.get('/')
        self.assertEqual(page.status_code,200)
        self.assertIn('>Hosted workspace<',page.text)
        self.assertNotIn('>Local storage<',page.text)
        self.assertIn('/hosted.js',page.text)
        for path,kind in (('/hosted.js','text/javascript'),('/icons.svg','image/svg+xml'),('/style.css','text/css'),('/fonts/newsreader-latin-opsz-normal.woff2','font/woff2')):
            r=self.client.get(path)
            self.assertEqual(r.status_code,200,path)
            self.assertTrue(r.headers['content-type'].startswith(kind),path)
        self.assertEqual(self.client.get('/hosted.py').status_code,404)

    def test_invites_single_use_and_password_recovery_revokes_credentials(self):
        self.use(self.a)
        key=self.post('/api/keys',{'name':'Fixture','scope':'read'}).json()['key']
        r=self.client.post('/auth/recover',json={'email':self.a['email'],'password':'changed fixture password','recovery':self.a['recovery']},headers={'Origin':'https://testserver'})
        self.assertEqual(r.status_code,200,r.text)
        self.assertNotEqual(r.json()['recovery_code'],self.a['recovery'])
        self.assertEqual(self.client.get('/api/session').status_code,401)
        with self.assertRaises(PermissionError):self.accounts.authenticate_key(key)
        r=self.client.post('/auth/recover',json={'email':self.a['email'],'password':'changed fixture password','recovery':self.a['recovery']},headers={'Origin':'https://testserver'})
        self.assertEqual(r.status_code,400)
        invitation=self.accounts.invite('one@example.test')
        self.accounts.register('one@example.test','long fixture password',invitation)
        with self.assertRaises(ValueError):self.accounts.register('one@example.test','long fixture password',invitation)

    def test_tenant_isolation_for_evidence_reviews_and_agent_calls(self):
        item=self.evidence(self.a)
        self.client.headers.clear()
        b=self.register('bob@example.test');self.use(b)
        self.assertEqual(self.client.get('/api/state').json()['items'],[])
        self.assertEqual(self.client.get('/api/items/'+item['id']).status_code,400)
        self.assertEqual(self.post('/api/review',{'revision_id':item['current_revision'],'allowed':True,'approved':True}).status_code,400)
        key=self.post('/api/keys',{'name':'Bob','scope':'collect'}).json()['key']
        r=self.client.post('/agent',json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'proofpage_get_item','arguments':{'item_id':item['id']}}},headers={'Authorization':'Bearer '+key})
        self.assertEqual(r.status_code,400)
        self.use(self.a);self.assertEqual(len(self.client.get('/api/state').json()['items']),1)

    def test_no_server_filesystem_or_browser_render_access(self):
        self.use(self.a)
        for route in ('watches','watch-scan','watch-toggle'):
            self.assertEqual(self.post('/api/'+route,{'directory':'/etc','enabled':True}).status_code,400)
        self.assertEqual(self.post('/api/collect',{'source_id':'anything','render':True}).status_code,400)

    def test_agent_scopes_revocation_and_no_approval_tools(self):
        self.evidence(self.a)
        value=self.post('/api/keys',{'name':'Search agent','scope':'read'}).json();key=value['key']
        def rpc(method,params={}):return self.client.post('/agent',json={'jsonrpc':'2.0','id':1,'method':method,'params':params},headers={'Authorization':'Bearer '+key})
        tools=rpc('tools/list').json()['result']['tools']
        names={t['name'] for t in tools}
        self.assertIn('proofpage_get_context',names);self.assertNotIn('proofpage_collect',names)
        self.assertFalse(any('approve' in n or 'export' in n for n in names))
        self.assertEqual(rpc('tools/call',{'name':'proofpage_collect','arguments':{'source_id':'anything'}}).status_code,401)
        response=rpc('tools/call',{'name':'proofpage_get_context','arguments':{'query':'sunlight'}})
        self.assertEqual(response.status_code,200,response.text)
        self.post('/api/keys/revoke',{'id':value['id']})
        self.assertEqual(rpc('tools/list').status_code,401)

    def test_data_portability_excludes_account_secrets(self):
        self.evidence(self.a)
        response=self.client.get('/api/account/export')
        self.assertEqual(response.status_code,200,response.text[:100] if response.status_code!=200 else '')
        from proofpage.backup import restore
        from proofpage.core import Store
        path=Path(self.temp.name)/'download.sqlite3';path.write_bytes(response.content)
        target=Path(self.temp.name)/'restored'
        restore(path,target)
        store=Store(target)
        self.assertEqual(len(store.search('sunlight')),1)
        tables={r['name'] for r in store.rows("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn('users',tables);self.assertNotIn('sessions',tables)

    def test_quota_is_atomic_and_shared_destination_limits(self):
        from proofpage.accounts import PLANS
        uid=self.accounts.authenticate(self.a['cookie'])['user_id']
        with patch.dict(PLANS['free'],{'pages':1}):
            def take():
                try:self.accounts.consume(uid,'pages');return True
                except ValueError:return False
            with ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(sum(pool.map(lambda _:take(),range(4))),1)
        self.accounts.reserve_host('example.test')
        with self.assertRaises(ValueError):self.accounts.reserve_host('example.test')
        self.assertEqual(self.accounts.plan(uid),'free')
        with self.assertRaises(ValueError):self.accounts.consume(uid,'models')

    def test_storage_cap_and_background_crawl_quota(self):
        import sqlite3
        from proofpage.hosted import HostedStore
        from proofpage.accounts import PLANS
        from proofpage import crawl
        uid=self.accounts.authenticate(self.a['cookie'])['user_id']
        with patch.dict(PLANS['free'],{'storage':1024*1024}):
            store=HostedStore(self.accounts,uid)
            source=store.source('Fixture','import','fixture:storage')
            with self.assertRaises(sqlite3.OperationalError):
                store.save(source['id'],'big','document','Large','x'*(2*1024*1024),'raw')
            self.assertEqual(store.search(),[])
        with patch('proofpage.core.validate_url'):
            source=store.source('Web','web','https://example.org/')
        job=crawl.create_job(store,source['id'])
        with patch.dict(PLANS['free'],{'pages':0}),patch('proofpage.core.fetch') as fetch:
            self.app.state.tick()
            fetch.assert_not_called()
        self.assertEqual(crawl.get_job(store,job['id'])['state'],'queued')
        with self.accounts.db() as db:
            self.assertIsNone(db.execute('SELECT * FROM host_limits WHERE host=?',('example.org',)).fetchone())

    def test_billing_off_and_malformed_requests(self):
        self.use(self.a)
        self.assertFalse(self.client.get('/api/billing').json()['configured'])
        self.assertEqual(self.post('/api/billing/checkout').status_code,400)
        self.assertEqual(self.client.post('/api/profiles',content='not json',headers={'Content-Type':'application/json'}).status_code,400)
        self.assertEqual(self.post('/api/profiles',[]).status_code,400)
        self.assertEqual(self.client.post('/api/import',content=b'x'*(16*1024*1024+1)).status_code,413)


@unittest.skipUnless(AVAILABLE,'Install .[hosted,test] for billing tests.')
class BillingTests(unittest.TestCase):
    def setUp(self):
        from proofpage.accounts import Accounts
        from proofpage.billing import Billing
        self.temp=tempfile.TemporaryDirectory();self.accounts=Accounts(self.temp.name)
        self.uid,_=self.accounts.register('billing@example.test','long fixture password',self.accounts.invite('billing@example.test'))
        self.env=patch.dict(os.environ,{'PROOFPAGE_STRIPE_KEY':'','PROOFPAGE_STRIPE_PRICE_ID':'price_fixture','PROOFPAGE_STRIPE_WEBHOOK_SECRET':'whsec_fixture','PROOFPAGE_STRIPE_LIVE':'false'});self.env.start()
        self.client=Mock()
        self.client.v1.prices.retrieve.return_value={'active':True,'type':'recurring','livemode':False,'unit_amount':1900,'currency':'usd','recurring':{'interval':'month','interval_count':1}}
        self.client.v1.customers.create.return_value={'id':'cus_fixture'}
        self.client.v1.subscriptions.list.return_value={'data':[],'has_more':False}
        self.client.v1.checkout.sessions.create.return_value={'id':'cs_fixture','url':'https://checkout.stripe.com/fixture'}
        self.client.v1.checkout.sessions.retrieve.return_value={'status':'open','url':'https://checkout.stripe.com/fixture'}
        self.billing=Billing(self.accounts,'https://testserver',self.client)

    def tearDown(self):self.env.stop();self.temp.cleanup()

    def subscription(self,status='active'):
        return {'id':'sub_fixture','customer':'cus_fixture','status':status,'created':1,'livemode':False,'items':{'data':[{'quantity':1,'price':{'id':'price_fixture'},'current_period_end':int(time.time())+3600}]}}

    def webhook(self,event_id,status='active'):
        self.client.v1.subscriptions.list.return_value={'data':[self.subscription(status)],'has_more':False}
        body=json.dumps({'id':event_id,'object':'event','type':'customer.subscription.updated','livemode':False,'data':{'object':{'customer':'cus_fixture','status':'active'}}}).encode()
        stamp=str(int(time.time()));signature=hmac.new(b'whsec_fixture',stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        return self.billing.webhook(body,'t='+stamp+',v1='+signature)

    def test_checkout_reuse_and_no_redirect_entitlement(self):
        self.billing.checkout(self.uid);self.billing.checkout(self.uid)
        self.assertEqual(self.client.v1.checkout.sessions.create.call_count,1)
        self.assertEqual(self.accounts.plan(self.uid),'free')
        params=self.client.v1.checkout.sessions.create.call_args.args[0]
        self.assertNotIn('payment_method_types',params)
        self.assertEqual(params['line_items'],[{'price':'price_fixture','quantity':1}])
        self.assertFalse('unit_amount' in str(params))

    def test_verified_webhook_reconciles_latest_state_and_duplicates(self):
        self.billing.checkout(self.uid)
        self.assertTrue(self.webhook('evt_first')['received'])
        self.assertEqual(self.accounts.plan(self.uid),'pro')
        self.assertTrue(self.webhook('evt_first')['duplicate'])
        self.webhook('evt_old_delivery','canceled')
        self.assertEqual(self.accounts.plan(self.uid),'free')
        with self.assertRaises(ValueError):self.billing.webhook(b'{}','bad')

    def test_nonmatching_price_and_failed_payments_do_not_grant_access(self):
        self.billing.checkout(self.uid)
        self.webhook('evt_past_due','past_due')
        self.assertEqual(self.accounts.plan(self.uid),'free')
        sub=self.subscription();sub['items']['data'][0]['price']['id']='price_other'
        self.client.v1.subscriptions.list.return_value={'data':[sub]}
        self.billing.reconcile(self.uid)
        self.assertEqual(self.accounts.plan(self.uid),'free')

    def test_real_sdk_objects_and_failed_checkout_retry(self):
        import stripe
        self.client.v1.prices.retrieve.return_value=stripe.Price.construct_from(self.client.v1.prices.retrieve.return_value,None)
        self.client.v1.subscriptions.list.return_value=stripe.ListObject.construct_from({'object':'list','data':[],'has_more':False},None)
        self.client.v1.checkout.sessions.create.side_effect=[RuntimeError('network'),{'id':'cs_retry','url':'https://checkout.stripe.com/retry'}]
        with self.assertRaises(RuntimeError):self.billing.checkout(self.uid)
        self.billing.checkout(self.uid)
        calls=self.client.v1.checkout.sessions.create.call_args_list
        self.assertEqual(calls[0].kwargs['options']['idempotency_key'],calls[1].kwargs['options']['idempotency_key'])
        self.assertEqual(calls[0].args[0],calls[1].args[0])
        self.assertEqual(self.client.v1.customers.create.call_count,1)

    def test_provider_failure_does_not_acknowledge_event(self):
        self.billing.checkout(self.uid)
        body=json.dumps({'id':'evt_retry','object':'event','type':'invoice.paid','livemode':False,'data':{'object':{'customer':'cus_fixture'}}}).encode()
        stamp=str(int(time.time()));sig=hmac.new(b'whsec_fixture',stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        self.client.v1.subscriptions.list.side_effect=RuntimeError('temporary failure')
        with self.assertRaises(RuntimeError):self.billing.webhook(body,'t='+stamp+',v1='+sig)
        with self.accounts.db() as db:self.assertIsNone(db.execute('SELECT * FROM events WHERE id=?',('evt_retry',)).fetchone())
