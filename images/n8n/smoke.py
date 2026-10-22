#!/usr/bin/env python3
"""Local disposable n8n workflow/auth smoke; no external integration."""
import datetime, http.cookies, json, secrets, subprocess, sys, time, urllib.error, urllib.request, uuid
image = sys.argv[1]
name = 'suji-n8n-smoke-' + uuid.uuid4().hex[:10]
volume = name + '-data'
checks = {}
cookie = None

def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()

def endpoint():
    return 'http://127.0.0.1:' + docker('port', name, '5678/tcp').rsplit(':', 1)[1]

def request(path, data=None, authenticated=True):
    global cookie
    headers = {'Host': 'n8n-citest.suji.fr', 'Origin': 'https://n8n-citest.suji.fr', 'X-Forwarded-Proto': 'https'}
    if cookie and authenticated:
        headers['Cookie'] = cookie
    raw = None
    if data is not None:
        raw = json.dumps(data).encode(); headers['Content-Type'] = 'application/json'
    try:
        with urllib.request.urlopen(urllib.request.Request(base + path, raw, headers), timeout=20) as response:
            if response.headers.get('Set-Cookie'):
                parsed = http.cookies.SimpleCookie(); parsed.load(response.headers['Set-Cookie'])
                cookie = '; '.join(key + '=' + val.value for key, val in parsed.items())
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
    for _ in range(120):
        try:
            if request('/healthz/readiness')[0] == 200: return
        except (urllib.error.URLError, TimeoutError, ConnectionError): pass
        time.sleep(1)
    raise RuntimeError('n8n did not become ready')

def require(name, condition, status=None):
    checks[name] = bool(condition)
    if not condition: raise RuntimeError(name + ' failed' + (': HTTP ' + str(status) if status else ''))

try:
    docker('volume', 'create', volume)
    docker('run', '-d', '--name', name, '--memory', '1024m', '--cpus', '1',
           '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
           '-p', '127.0.0.1::5678', '-v', volume + ':/home/node/.n8n',
           '-e', 'GENERIC_TIMEZONE=UTC', '-e', 'N8N_DIAGNOSTICS_ENABLED=false',
           '-e', 'N8N_VERSION_NOTIFICATIONS_ENABLED=false', '-e', 'N8N_PERSONALIZATION_ENABLED=false', image)
    base = endpoint(); ready(); checks['ready'] = True
    status, body = request('/'); require('editorServed', status == 200 and '<html' in str(body).lower(), status)
    status, _ = request('/rest/workflows', authenticated=False); require('workflowsRequireAuth', status in (401, 403), status)
    email = name + '@example.invalid'; password = 'Test-A7!' + secrets.token_hex(20)
    status, body = request('/rest/owner/setup', {'email': email, 'firstName': 'Isolated', 'lastName': 'Smoke', 'password': password})
    require('ownerSetup', status == 200 and bool(cookie), status)
    status, body = request('/rest/login', {'emailOrLdapLoginId': email, 'password': password})
    require('login', status == 200 and bool(cookie), status)
    status, _ = request('/rest/login', {'emailOrLdapLoginId': email, 'password': secrets.token_hex(24)}, authenticated=False)
    require('badPasswordRejected', status in (400, 401, 403), status)
    workflow = {'name': name, 'nodes': [
        {'id': str(uuid.uuid4()), 'name': 'Manual Trigger', 'type': 'n8n-nodes-base.manualTrigger', 'typeVersion': 1, 'position': [0, 0], 'parameters': {}},
        {'id': str(uuid.uuid4()), 'name': 'No Operation', 'type': 'n8n-nodes-base.noOp', 'typeVersion': 1, 'position': [200, 0], 'parameters': {}}],
        'connections': {'Manual Trigger': {'main': [[{'node': 'No Operation', 'type': 'main', 'index': 0}]]}}, 'settings': {'executionOrder': 'v1'}}
    status, body = request('/rest/workflows', workflow)
    identifier = (body.get('data') or {}).get('id') if isinstance(body, dict) else None
    require('workflowCreate', status == 200 and bool(identifier), status)
    status, body = request('/rest/workflows/' + identifier + '/run', {'triggerToStartFrom': {'name': 'Manual Trigger'}})
    execution = (body.get('data') or {}).get('executionId') if isinstance(body, dict) else None
    require('workflowRun', status == 200 and bool(execution), status)
    for _ in range(60):
        status, body = request('/rest/executions/' + str(execution))
        data = body.get('data') or {} if isinstance(body, dict) else {}
        if data.get('status') in ('success', 'error', 'canceled', 'crashed'): break
        time.sleep(1)
    require('workflowExecutionSuccess', status == 200 and data.get('status') == 'success', status)
    docker('restart', name); base = endpoint(); ready()
    status, _ = request('/rest/login', {'emailOrLdapLoginId': email, 'password': password}); require('loginAfterRestart', status == 200, status)
    status, body = request('/rest/workflows/' + identifier)
    require('workflowPersists', status == 200 and (body.get('data') or {}).get('name') == name, status)
    print(json.dumps({'checkedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'image': image, 'checks': checks, 'passed': all(checks.values())}, indent=2), flush=True)
finally:
    subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True)
    container_absent = subprocess.run(['docker', 'inspect', name], capture_output=True).returncode != 0
    volume_absent = subprocess.run(['docker', 'volume', 'inspect', volume], capture_output=True).returncode != 0
    print(json.dumps({'cleanup': {'containerAbsent': container_absent, 'volumeAbsent': volume_absent}}), flush=True)
    if not container_absent or not volume_absent: raise RuntimeError('Temporary resources remain')
