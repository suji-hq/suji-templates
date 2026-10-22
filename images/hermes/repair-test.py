"""Damage only a disposable container, then use real PM downloads/stage/publication."""
from pathlib import Path
import hashlib,json,os,subprocess,shutil,sys
from pm.paths import store_root
from pm.store import tree_digest
import pm.artifact_mirror as store_module
import pm.suji_security as security
from pm.install import ensure,installed_package

archive=Path(security.__file__).with_name('suji-security')/'undici6.tgz'
original=archive.read_bytes()
root=Path('/tmp/security-negative');dst=root/'lib/node_modules/npm/node_modules/undici';dst.mkdir(parents=True)
(dst/'package.json').write_text('{"name":"undici","version":"99.0.0"}')
try:security.patch_bundled_undici(root)
except ValueError as e:assert 'version' in str(e)
else:raise AssertionError('unexpected version accepted')
assert json.loads((dst/'package.json').read_text())['version']=='99.0.0'
shutil.rmtree(dst)
outside=Path('/tmp/suji-security-outside');outside.mkdir();(outside/'sentinel').write_text('untouched')
dst.symlink_to(outside)
try:security.patch_bundled_undici(root)
except ValueError as e:assert 'path' in str(e)
else:raise AssertionError('symlink escape accepted')
assert (outside/'sentinel').read_text()=='untouched'
dst.unlink();dst.mkdir()
(dst/'package.json').write_text('{"name":"undici","version":"6.27.0"}')
archive.write_bytes(original+b'corrupt')
try:
 try:security.patch_bundled_undici(root)
 except ValueError as e:assert 'checksum' in str(e)
 else:raise AssertionError('corrupt artifact accepted')
finally:archive.write_bytes(original)
assert (dst/'package.json').read_text()=='{"name":"undici","version":"6.27.0"}'
if '--negative-only' in sys.argv:
 print(json.dumps({'corruptArtifactRejected':True,'symlinkEscapeRejected':True,'versionDriftRejected':True,'originalUntouched':True}))
 sys.exit(0)
# Remove only disposable container tool trees to exercise actual recovery from missing artifacts.
for entry in ['node-26.12.1-linux-x64','npm-12.0.2-linux-x64']:
 shutil.rmtree(store_root()/entry)
home=Path(os.environ['HERMES_HOME']);home.mkdir(parents=True,exist_ok=True);os.chown(home,10000,10000)
os.setgid(10000);os.setuid(10000)
records=[];stages=[]
original_source=store_module.pinned_source
original_patch=security.patch_bundled_undici
def observed_source(url,destination,digest):
 records.append({'url':url,'sha256':digest});return original_source(url,destination,digest)
def observed_stage(staged):
 package=json.loads((staged/'lib/node_modules/npm/node_modules/undici/package.json').read_text())
 stages.append(package['version']);return original_patch(staged)
store_module.pinned_source=observed_source;security.patch_bundled_undici=observed_stage
ensure('npm',explicit=True,verify=True)
for name in ['node','npm']:
 item=installed_package(name);assert item.path.is_relative_to(home),str(item.path)
 assert json.loads((item.path/'lib/node_modules/npm/node_modules/undici/package.json').read_text())['version']=='6.29.1'
 facts=json.loads((item.path.parent/'facts.json').read_text())
 assert facts['packages'][name]['digest']==tree_digest(item.path)
node=installed_package('node');assert node.version=='26.12.1'
assert subprocess.check_output([str(node.binary),'--version'],text=True).strip()=='v26.12.1'
assert stages==['6.28.0','6.27.0'],stages
assert {r['url'] for r in records}=={'https://nodejs.org/dist/v26.12.1/node-v26.12.1-linux-x64.tar.xz','https://registry.npmjs.org/npm/-/npm-12.0.2.tgz'},records
print(json.dumps({'corruptArtifactRejected':True,'symlinkEscapeRejected':True,'versionDriftRejected':True,'originalUntouched':True,'repairDownloaded':records,'actualStages':stages,'repairPreservedPatches':True,'uid':os.getuid()}))
