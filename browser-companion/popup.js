const $ = id => document.getElementById(id);
let capture;
$('preview').onclick = async () => {
  $('status').textContent = 'Reading visible page text…'; $('result').hidden = true; capture = null;
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
      return {title:document.title,url:url.href,text:parts.join('\n\n'),created_at:new Date().toISOString()};
    }});
    if(!result?.text?.trim())throw new Error('No readable text found. Finish signing in or loading the page, then try again.');
    capture=result; $('url').value=result.url; $('text').value=result.text; $('consent').checked=false; $('save').disabled=true; $('result').hidden=false; $('status').textContent='Preview ready. Page text can still contain private information: review it before saving.';
  } catch(e) { $('status').textContent=e.message || 'This browser page cannot be captured.'; }
};
$('consent').onchange=()=>{$('save').disabled=!$('consent').checked;};
$('save').onclick=()=>{
 if(!capture||!$('consent').checked||!$('text').value.trim())return;
 const data={...capture,text:$('text').value,id:capture.url,proofpage_capture:'visible-text-v1',attestation:'user_supplied',coverage:'User-reviewed browser text. May be edited. No HTTP response, cookies, images, iframe content, or server authenticity proof. URL query and fragment omitted.'};
 const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='proofpage-browser-capture.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),10000);
 $('status').textContent='Download requested. Import the JSON file into Proofpage.';
};
