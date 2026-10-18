const $ = id => document.getElementById(id);
let capture;
$('preview').onclick = async () => {
  $('preview').disabled=true; $('status').textContent = 'Preparing your page…'; $('result').hidden = true; $('download').disabled=true; capture = null;
  try {
    const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
    const [{result}] = await chrome.scripting.executeScript({target:{tabId:tab.id},func:() => {
      const url = new URL(location.href);
      if (!['http:','https:'].includes(url.protocol)) throw new Error('Open an ordinary web page first.');
      // Do not persist query tokens, fragments, cookies, form values, or hidden DOM.
      url.search=''; url.hash=''; url.username=''; url.password='';
      const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
      const parts=[]; let node, size=0;
      while ((node=walker.nextNode())) {
        const el=node.parentElement;
        if (!el || el.closest('script,style,noscript,form,input,textarea,select,[contenteditable],[hidden],[aria-hidden="true"]')) continue;
        const style=getComputedStyle(el); if(style.visibility==='hidden'||style.display==='none'||!el.getClientRects().length)continue;
        const text=node.textContent.trim();if(!text)continue;
        size+=text.length; if(size>500000)throw new Error('Page is too large. Select a smaller page or export it manually.');
        parts.push(text);
      }
      const visible = el => !el.closest('form,[contenteditable],[hidden],[aria-hidden="true"]') && el.getClientRects().length && getComputedStyle(el).visibility!=='hidden';
      const clean = value => {try {const u=new URL(value,location.href);if(!['http:','https:'].includes(u.protocol))return '';u.search='';u.hash='';u.username='';u.password='';return u.href;}catch{return '';}};
      const links=[...document.querySelectorAll('a[href]')].filter(visible).slice(0,100).map(el=>({label:(el.innerText||'Link').trim().slice(0,300),url:clean(el.href)})).filter(x=>x.url);
      const images=[...document.querySelectorAll('img')].filter(visible).slice(0,50).map(el=>({label:(el.alt||'Image without alt text').slice(0,300),url:clean(el.currentSrc||el.src)})).filter(x=>x.url);
      const tables=[...document.querySelectorAll('table')].filter(visible).slice(0,20).map(el=>[...el.querySelectorAll('tr')].filter(visible).slice(0,100).map(row=>[...row.querySelectorAll('th,td')].filter(visible).map(cell=>cell.innerText.trim().slice(0,1000)).join(' | ')).join('\n').slice(0,20000));
      return {title:document.title,url:url.href,text:parts.join('\n\n'),links,images,tables,created_at:new Date().toISOString()};
    }});
    if(!result?.text?.trim()&&!result?.images?.length&&!result?.tables?.length)throw new Error('No readable text found. Finish signing in or loading the page, then try again.');
    capture=result;
    for(const kind of ['links','images','tables']) {
      const entries=result[kind]||[];
      $(kind).value=kind==='tables'?entries.join('\n\n'):entries.map(x=>x.label+' — '+x.url).join('\n');
      $(kind+'-count').textContent=String(entries.length);
      $('include-'+kind).checked=false; $(kind).hidden=true;
      $('include-'+kind).disabled=!entries.length;
    }
    $('capture-count').textContent=result.text.length.toLocaleString()+' characters';
    $('url').value=result.url; $('text').value=result.text; $('consent').checked=false; $('save').disabled=true; $('result').hidden=false; $('status').textContent='Preview ready. Page text can still contain private information: review it before saving.';
  } catch(e) { $('status').textContent=e.message || 'This browser page cannot be captured.'; } finally { $('preview').disabled=false; }
};
$('consent').onchange=()=>{$('save').disabled=!$('consent').checked; $('download').disabled=!$('consent').checked;};
function reviewedCapture(){
 const page_parts={};
 for(const kind of ['links','images','tables'])if($('include-'+kind).checked&&$(kind).value.trim()){const value=$(kind).value.trim();if(value.length>100000)throw new Error('Reduce '+kind+' to 100,000 characters before saving.');page_parts[kind]=value;}
 const text=[$('text').value.trim(),...Object.entries(page_parts).map(([kind,value])=>kind.toUpperCase()+'\n'+value)].filter(Boolean).join('\n\n');
 if(!text)throw new Error('Keep some page text or include a reference or table before saving.');
 if(text.length>500000)throw new Error('Capture is too large. Remove some content before saving.');
 return {title:capture.title,url:capture.url,created_at:capture.created_at,text,page_parts,id:capture.url,proofpage_capture:'visible-text-v1',attestation:'user_supplied',coverage:'User-reviewed browser content and optional references/table text. May be edited. No downloaded media, HTTP response, cookies, iframe content, or server authenticity proof. URL query and fragment omitted.'};
}
function downloadCapture(){
 if(!capture||!$('consent').checked)return;
 let data;try{data=reviewedCapture();}catch(e){$('status').textContent=e.message;return;}
 const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='proofpage-browser-capture.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
 $('status').textContent='Download requested. Import the JSON file into Proofpage.';
};

