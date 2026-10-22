"""Apply the reviewed security overlay to the exact immutable upstream image."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

def require(condition, message="Unexpected upstream image structure/version"):
    if not condition:
        raise RuntimeError(message)


ROOT = Path('/opt/hermes')
STORE = ROOT / 'tools'
SHA = {
    'pm/packages.py': 'b90ad2878c6289f7bd831cb40cc4315e1e81705768f2001af44666da7e703ccc',
    'pm/lock.json': '172dbe11404b0305e81c2cea4597cb8d680e642ea7f0591a79d7a305af5a0661',
    'tools/facts.json': 'e57104aa925deab78e65e1076f9b8d20d62065dee40ecff7338abad6a8846f0e',
}
require(subprocess.check_output(['uname', '-m'], text=True).strip() == 'x86_64', 'amd64 only')
require(subprocess.check_output(['/usr/local/bin/node', '--version'], text=True).strip() == 'v26.7.0')
for name, sha in SHA.items():
    require(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, 'upstream drift: ' + name)
source = (ROOT / 'pm/packages.py').read_text()
hook = '''
    def stage(self, store: Store, staged: Path, version: str, target: str) -> None:
        super().stage(store, staged, version, target)
        from pm.suji_security import patch_bundled_undici
        patch_bundled_undici(staged)
'''
for package in ['node', 'npm']:
    marker = f'    name = "{package}"\n'
    require(source.count(marker) == 1)
    source = source.replace(marker, marker + hook)
(ROOT / 'pm/packages.py').write_text(source)
sys.path.insert(0, str(ROOT))
from pm.suji_security import patch_bundled_undici
from pm.store import tree_digest

node = STORE / 'node-26.12.1-linux-x64'
npm = STORE / 'npm-12.0.2-linux-x64'
require(subprocess.check_output([str(node / 'bin/node'), '--version'], text=True).strip() == 'v26.12.1')
require(json.loads((npm / 'lib/node_modules/npm/package.json').read_text())['version'] == '12.0.2')
patch_bundled_undici(node)
patch_bundled_undici(npm)
photon = ROOT / 'plugins/platforms/photon/sidecar/node_modules/undici'
require(json.loads((photon / 'package.json').read_text())['version'] == '7.30.0')
archive = ROOT / 'pm/suji-security/undici7.tgz'
require(hashlib.sha256(archive.read_bytes()).hexdigest() == 'c98bd3881137c11341e8be8d2ec509ebf973b6f8b36d0a4c6d2afcda15e0d712')
staged = ROOT / 'pm/suji-security/photon'
staged.mkdir()
with tarfile.open(archive, 'r:gz') as tar:
    require(all((m.name.startswith('package/') and (m.isfile() or m.isdir()) for m in tar.getmembers())))
    tar.extractall(staged, filter='data')
require(json.loads((staged / 'package/package.json').read_text())['version'] == '7.30.1')
shutil.rmtree(photon)
(staged / 'package').rename(photon)
staged.rmdir()

lock = json.loads((ROOT / 'pm/lock.json').read_text())
facts = json.loads((STORE / 'facts.json').read_text())
require(lock['packages']['node']['version'] == facts['packages']['node']['version'] == '26.7.0')
require(lock['packages']['npm']['version'] == facts['packages']['npm']['version'] == '12.0.2')
sha = '6170b2d474e1c626f43cff3adc118df9fe3b573258a4fc3d850c8dbc6b079bbd'
lock['packages']['node'] = {'version': '26.12.1', 'artifacts': {'linux-x64': {
    'url': 'https://nodejs.org/dist/v26.12.1/node-v26.12.1-linux-x64.tar.xz', 'sha256': sha}}}
fact = facts['packages']['node']
fact.update(version='26.12.1', entry=node.name, artifacts=[sha], digest=tree_digest(node))
fact['env'] = {'PATH': ['{{store}}/' + node.name + '/bin']}
facts['packages']['npm']['digest'] = tree_digest(npm)
(ROOT / 'pm/lock.json').write_text(json.dumps(lock, indent=2, sort_keys=True) + '\n')
(STORE / 'facts.json').write_text(json.dumps(facts, indent=2, sort_keys=True) + '\n')
link = Path('/usr/local/bin/node')
require(link.is_symlink() and str(link.readlink()) == '/opt/hermes/tools/node-26.7.0-linux-x64/bin/node')
link.unlink()
link.symlink_to(node / 'bin/node')
shutil.rmtree(STORE / 'node-26.7.0-linux-x64')
print(json.dumps({'node': '26.12.1', 'npm': '12.0.2', 'undici': ['6.29.1', '6.29.1', '7.30.1'], 'pmStageHooks': ['node', 'npm'], 'platform': 'linux/amd64'}))
