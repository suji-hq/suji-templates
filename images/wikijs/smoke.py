#!/usr/bin/env python3
"""Disposable Wiki.js setup, auth, page publishing and SQLite persistence smoke."""
import datetime,json,secrets,subprocess,sys,time,urllib.error,urllib.request,uuid
image=sys.argv[1];name='suji-wikijs-smoke-'+uuid.uuid4().hex[:10];volume=name+'-data';checks={};token=None;mounted=[]
def docker(*args):return subprocess.run(['docker',*args],check=True,capture_output=True,text=True).stdout.strip()
def endpoint():return 'http://127.0.0.1:'+docker('port',name,'3000/tcp').rsplit(':',1)[1]
def require(key,value,status=None):
 checks[key]=bool(value)
 if not value:raise RuntimeError(key+' failed'+(': HTTP '+str(status) if status else ''))
def request(path,data=None,auth=True):
 headers={'Host':'wikijs-citest.suji.fr','Origin':'http://wikijs-citest.suji.fr'}
 if token and auth:headers['Authorization']='Bearer '+token
 raw=None
 if data is not None:raw=json.dumps(data).encode();headers['Content-Type']='application/json'
 try:
  with urllib.request.urlopen(urllib.request.Request(base+path,raw,headers),timeout=30) as r:status=r.status;body=r.read()
 except urllib.error.HTTPError as e:status=e.code;body=e.read()
 try:return status,json.loads(body)
 except ValueError:return status,body.decode(errors='replace')
def ready(path='/',graphql=False):
 for _ in range(120):
  try:
   status,body=request(path,{'query':'{ authentication { activeStrategies { key } } }'} if graphql else None)
   if status==200 and (not graphql or isinstance(body,dict) and 'data' in body):return
  except (urllib.error.URLError,TimeoutError,ConnectionError):pass
  time.sleep(1)
 raise RuntimeError('Wiki.js did not become ready')
def graphql(query,auth=True):
 status,body=request('/graphql',{'query':query},auth)
 return status,body

def login(email,password):
 query='mutation { authentication { login(username:'+json.dumps(email)+',password:'+json.dumps(password)+',strategy:"local") { responseResult { succeeded } jwt } } }'
 status,body=graphql(query,False);res=((body.get('data') or {}).get('authentication') or {}).get('login') or {} if isinstance(body,dict) else {}
 return status,res
try:
 docker('volume','create',volume)
 docker('run','-d','--name',name,'--memory','1024m','--cpus','1','-p','127.0.0.1::3000','-v',volume+':/wiki/data','-e','DB_TYPE=sqlite','-e','DB_FILEPATH=/wiki/data/wiki.sqlite',image)
 mounted=[m['Name'] for m in json.loads(docker('inspect',name))[0]['Mounts'] if m['Type']=='volume']
 base=endpoint();ready();checks['setupServed']=True
 email=name+'@example.invalid';password='Test-A7!'+secrets.token_hex(20)
 status,body=request('/finalize',{'adminEmail':email,'adminPassword':password,'siteUrl':'http://wikijs-citest.suji.fr','telemetry':False});require('setupComplete',status==200 and body.get('ok') is True,status)
 ready('/graphql',True)
 q='mutation { pages { create(content:"test",description:"test",editor:"markdown",isPublished:true,isPrivate:false,locale:"en",path:"unauthorized",tags:[],title:"Unauthorized") { responseResult { succeeded } page { id } } } }'
 status,body=graphql(q,False);res=((body.get('data') or {}).get('pages') or {}).get('create') or {};require('pageCreateRequiresAuth',bool(body.get('errors')) or res.get('responseResult',{}).get('succeeded') is False,status)
 status,res=login(email,password);require('login',status==200 and res.get('responseResult',{}).get('succeeded') and bool(res.get('jwt')),status);token=res['jwt']
 status,res=login(email,secrets.token_hex(24));require('badPasswordRejected',status==200 and res.get('responseResult',{}).get('succeeded') is False and not res.get('jwt'),status)
 marker='isolated-wiki-'+uuid.uuid4().hex
 q='mutation { pages { create(content:'+json.dumps('# '+marker)+',description:"Isolated test",editor:"markdown",isPublished:true,isPrivate:false,locale:"en",path:"smoke",tags:[],title:'+json.dumps(marker)+') { responseResult { succeeded } page { id path } } } }'
 status,body=graphql(q);res=((body.get('data') or {}).get('pages') or {}).get('create') or {};pid=(res.get('page') or {}).get('id');require('pagePublished',status==200 and res.get('responseResult',{}).get('succeeded') and pid,status)
 status,body=request('/en/smoke',auth=False);require('publicContentServed',status==200 and marker in str(body),status)
 docker('restart',name);base=endpoint();ready('/graphql',True)
 status,res=login(email,password);require('loginAfterRestart',status==200 and res.get('responseResult',{}).get('succeeded') and res.get('jwt'),status);token=res['jwt']
 status,body=request('/en/smoke',auth=False);require('pagePersists',status==200 and marker in str(body),status)
 status,body=graphql('mutation { pages { delete(id:'+str(pid)+') { responseResult { succeeded } } } }');res=((body.get('data') or {}).get('pages') or {}).get('delete') or {};require('pageDelete',status==200 and res.get('responseResult',{}).get('succeeded'),status)
 status,body=graphql('{ pages { list { id } } }');require('pageAbsent',status==200 and all(p['id']!=pid for p in body['data']['pages']['list']),status)
 print(json.dumps({'checkedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'image':image,'checks':checks,'passed':all(checks.values())},indent=2),flush=True)
finally:
 subprocess.run(['docker','rm','-fv',name],capture_output=True);subprocess.run(['docker','volume','rm',volume],capture_output=True)
 a=subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0;b=all(subprocess.run(['docker','volume','inspect',v],capture_output=True).returncode!=0 for v in set(mounted+[volume]))
 print(json.dumps({'cleanup':{'containerAbsent':a,'allVolumesAbsent':b}}),flush=True)
 if not a or not b:raise RuntimeError('Temporary resources remain')