$('download').disabled=true;
$('download').onclick=downloadCapture;
let connection;
chrome.storage.local.get('connection').then(saved=>{connection=saved.connection; if(connection){$('port').value=connection.port; $('connection-state').textContent='Pairing saved';}});
async function request(path, data, port, token) {
 const response=await fetch(`http://127.0.0.1:${port}/api/companion/${path}`, {method:'POST',headers:{'Content-Type':'application/json',...(token?{'Authorization':'Bearer '+token}:{})},body:JSON.stringify(data),signal:AbortSignal.timeout(15000)});
 const result=await response.json();
 if(response.status===401&&token){connection=null;await chrome.storage.local.remove('connection');$('connection-state').textContent='Reconnect needed';$('connection-panel').open=true;}
 if(response.status===404&&path==='import-file')throw new Error('This app version does not support original-file imports. Update Proofpage first.');
 if(!response.ok)throw new Error(result.error||'Unable to connect.'); return result;
}
$('connect').onclick=async()=>{
 try {
  const port=Number($('port').value);
  if(!Number.isInteger(port)||port<1||port>65535)throw new Error('Enter the port shown in Proofpage Settings.');
  if(!await chrome.permissions.request({origins:['http://127.0.0.1/*']}))throw new Error('Allow access to your local app to connect.');
  const result=await request('pair',{code:$('code').value.trim().toUpperCase()},port);
  connection={port,token:result.token}; await chrome.storage.local.set({connection}); $('code').value=''; $('connection-state').textContent='Connected'; $('connection-panel').open=false; $('status').textContent='Connected. Preview a page, review it, then save.';
 }catch(e){$('status').textContent=e.message||'Open Proofpage and try again.';}
};
$('save').onclick=async()=>{
 if(!capture||!$('consent').checked)return;
 if(!connection){$('connection-panel').open=true; $('status').textContent='Connect to Proofpage above first, or choose Download JSON instead.';return;}
 $('save').disabled=true;
 try {
  const result=await request('import',{reviewed:true,capture:reviewedCapture()},connection.port,connection.token);
  if(result.errors?.length)throw new Error(result.errors[0].error);
  $('status').textContent=result.added?'Saved to your Proofpage library.':'Already saved. Your library is up to date.';
 }catch(e){$('status').textContent=(e.message||'Could not reach Proofpage.')+' Open the app or download the JSON instead.';}
 finally{$('save').disabled=false;}
};

for(const kind of ['links','images','tables'])$('include-'+kind).onchange=()=>{$(kind).hidden=!$('include-'+kind).checked;};

function fileReady(){ $('save-file').disabled=!$('original-file').files.length||!$('file-consent').checked; }
$('original-file').onchange=()=>{$('file-consent').checked=false;fileReady();};
$('file-consent').onchange=fileReady;
$('save-file').onclick=async()=>{
 if(!$('file-consent').checked)return;
 const file=$('original-file').files[0];if(!file)return;
 if(!connection){$('connection-panel').open=true;$('status').textContent='Connect your desktop app before saving a file.';return;}
 $('save-file').disabled=true;
 try{
  if(!file.size||file.size>8*1024*1024)throw new Error('Choose a nonempty file up to 8 MiB.');
  const bytes=new Uint8Array(await file.arrayBuffer());let binary='';
  for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  const result=await request('import-file',{reviewed:true,filename:file.name,data:btoa(binary)},connection.port,connection.token);
  if(result.errors?.length)throw new Error(result.errors[0].error);
  $('status').textContent=result.added?'Original file saved. Open your library to preview or download it.':'This original file is already in your library.';
 }catch(e){$('status').textContent=(e.message||'File import failed.')+' You can also use Import files in the desktop app.';}
 finally{fileReady();}
};
