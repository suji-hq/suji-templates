const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const expected={"/usr/src/app/node_modules/@ai-sdk/amazon-bedrock/node_modules/undici": {"from": "6.28.1", "to": "6.29.1"}, "/usr/src/app/node_modules/@ai-sdk/anthropic/node_modules/undici": {"from": "6.28.1", "to": "6.29.1"}, "/usr/src/app/node_modules/@ai-sdk/azure/node_modules/undici": {"from": "6.28.1", "to": "6.29.1"}, "/usr/src/app/node_modules/@ai-sdk/deepseek/node_modules/undici": {"from": "6.28.1", "to": "6.29.1"}, "/usr/src/app/node_modules/@ai-sdk/gateway/node_modules/undici": {"from": "6.28.1", "to": "6.29.1"}, "/usr/src/app/node_modules/@ai-sdk/google/node_modules/undici": {"from": "6.28.1", "to": "6.29.1"}, "/usr/src/app/node_modules/@ai-sdk/groq/node_modules/undici": {"from": "6.28.1", "to": "6.29.1"}, "/usr/src/app/node_modules/@ai-sdk/openai/node_modules/undici": {"from": "6.28.1", "to": "6.29.1"}, "/usr/src/app/node_modules/ai/node_modules/undici": {"from": "6.28.1", "to": "6.29.1"}, "/usr/src/app/node_modules/undici": {"from": "7.29.1", "to": "7.30.1"}, "/usr/src/app/node_modules/undici8": {"from": "8.10.2", "to": "8.12.3"}};
assert.equal(process.version,'v24.22.1');
assert.equal(process.versions.modules,'137');
const found={};
function walk(root){for(const e of fs.readdirSync(root,{withFileTypes:true})){const p=path.join(root,e.name);if(e.isDirectory())walk(p);else if(e.isFile() && e.name==='package.json'){const m=JSON.parse(fs.readFileSync(p));if(m.name==='undici')found[path.dirname(p)]=m.version;}}}
walk('/usr/src/app/node_modules');
assert.deepEqual(found,Object.fromEntries(Object.entries(expected).map(([p,v])=>[p,v.to])));
(async()=>{
 const server=http.createServer((q,s)=>s.end('marketplace-undici-smoke'));await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{for(const [p,v] of Object.entries(expected)){const m=require(p+'/package.json');assert.deepEqual(m.dependencies||{},{});const r=await require(p).fetch('http://127.0.0.1:'+server.address().port);assert.equal(r.status,200);assert.equal(await r.text(),'marketplace-undici-smoke');console.log(JSON.stringify({package:p,version:v.to,fetch:true}));}}
 finally{await new Promise(r=>server.close(r));}
 const sharp=require('/usr/src/app/node_modules/sharp');const png=await sharp({create:{width:2,height:2,channels:3,background:'#ff0000'}}).png().toBuffer();assert.ok(png.length>0);
 const sqlite=require('/usr/src/app/node_modules/sqlite3');const db=new sqlite.Database(':memory:');await new Promise((res,rej)=>db.get('SELECT 42 AS value',(e,row)=>e?rej(e):(assert.equal(row.value,42),res())));await new Promise((res,rej)=>db.close(e=>e?rej(e):res()));
 console.log(JSON.stringify({nativeModules:{sharp:true,sqlite3:true},node:process.version,abi:process.versions.modules}));
})().catch(e=>{console.error(e);process.exitCode=1});
