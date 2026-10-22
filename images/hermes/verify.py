"""Verify runtime, hashes, and fail-closed PM staging without external traffic."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tempfile
from pm.lock import Facts,Lockfile
from pm.paths import lockfile_path,store_root,facts_path
from pm.store import tree_digest
from pm.install import installed_package
from pm.suji_security import patch_bundled_undici

store=store_root();lock=Lockfile(lockfile_path());facts=Facts(facts_path())
assert subprocess.check_output(['node','--version'],text=True).strip()=='v26.12.1'
expected={store/'node-26.12.1-linux-x64/lib/node_modules/npm/node_modules/undici':'6.29.1',store/'npm-12.0.2-linux-x64/lib/node_modules/npm/node_modules/undici':'6.29.1',Path('/opt/hermes/plugins/platforms/photon/sidecar/node_modules/undici'):'7.30.1'}
for p,v in expected.items():
 assert json.loads((p/'package.json').read_text())['version']==v
 subprocess.run(['node','-e',"const u=require(process.argv[1]);if(typeof u.fetch!=='function')process.exit(1)",str(p)],check=True)
for name,version in [('node','26.12.1'),('npm','12.0.2')]:
 item=installed_package(name);assert item and item.version==version
 fact=facts.get(name);assert fact['digest']==tree_digest(item.path)
 assert facts.installed(name,version,store,('linux-x64',tuple(a['sha256'] for a in lock.artifacts(name,'linux-x64'))))
with tempfile.TemporaryDirectory() as d:
 root=Path(d);dst=root/'lib/node_modules/npm/node_modules/undici';dst.mkdir(parents=True)
 (dst/'package.json').write_text('{"name":"undici","version":"6.27.0"}')
 patch_bundled_undici(root)
 assert json.loads((dst/'package.json').read_text())['version']=='6.29.1'
 # Actual helper is idempotent and rejects layout/version drift.
 patch_bundled_undici(root)
 (dst/'package.json').write_text('{"name":"undici","version":"99.0.0"}')
 try:patch_bundled_undici(root)
 except ValueError:pass
 else:raise AssertionError('accepted version drift')
 shutil.rmtree(dst);dst.symlink_to('/tmp')
 try:patch_bundled_undici(root)
 except ValueError:pass
 else:raise AssertionError('accepted symlink escape')
print(json.dumps({'node':'26.12.1','undici':list(expected.values()),'pmFactsVerified':True,'idempotentStage':True,'versionDriftRejected':True,'symlinkEscapeRejected':True,'uid':os.getuid()}))
