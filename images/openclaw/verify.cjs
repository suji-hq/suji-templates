const assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),path=require('node:path');
const paths={
 '/app/node_modules/.pnpm/npm@12.2.0/node_modules/npm/node_modules/undici':'6.29.1',
 '/app/node_modules/.pnpm/undici@8.11.2/node_modules/undici':'8.12.3',
 '/usr/local/lib/node_modules/npm/node_modules/undici':'8.12.3'
};
assert.equal(process.version,'v24.22.1');assert.equal(process.versions.modules,'137');
const found={};function walk(p){let st;try{st=fs.lstatSync(p)}catch{return}if(st.isSymbolicLink())return;if(st.isDirectory()){for(const n of fs.readdirSync(p))walk(path.join(p,n))}else if(path.basename(p)==='package.json'){const x=JSON.parse(fs.readFileSync(p));if(x.name==='undici')found[path.dirname(p)]=x.version}}
for(const p of ['/app/node_modules','/app/extensions','/usr/local/lib/node_modules'])walk(p);assert.deepEqual(found,paths);
assert.equal(require('/app/package.json').version,'2026.10.5');
(async()=>{const server=http.createServer((req,res)=>res.end('isolated-undici-smoke'));await new Promise(r=>server.listen(0,'127.0.0.1',r));try{for(const [p,v] of Object.entries(paths)){assert.equal(require(p+'/package.json').version,v);assert.deepEqual(require(p+'/package.json').dependencies||{},{});const r=await require(p).fetch('http://127.0.0.1:'+server.address().port);assert.equal(await r.text(),'isolated-undici-smoke');console.log(JSON.stringify({path:p,version:v,fetch:true}));}const sqlite=require('node:sqlite');const db=new sqlite.DatabaseSync(':memory:',{allowExtension:true});require('/app/node_modules/sqlite-vec').load(db);assert.equal(db.prepare('select vec_version() as version').get().version,'v0.1.9');assert.equal(db.prepare('select 1 as ok').get().ok,1);db.close();console.log(JSON.stringify({node:process.version,sqlite:true,uid:process.getuid()}));}finally{await new Promise(r=>server.close(r));}})().catch(e=>{console.error(e);process.exitCode=1});
