"""Disposable, egress-isolated validation of the existing Suji compose contract."""
import pathlib,subprocess,yaml,secrets,json,time,urllib.request,urllib.error,hashlib,sys,os
root=pathlib.Path(__file__).resolve().parent
image=os.environ.get('MARKETPLACE_SMOKE_IMAGE','suji-marketplace-openclaw:2026.10.5-suji.1')
project='suji-openclaw-test-20261022'; token=secrets.token_hex(32)
values={'AI_PROVIDER':'openai','AI_MODEL':'gpt-5.5','AI_API_KEY':'','AI_BASE_URL':'','OPENCLAW_GATEWAY_PASSWORD':token,'TELEGRAM_BOT_TOKEN':'','DISCORD_BOT_TOKEN':''}
source=(root/'compose.test.yaml').read_text()
for k,v in values.items():source=source.replace('${'+k+'}',v)
cfg=yaml.safe_load(source)
for name,service in cfg['services'].items():
 if name!='init-perms':service['image']=image
 service['restart']='no';service['networks']=['suji-net']
cfg['services']['openclaw'].pop('ports',None)
cfg['networks']={'suji-net':{'internal':True}}
compose=root/'smoke-compose.private.yaml';compose.write_text(yaml.safe_dump(cfg,sort_keys=False));compose.chmod(0o600)
base=['docker','compose','-p',project,'-f',str(compose)]
def run(cmd,timeout=60):return subprocess.check_output(cmd,text=True,stderr=subprocess.STDOUT,timeout=timeout)
def dc(*args,timeout=60):return run(base+list(args),timeout)
report={'image':image,'egressIsolated':True,'privateBridgeOnly':True,'publishedPorts':False,'fakeProviderKeys':False,'llmRequests':0,'channelTokensProvided':False}
def emit():print(json.dumps(report),flush=True)
try:
 dc('up','-d',timeout=300)
 cid=dc('ps','-q','openclaw').strip();assert cid
 network=next(iter(json.loads(run(['docker','inspect',cid]))[0]['NetworkSettings']['Networks'].values()))
 url='http://'+network['IPAddress']+':18789'
 def request(path,auth=None,data=None):
  headers={'Authorization':'Bearer '+auth} if auth else {}
  if data is not None:headers['Content-Type']='application/json'
  req=urllib.request.Request(url+path,data=data,headers=headers)
  try:
   with urllib.request.urlopen(req,timeout=30 if path=='/tools/invoke' else 5) as r:return r.status,r.read()
  except urllib.error.HTTPError as e:return e.code,e.read()
 ready=False
 for _ in range(90):
  try:
   checks={p:request(p)[0] for p in ['/healthz','/startupz','/readyz','/']}
   report['lastReadiness']=checks
   if all(s==200 for s in checks.values()):ready=True;break
  except (OSError,TimeoutError):pass
  time.sleep(2)
 assert ready,'readiness never became ready: '+str(report.get('lastReadiness'))
 report['health']={p:request(p)[0] for p in ['/healthz','/startupz','/readyz','/']}
 assert all(s==200 for s in report['health'].values()),report['health']
 body=b'{"tool":"sessions_list","args":{}}'
 report['toolAuth']={}
 for label,auth in [('missing',None),('wrong','invalid-smoke-token'),('correct',token)]:
  report['toolAuth'][label]=request('/tools/invoke',auth=auth,data=body)[0]
 assert report['toolAuth']['missing']==401 and report['toolAuth']['wrong']==401,report['toolAuth']
 assert report['toolAuth']['correct']==200,report['toolAuth']
 config=json.loads(run(['docker','exec',cid,'cat','/home/node/.openclaw/openclaw.json']))
 assert config['gateway']['mode']=='local' and config['gateway']['bind']=='lan'
 assert config['gateway']['controlUi']['dangerouslyAllowHostHeaderOriginFallback'] is True
 assert config['agents']['defaults']['model']['primary']=='openai/gpt-5.5'
 # Capture bytes before rerunning the existing seed script; no customer data exists.
 before=run(['docker','exec',cid,'cat','/home/node/.openclaw/openclaw.json'])
 dc('run','--rm','--no-deps','init-config',timeout=240)
 after=run(['docker','exec',cid,'cat','/home/node/.openclaw/openclaw.json'])
 assert before==after,'repeat init modified existing configuration'
 report['repeatInitPreservedConfig']=True;
 fail_script='node() { return 42; };\n'+cfg['services']['init-config']['command'][0].replace('$$','$')
 failed=subprocess.run(['docker','run','--rm','--network','none','--memory','128m','--cpus','.1','--entrypoint','/bin/sh',image,'-c',fail_script],text=True,capture_output=True,timeout=30)
 assert failed.returncode==42,{'initFailureExit':failed.returncode}
 report['initCommandFailureStops']=True
 invalid_script='printf %s \"{invalid-json5\" > /home/node/.openclaw/openclaw.json;\n'+cfg['services']['init-config']['command'][0].replace('$$','$')
 invalid=subprocess.run(['docker','run','--rm','--network','none','--memory','128m','--cpus','.1','--tmpfs','/home/node/.openclaw:rw,uid=1000,gid=1000','--entrypoint','/bin/sh',image,'-c',invalid_script],text=True,capture_output=True,timeout=30)
 assert invalid.returncode!=0 and 'JSON5' in invalid.stderr,{'invalidConfigExit':invalid.returncode}
 report['invalidConfigRejected']=True;report['configSha256']=hashlib.sha256(after.encode()).hexdigest()
 inspect=json.loads(run(['docker','inspect',cid]))[0]
 report['process']={'running':inspect['State']['Running'],'restarts':inspect['RestartCount'],'oomKilled':inspect['State']['OOMKilled']};assert report['process']['running'] and report['process']['restarts']==0
 report['memoryLimits']={'initMiB':512,'gatewayMiB':2048};report['passed']=True
except Exception as e:
 report['passed']=False;report['error']=(str(e)+' '+str(getattr(e,'output',''))).replace(token,'[REDACTED]')[-5000:]
 try:report['logs']=dc('logs','--no-color','--tail','35').replace(token,'[REDACTED]')[-7000:]
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
 compose.unlink(missing_ok=True);emit()
 if cleanup_error:raise cleanup_error
