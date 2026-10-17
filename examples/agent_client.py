"""Minimal real stdio client: python examples/agent_client.py --home .proofpage sunlight."""
import argparse
import json
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--home', required=True)
parser.add_argument('query')
args = parser.parse_args()
messages = [
    {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'proofpage-example','version':'1'}}},
    {'jsonrpc':'2.0','method':'notifications/initialized'},
    {'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'proofpage_get_context','arguments':{'query':args.query}}},
]
result = subprocess.run([sys.executable,'-m','proofpage','--home',args.home,'mcp'],input='\n'.join(map(json.dumps,messages))+'\n',text=True,capture_output=True,check=True,timeout=30)
response = json.loads(result.stdout.splitlines()[-1])['result']
if response.get('isError'):
    raise SystemExit(response['content'][0]['text'])
print(json.dumps(json.loads(response['content'][0]['text']),indent=2))
