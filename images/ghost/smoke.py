#!/usr/bin/env python3
"""Local disposable Ghost publishing/auth smoke; no external integration."""
import datetime, http.cookies, json, secrets, subprocess, sys, time, urllib.error, urllib.request, uuid
image = sys.argv[1]
name = 'suji-ghost-smoke-' + uuid.uuid4().hex[:10]
volume = name + '-data'
checks = {}
cookie = None

def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout.strip()

def endpoint():
    return 'http://127.0.0.1:' + docker('port', name, '2368/tcp').rsplit(':', 1)[1]

def request(path, data=None, authenticated=True):
    global cookie
    headers = {'Host': 'ghost-citest.suji.fr', 'Origin': 'http://ghost-citest.suji.fr', 'X-Forwarded-Proto': 'http'}
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
            if request('/ghost/api/admin/authentication/setup/')[0] == 200: return
        except (urllib.error.URLError, TimeoutError, ConnectionError): pass
        time.sleep(1)
    raise RuntimeError('Ghost did not become ready')

def require(name, condition, status=None):
    checks[name] = bool(condition)
    if not condition: raise RuntimeError(name + ' failed' + (': HTTP ' + str(status) if status else ''))

try:
    docker('volume', 'create', volume)
    docker('run', '-d', '--name', name, '--memory', '1024m', '--cpus', '1',
           '-p', '127.0.0.1::2368', '-v', volume + ':/var/lib/ghost/content',
           '-e', 'url=http://ghost-citest.suji.fr', '-e', 'database__client=sqlite3',
           '-e', 'database__connection__filename=/var/lib/ghost/content/data/ghost.db',
           '-e', 'security__staffDeviceVerification=false', '-e', 'privacy__useUpdateCheck=false',
           '-e', 'privacy__useGravatar=false', '-e', 'mail__transport=SMTP',
           '-e', 'mail__options__host=127.0.0.1', '-e', 'mail__options__port=9', image)
    base = endpoint(); ready(); checks['ready'] = True
    status, body = request('/'); require('publicSiteServed', status == 200 and '<html' in str(body).lower(), status)
    status, _ = request('/ghost/api/admin/posts/', authenticated=False); require('postsRequireAuth', status in (401, 403), status)
    email = name + '@example.invalid'; password = 'Test-A7!' + secrets.token_hex(20)
    status, body = request('/ghost/api/admin/authentication/setup/', {'setup': [{'name': 'Isolated Smoke', 'email': email, 'password': password, 'blogTitle': 'Isolated Ghost smoke'}]})
    require('ownerSetup', status in (200, 201), status)
    status, body = request('/ghost/api/admin/session/', {'username': email, 'password': password})
    require('login', status in (200, 201) and bool(cookie), status)
    owner_cookie = cookie
    status, _ = request('/ghost/api/admin/session/', {'username': email, 'password': secrets.token_hex(24)}, authenticated=False)
    require('badPasswordRejected', status in (400, 401, 403, 422), status)
    cookie = owner_cookie
    marker = 'isolated-publishing-' + uuid.uuid4().hex
    status, body = request('/ghost/api/admin/posts/?source=html', {'posts': [{'title': marker, 'html': '<p>' + marker + '</p>', 'status': 'published'}]})
    post = (body.get('posts') or [{}])[0] if isinstance(body, dict) else {}
    require('postPublished', status in (200, 201) and post.get('status') == 'published', status)
    slug = post['slug']
    status, body = request('/' + slug + '/', authenticated=False)
    require('publishedContentServed', status == 200 and marker in str(body), status)
    docker('restart', name); base = endpoint(); ready()
    status, _ = request('/ghost/api/admin/session/', {'username': email, 'password': password})
    require('loginAfterRestart', status in (200, 201), status)
    status, body = request('/' + slug + '/', authenticated=False)
    require('postPersists', status == 200 and marker in str(body), status)
    print(json.dumps({'checkedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'image': image, 'checks': checks, 'passed': all(checks.values())}, indent=2), flush=True)

finally:
    subprocess.run(['docker', 'rm', '-f', name], capture_output=True)
    subprocess.run(['docker', 'volume', 'rm', volume], capture_output=True)
    container_absent = subprocess.run(['docker', 'inspect', name], capture_output=True).returncode != 0
    volume_absent = subprocess.run(['docker', 'volume', 'inspect', volume], capture_output=True).returncode != 0
    print(json.dumps({'cleanup': {'containerAbsent': container_absent, 'volumeAbsent': volume_absent}}), flush=True)
    if not container_absent or not volume_absent: raise RuntimeError('Temporary resources remain')
