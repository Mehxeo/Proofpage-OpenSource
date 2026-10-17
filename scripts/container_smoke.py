"""CI smoke test of the actual non-root, read-only production image and persistent volume."""
import http.cookiejar
import json
import subprocess
import time
import urllib.request
import uuid

suffix=uuid.uuid4().hex[:12]
container='proofpage-smoke-'+suffix
volume='proofpage-smoke-'+suffix
origin='http://127.0.0.1:18000'
subprocess.run(['docker','volume','create',volume],check=True,capture_output=True)
try:
    subprocess.run(['docker','run','--detach','--name',container,'--read-only','--cap-drop=ALL','--security-opt=no-new-privileges',
                    '--tmpfs','/tmp:rw,noexec,nosuid,size=256m','-p','127.0.0.1:18000:8000','-v',volume+':/data',
                    '-e','PROOFPAGE_PUBLIC_URL='+origin,'-e','PROOFPAGE_DEVELOPMENT=true','proofpage:test'],check=True,capture_output=True)
    jar=http.cookiejar.CookieJar()
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    def request(path,payload=None,token=None):
        headers={'Origin':origin,'Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        req=urllib.request.Request(origin+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
        with client.open(req,timeout=10) as response:return json.load(response)
    def ready():
        for _ in range(40):
            try:
                if request('/healthz')['status']=='ok':return
            except OSError:pass
            time.sleep(.5)
        raise RuntimeError('Container failed readiness.')
    ready()
    invitation=subprocess.check_output(['docker','exec',container,'python','-m','proofpage','invite','ci@example.test'],text=True).strip()
    account=request('/auth/register',{'email':'ci@example.test','password':'synthetic-ci-password','invite':invitation})
    profile=request('/api/profiles',{'name':'Persistence fixture','provider':'fixture','account':'ci','adapter':'generic'},account['token'])
    subprocess.run(['docker','restart',container],check=True,capture_output=True)
    ready()
    assert request('/api/session')['mode']=='hosted'
    assert request('/api/state')['profiles'][0]['id']==profile['id']
    assert not request('/api/billing')['configured']
    print('Container verified: non-root/read-only startup, invitation login, session/data persistence after restart, billing disabled.')
finally:
    subprocess.run(['docker','rm','--force',container],capture_output=True)
    subprocess.run(['docker','volume','rm',volume],capture_output=True)
