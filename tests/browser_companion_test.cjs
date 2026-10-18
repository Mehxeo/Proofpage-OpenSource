// Exercise the actual popup code with a deterministic extension/DOM fixture.
const vm=require('node:vm'),fs=require('node:fs'),assert=require('node:assert/strict');
const nodes={};for(const id of ['preview','status','result','url','text','consent','save','download','port','code','connect'])nodes[id]={value:'',textContent:'',hidden:false,disabled:false,checked:false};
let artifact,downloaded=false,fail=false;
const fixture=[['Readable account page',false,true],['password=never-copy',true,true],['hidden token',false,false],['Selected evidence',false,true]];
let index=0;
const document={title:'Member page',body:{},getElementById:id=>nodes[id],createElement:()=>({click(){downloaded=true;}}),createTreeWalker:()=>({nextNode(){const row=fixture[index++];return row?{textContent:row[0],parentElement:{closest:()=>row[1],getClientRects:()=>row[2]?[{}]:[]}}:null;}})};
const NativeURL=URL;class TestURL extends NativeURL{static createObjectURL(blob){artifact=blob;return 'blob:test';}static revokeObjectURL(){}}
const chrome={storage:{local:{get:async()=>({}),set:async()=>{}}},permissions:{request:async()=>true},tabs:{query:async()=>[{id:123}]},scripting:{executeScript:async({func,target})=>{assert.equal(target.tabId,123);if(fail)throw Error('Protected page');index=0;return [{result:func()}];}}};
const context={document,chrome,URL:TestURL,Blob,NodeFilter:{SHOW_TEXT:4},location:{href:'https://example.com/private?token=secret#session'},AbortSignal,fetch:async()=>({ok:true,json:async()=>({token:'scoped-test-token',added:1})}),getComputedStyle:()=>({visibility:'visible',display:'block'}),setTimeout:()=>{}};
vm.createContext(context);vm.runInContext(fs.readFileSync('browser-companion/popup.js','utf8'),context);
(async()=>{
 await nodes.preview.onclick();assert.equal(nodes.url.value,'https://example.com/private');assert.equal(nodes.text.value,'Readable account page\n\nSelected evidence');assert.equal(nodes.save.disabled,true);
 nodes.save.onclick();assert.equal(downloaded,false);
 nodes.text.value='Reviewed excerpt only';nodes.consent.checked=true;nodes.consent.onchange();assert.equal(nodes.save.disabled,false);nodes.download.onclick();assert.equal(downloaded,true);
 const data=JSON.parse(await artifact.text());assert.equal(data.text,'Reviewed excerpt only');assert.equal(data.attestation,'user_supplied');assert.equal(data.proofpage_capture,'visible-text-v1');assert.ok(!JSON.stringify(data).includes('secret'));assert.ok(!('cookies'in data));
 nodes.port.value='8765';nodes.code.value='ABCD';await nodes.connect.onclick();assert.match(nodes.status.textContent,/Connected/);await nodes.save.onclick();assert.match(nodes.status.textContent,/Saved to your Proofpage/);
 fail=true;await nodes.preview.onclick();assert.equal(nodes.result.hidden,true);assert.match(nodes.status.textContent,/Protected page/);
 const manifest=JSON.parse(fs.readFileSync('browser-companion/manifest.json'));assert.deepEqual(manifest.permissions,['activeTab','scripting','storage']);assert.equal(manifest.host_permissions,undefined);
 console.log('Browser companion: review gate, text filtering, redaction, URL sanitization, error path and least-privilege manifest passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
