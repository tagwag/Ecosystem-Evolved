"""Ask the server 'forest' to download an Ollama model through Forest Chat (port 8080), then list its models.
Usage: python -m agent.forest_pull qwen2.5:7b
If Forest Chat does not pass /api/pull through, this prints PULL_NOT_PROXIED and the owner runs on the server:
    ollama pull qwen2.5:7b
"""
import json, sys, urllib.request
BASE = 'http://192.168.1.17:8080'
name = sys.argv[1] if len(sys.argv) > 1 else 'qwen2.5:7b'
def call(path, body=None, timeout=60):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)
try:
    with call('/api/pull', {'model': name, 'stream': True}, timeout=3600) as r:
        last = ''
        for line in r:
            try: st = json.loads(line).get('status', '')
            except Exception: st = line[:120]
            if st != last: print(st, flush=True); last = st
    print('PULL_FINISHED', name)
except Exception as e:
    print('PULL_NOT_PROXIED or failed:', repr(e)); print('Run on the server:  ollama pull', name)
try:
    print('models on forest:', [m['name'] for m in json.loads(call('/api/tags').read())['models']])
except Exception as e:
    print('could not list models:', repr(e))
print('FOREST_PULL_DONE')
