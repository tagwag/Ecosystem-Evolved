"""READ-ONLY probe of the server 'forest' (192.168.1.17) from the workstation: which ports answer, and what kind of
login Forest Chat asks for (the WWW-Authenticate header of its 401 reply). Sends no passwords; changes nothing.
Usage: python -m agent.forest_probe   -> prints a report and FOREST_PROBE_DONE"""
import socket, urllib.request, urllib.error
HOST = '192.168.1.17'
for port, what in ((22, 'SSH'), (8080, 'Forest Chat'), (11434, 'Ollama'), (80, 'web'), (443, 'https')):
    s = socket.socket(); s.settimeout(2)
    print(f'port {port:5d} ({what}):', 'OPEN' if s.connect_ex((HOST, port)) == 0 else 'closed'); s.close()
for path in ('/', '/api/tags', '/api/chat'):
    try:
        r = urllib.request.urlopen(urllib.request.Request(f'http://{HOST}:8080{path}', method='GET'), timeout=5)
        print(path, r.status, dict(r.headers))
    except urllib.error.HTTPError as e:
        print(path, e.code, 'WWW-Authenticate:', e.headers.get('WWW-Authenticate'), 'Server:', e.headers.get('Server'),
              'body:', e.read(300))
    except Exception as e:
        print(path, 'error', repr(e))
try:
    print('ollama direct:', urllib.request.urlopen(f'http://{HOST}:11434/api/tags', timeout=5).read(400))
except Exception as e:
    print('ollama direct: not reachable', repr(e))
u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); u.connect((HOST, 9)); print('this workstation LAN IP:', u.getsockname()[0])
print('FOREST_PROBE_DONE')
