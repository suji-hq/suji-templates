#!/usr/bin/env python3
"""Local disposable Crafty control-panel/auth smoke; no external integration."""
import datetime, json, secrets, subprocess, sys, time, urllib.error, urllib.request, uuid, ssl
image = sys.argv[1]
name = 'suji-crafty-smoke-' + uuid.uuid4().hex[:10]
volume = name + '-data'
checks = {}
token = None
context = ssl._create_unverified_context()  # Only this disposable loopback container's self-signed TLS.
def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()
def endpoint():
    return 'https://127.0.0.1:' + docker('port', name, '8443/tcp').rsplit(':', 1)[1]
def request(path, data=None, authenticated=True):
    headers = {}
    if token and authenticated: headers['Authorization'] = 'Bearer ' + token
    raw = None
    if data is not None: raw = json.dumps(data).encode(); headers['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, raw, headers), context=context, timeout=20) as response:
            body = response.read()
            try: result = json.loads(body)
            except ValueError: result = body.decode(errors='replace')
            return response.status, result
    except urllib.error.HTTPError as error:
        body = error.read()
        try: result = json.loads(body)
        except ValueError: result = body.decode(errors='replace')
        return error.code, result

def ready():
    for _ in range(180):
        try:
            if request('/api/v2/')[0] == 200: return
        except (urllib.error.URLError, TimeoutError, ConnectionError): pass
        time.sleep(1)
    raise RuntimeError('Crafty did not become ready')

def require(name, condition, status=None):
    checks[name] = bool(condition)
    if not condition: raise RuntimeError(name + ' failed' + (': HTTP ' + str(status) if status else ''))

try:
    docker('volume', 'create', volume)
    docker('run', '-d', '--name', name, '--memory', '2048m', '--cpus', '2',
           '-p', '127.0.0.1::8443', '-v', volume + ':/crafty/app/config', '-e', 'TZ=Etc/UTC', image)
    base = endpoint(); ready(); checks['ready'] = True
    status, body = request('/public/login'); require('loginPageServed', status == 200 and '<html' in str(body).lower(), status)
    status, _ = request('/api/v2/servers', authenticated=False); require('serversRequireAuth', status in (401, 403), status)
    credentials = docker('exec', name, 'cat', '/crafty/app/config/default-creds.txt')
    password = json.loads(credentials)['password']
    status, body = request('/api/v2/auth/login', {'username': 'admin', 'password': password})
    token = (body.get('data') or {}).get('token') if isinstance(body, dict) else None
    require('adminLogin', status == 200 and bool(token), status)
    status, _ = request('/api/v2/auth/login', {'username': 'admin', 'password': secrets.token_hex(24)}, authenticated=False)
    require('badPasswordRejected', status in (400, 401, 403), status)
    status, body = request('/api/v2/servers'); require('serverList', status == 200 and body.get('status') == 'ok', status)
    username = 'smoke_' + uuid.uuid4().hex[:8]; testpass = 'Test-A7!' + secrets.token_hex(20)
    status, body = request('/api/v2/users', {'username': username, 'password': testpass, 'email': username + '@example.invalid', 'superuser': False})
    require('createRestrictedUser', status == 201 and body.get('status') == 'ok', status)
    status, body = request('/api/v2/auth/login', {'username': username, 'password': testpass}, authenticated=False)
    restricted = (body.get('data') or {}).get('token') if isinstance(body, dict) else None
    require('restrictedUserLogin', status == 200 and bool(restricted), status)
    admin_token = token; token = restricted
    status, _ = request('/api/v2/users'); require('restrictedUserCannotListUsers', status in (401, 403), status)
    token = admin_token
    docker('restart', name); base = endpoint(); ready()
    status, body = request('/api/v2/auth/login', {'username': username, 'password': testpass}, authenticated=False)
    require('userPersistsAfterRestart', status == 200 and bool((body.get('data') or {}).get('token')), status)
    status, body = request('/api/v2/auth/login', {'username': 'admin', 'password': password}, authenticated=False)
    require('adminPersistsAfterRestart', status == 200 and bool((body.get('data') or {}).get('token')), status)
    print(json.dumps({'checkedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'image': image, 'checks': checks, 'passed': all(checks.values()), 'scope': 'Control panel authentication/authorization and persistence; no Minecraft game server created or EULA accepted'}, indent=2), flush=True)

finally:
    subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True)
    container_absent = subprocess.run(['docker', 'inspect', name], capture_output=True).returncode != 0
    volume_absent = subprocess.run(['docker', 'volume', 'inspect', volume], capture_output=True).returncode != 0
    print(json.dumps({'cleanup': {'containerAbsent': container_absent, 'volumeAbsent': volume_absent}}), flush=True)
    if not container_absent or not volume_absent: raise RuntimeError('Temporary resources remain')
