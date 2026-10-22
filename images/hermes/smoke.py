"""Egress-isolated dashboard auth/persistence smoke, no LLM keys or calls."""
import pathlib,subprocess,yaml,secrets,json,time,urllib.request,urllib.error,http.cookiejar,os
root=pathlib.Path(__file__).resolve().parent
image=os.environ.get('MARKETPLACE_SMOKE_IMAGE','suji-marketplace-hermes:0.22.4-suji.1')
project='suji-hermes-test-20261022';password=secrets.token_hex(24);secret=secrets.token_hex(32)
source=(root/'compose.test.yaml').read_text()
for k,v in {'DASHBOARD_USERNAME':'isolated-smoke','DASHBOARD_PASSWORD':password,'DASHBOARD_SECRET':secret,'ANTHROPIC_API_KEY':'','OPENAI_API_KEY':'','OPENROUTER_API_KEY':''}.items():source=source.replace('${'+k+'}',v)
cfg=yaml.safe_load(source);svc=cfg['services']['hermes'];svc['image']=image;svc['restart']='no';svc.pop('ports',None)
cfg['networks']={'suji-net':{'internal':True}}
compose=root/'smoke-compose.private.yaml';compose.write_text(yaml.safe_dump(cfg,sort_keys=False));compose.chmod(0o600)
base=['docker','compose','-p',project,'-f',str(compose)]
def run(cmd,timeout=60):return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT,timeout=timeout)
def dc(*args,timeout=60):return run(base+list(args),timeout)
report={'image':image,'egressIsolated':True,'publishedPorts':False,'providerKeys':False,'llmRequests':0}
jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
try:
 dc('up','-d',timeout=120)
 cid=dc('ps','-q','hermes').strip();assert cid
 network=next(iter(json.loads(run(['docker','inspect',cid]))[0]['NetworkSettings']['Networks'].values()));url='http://'+network['IPAddress']+':9119'
 def request(path,data=None,auth=False):
  payload=json.dumps(data).encode() if data is not None else None
  req=urllib.request.Request(url+path,data=payload,headers={'Content-Type':'application/json','Origin':url,'Accept':'application/json'})
  opener=client if auth else urllib.request.build_opener()
  try:
   with opener.open(req,timeout=10) as r:return r.status,r.read()
  except urllib.error.HTTPError as e:return e.code,e.read()
 def ready():
  for _ in range(90):
   try:
    if request('/api/status')[0]==200:return
   except (OSError,TimeoutError):pass
   time.sleep(2)
  raise AssertionError('dashboard never became ready')
 ready();report['health']=request('/api/status')[0];report['loginPage']=request('/login')[0]
 report['missingSession']=request('/api/auth/me')[0];assert report['missingSession']==401
 wrong=request('/auth/password-login',{'provider':'basic','username':'isolated-smoke','password':'incorrect-smoke-password'})[0]
 assert wrong==401;report['wrongPassword']=wrong
 correct=request('/auth/password-login',{'provider':'basic','username':'isolated-smoke','password':password},True)[0]
 assert correct==200;report['correctPassword']=correct
 assert request('/api/auth/me',auth=True)[0]==200;report['authenticatedSession']=True
 # Root document after authentication must be the application, not a login redirect.
 assert request('/',auth=True)[0]==200
 run(['docker','exec',cid,'/bin/sh','-c','printf isolated-persistence-check > /opt/data/suji-smoke-marker'])
 dc('restart','hermes',timeout=90);ready()
 assert request('/api/auth/me',auth=True)[0]==200;report['sessionSurvivesRestart']=True
 assert run(['docker','exec',cid,'cat','/opt/data/suji-smoke-marker'])=='isolated-persistence-check';report['volumePersists']=True
 inspect=json.loads(run(['docker','inspect',cid]))[0]
 assert inspect['State']['Running'] and not inspect['State']['OOMKilled']
 processes=run(['docker','top',cid,'-eo','pid,uid,args'])
 assert '10000' in processes;report['nonRootChildren']=True
 report['running']=True;report['oomKilled']=False;report['passed']=True
except Exception as e:
 report['passed']=False;report['error']=(str(e)+' '+str(getattr(e,'output','')))[-3000:]
 try:report['logs']=dc('logs','--no-color','--tail','50')[-6000:]
 except Exception:pass
 raise
finally:
 cleanup_error=None
 try:
  dc('down','-v','--remove-orphans',timeout=120)
  for resource,args in [('containers',['ps','-a']),('volumes',['volume','ls']),('networks',['network','ls'])]:
   assert not run(['docker',*args,'--filter','label=com.docker.compose.project='+project,'-q']).strip(),resource+' remain'
  report['cleaned']=True;report['resourceCleanupConfirmed']=True
 except Exception as cleanup_error_value:
  cleanup_error=cleanup_error_value;report['cleaned']=False;report['passed']=False
 compose.unlink(missing_ok=True)
 print(json.dumps(report).replace(password,'[REDACTED]').replace(secret,'[REDACTED]'),flush=True)
 if cleanup_error:raise cleanup_error
