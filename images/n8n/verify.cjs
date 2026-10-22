const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const root = '/usr/local/lib/node_modules/n8n/node_modules/.pnpm';
const expected = { 'undici@6.29.0': '6.29.1', 'undici@7.29.1': '7.30.1' };
assert.equal(process.version, 'v26.12.1');
assert.deepEqual(fs.readdirSync(root).filter(n => n.startsWith('undici@')).sort(), Object.keys(expected).sort());
(async () => {
  const server = http.createServer((req, res) => res.end('marketplace-undici-smoke'));
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  try {
    for (const [directory, version] of Object.entries(expected)) {
      const packagePath = path.join(root, directory, 'node_modules/undici');
      const metadata = require(path.join(packagePath, 'package.json'));
      assert.equal(metadata.version, version);
      assert.deepEqual(metadata.dependencies || {}, {});
      const undici = require(packagePath);
      const response = await undici.fetch(`http://127.0.0.1:${server.address().port}`);
      assert.equal(response.status, 200);
      assert.equal(await response.text(), 'marketplace-undici-smoke');
      console.log(JSON.stringify({ directory, version, fetch: true }));
    }
  } finally { await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode = 1; });
