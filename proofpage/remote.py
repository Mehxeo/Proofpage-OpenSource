"""Stdio-to-hosted bridge; credentials remain in environment, never tool arguments."""
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from .models import NoRedirect


def run():
    origin = os.environ.get('PROOFPAGE_REMOTE_URL','').rstrip('/')
    parsed=urllib.parse.urlsplit(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('PROOFPAGE_REMOTE_URL must be an HTTPS origin.')
    key=os.environ.get('PROOFPAGE_AGENT_KEY','')
    if not key.startswith('pp_'):raise ValueError('Set PROOFPAGE_AGENT_KEY to a hosted agent key.')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    for line in sys.stdin:
        mid=None
        try:
            payload=json.loads(line);mid=payload.get('id')
            request=urllib.request.Request(origin+'/agent',data=line.encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
            with opener.open(request,timeout=90) as response:
                body=response.read(16*1024*1024+1)
            if len(body)>16*1024*1024:raise ValueError('Response too large.')
            if mid is not None:print(json.dumps(json.loads(body)),flush=True)
        except Exception:
            if mid is not None:print(json.dumps({'jsonrpc':'2.0','id':mid,'error':{'code':-32000,'message':'Hosted request failed. Check the endpoint, key scope, quota, and server availability.'}}),flush=True)
