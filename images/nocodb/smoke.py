#!/usr/bin/env python3
"""Disposable NocoDB auth, SQLite record CRUD and persistence smoke."""
import datetime, json, secrets, subprocess, sys, time, urllib.error, urllib.request, uuid
image=sys.argv[1]; name='suji-nocodb-smoke-'+uuid.uuid4().hex[:10]; volume=name+'-data'; checks={}; token=None

def docker(*args): return subprocess.run(['docker',*args],check=True,capture_output=True,text=True).stdout.strip()
def endpoint():return 'http://127.0.0.1:'+docker('port',name,'8080/tcp').rsplit(':',1)[1]
def require(key,condition,status=None):
 checks[key]=bool(condition)
 if not condition:raise RuntimeError(key+' failed'+(': HTTP '+str(status) if status else ''))
def request(path,data=None,method=None,auth=True):
 headers={'Host':'nocodb-citest.suji.fr','Origin':'https://nocodb-citest.suji.fr','X-Forwarded-Proto':'https'}
 if token and auth:headers['xc-auth']=token
 raw=None
 if data is not None:raw=json.dumps(data).encode();headers['Content-Type']='application/json'
 try:
  with urllib.request.urlopen(urllib.request.Request(base+path,raw,headers,method=method),timeout=25) as r:status=r.status;body=r.read()
 except urllib.error.HTTPError as e:status=e.code;body=e.read()
 try:return status,json.loads(body)
 except ValueError:return status,body.decode(errors='replace')
def ready():
 for _ in range(120):
  try:
   if request('/api/v1/health')[0]==200:return
  except (urllib.error.URLError,TimeoutError,ConnectionError):pass
  time.sleep(1)
 raise RuntimeError('NocoDB did not become ready')
try:
 docker('volume','create',volume)
 docker('run','-d','--name',name,'--memory','2048m','--cpus','1','-p','127.0.0.1::8080','-v',volume+':/usr/app/data','-e','NC_AUTH_JWT_SECRET='+secrets.token_hex(32),'-e','NC_PUBLIC_URL=https://nocodb-citest.suji.fr','-e','NC_DISABLE_TELE=true',image)
 base=endpoint();ready();checks['ready']=True
 status,body=request('/');require('webAppServed',status==200 and '<html' in str(body).lower(),status)
 status,_=request('/api/v2/meta/bases',auth=False);require('basesRequireAuth',status in (401,403),status)
 email=name+'@example.invalid'; password='Test-A7!'+secrets.token_hex(20)
 status,body=request('/api/v1/auth/user/signup',{'email':email,'password':password,'display_name':'Isolated Smoke'})
 token=body.get('token') if isinstance(body,dict) else None;require('signup',status in (200,201) and bool(token),status)
 status,body=request('/api/v1/auth/user/signin',{'email':email,'password':password},auth=False)
 require('login',status==200 and bool(body.get('token')),status);token=body['token']
 status,_=request('/api/v1/auth/user/signin',{'email':email,'password':secrets.token_hex(24)},auth=False);require('badPasswordRejected',status in (400,401,403),status)
 status,body=request('/api/v2/meta/bases',{'title':name});base_id=body.get('id') if isinstance(body,dict) else None;require('baseCreate',status in (200,201) and bool(base_id),status)
 status,body=request('/api/v2/meta/bases/'+base_id+'/tables',{'title':'SmokeRecords','table_name':'smoke_records','columns':[{'title':'Id','column_name':'id','uidt':'ID','dt':'integer','pk':True,'ai':True,'rqd':True},{'title':'Name','column_name':'name','uidt':'SingleLineText','dt':'varchar','pv':True}]})
 table_id=body.get('id') if isinstance(body,dict) else None;require('tableCreate',status in (200,201) and bool(table_id),status)
 path='/api/v2/tables/'+table_id+'/records';marker=uuid.uuid4().hex
 status,body=request(path,{'Name':marker});rid=body.get('Id') if isinstance(body,dict) else None;require('recordCreate',status in (200,201) and rid is not None,status)
 status,body=request(path);require('recordRead',status==200 and any(x.get('Name')==marker for x in body.get('list',[])),status)
 marker+='updated';status,_=request(path,{'Id':rid,'Name':marker},method='PATCH');require('recordUpdate',status in (200,201),status)
 docker('restart',name);base=endpoint();ready()
 status,body=request('/api/v1/auth/user/signin',{'email':email,'password':password},auth=False);require('loginAfterRestart',status==200 and bool(body.get('token')),status);token=body['token']
 status,body=request(path);require('recordPersists',status==200 and any(x.get('Name')==marker for x in body.get('list',[])),status)
 status,_=request(path,{'Id':rid},method='DELETE');require('recordDelete',status in (200,201),status)
 status,body=request(path);require('recordAbsent',status==200 and all(x.get('Id')!=rid for x in body.get('list',[])),status)
 print(json.dumps({'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image':image,'checks':checks,'passed':all(checks.values())},indent=2),flush=True)
finally:
 subprocess.run(['docker','rm','-f',name],capture_output=True);subprocess.run(['docker','volume','rm',volume],capture_output=True)
 a=subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0;b=subprocess.run(['docker','volume','inspect',volume],capture_output=True).returncode!=0
 print(json.dumps({'cleanup':{'containerAbsent':a,'volumeAbsent':b}}),flush=True)
 if not a or not b:raise RuntimeError('Temporary resources remain')
