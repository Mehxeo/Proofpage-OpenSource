"""Build the dependency-free public docs from a curated set of repository guides."""
import html
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
PAGES = [('start','QUICKSTART.md','Start here'),('browser-capture','BROWSER_CAPTURE.md','Signed-in pages'),('media','MEDIA.md','Images, PDFs & automation'),('verify','VERIFY.md','Check quotes'),('rights','RIGHTS.md','Review rights'),('proof','PROOF.md','Receipts & archives'),('agents','TRAINING_AND_AGENTS.md','AI assistants & training'),('business','BUSINESS_CONTEXT.md','Business context'),('connectors','CONNECTORS.md','Google Docs & remote MCP'),('developers','DEVELOPER_WORKFLOW.md','Developer SDKs & replay'),('cli','CLI.md','Command line')]

def inline(text):
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    def link(m):
        label, url = m.groups()
        if not url.startswith(('https://','http://','/','#')):
            url = 'https://github.com/Mehxeo/Proofpage-OpenSource/blob/main/docs/' + url
        return f'<a href="{url}">{label}</a>'
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, text)

def render(text):
    result=[]; code=[]; paragraph=[]; fenced=False; table=False; listing=None
    def flush_paragraph():
        if paragraph:
            result.append('<p>'+inline(' '.join(paragraph))+'</p>'); paragraph.clear()
    def close_list():
        nonlocal listing
        if listing:
            result.append('</'+listing+'>'); listing=None
    for line in text.splitlines():
        if line.startswith(('<details', '</details', '![')): continue
        if line.startswith('```'):
            flush_paragraph(); close_list()
            if fenced: result.append('<pre><code>'+html.escape('\n'.join(code))+'</code></pre>'); code=[]
            fenced=not fenced; continue
        if fenced: code.append(line); continue
        if line.startswith('|'):
            flush_paragraph(); close_list()
            if not table: result.append('<div class="table-scroll"><table>');table=True
            if re.fullmatch(r'[| :\-]+',line):continue
            result.append('<tr>'+''.join('<td>'+inline(c.strip())+'</td>' for c in line.strip('|').split('|'))+'</tr>');continue
        if table: result.append('</table></div>');table=False
        match=re.match(r'^(#{1,3}) (.*)',line)
        if match:
            flush_paragraph(); close_list()
            level=min(len(match[1])+1,4);result.append(f'<h{level}>{inline(match[2])}</h{level}>')
            continue
        entry=re.match(r'^\s*(?:([-*])|\d+\.)\s+(.*)',line)
        if entry:
            flush_paragraph()
            kind='ul' if entry[1] else 'ol'
            if listing!=kind:
                close_list(); listing=kind; result.append('<'+kind+'>')
            result.append('<li>'+inline(entry[2])+'</li>')
        elif not line.strip():
            flush_paragraph(); close_list()
        elif listing and line.startswith(' '):
            # Wrapped list text belongs to the previous entry.
            result[-1]=result[-1][:-5]+' '+inline(line.strip())+'</li>'
        else:
            close_list(); paragraph.append(line.strip())
    flush_paragraph(); close_list()
    if table:result.append('</table></div>')
    return '\n'.join(result)

nav=''.join(f'<a href="#{slug}">{title}</a>' for slug,_,title in PAGES)
articles=''.join(f'<article id="{slug}" data-doc>{render((ROOT/"docs"/file).read_text())}</article>' for slug,file,_ in PAGES)
page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Proofpage documentation</title><meta name="description" content="Install Proofpage, capture pages, check quotes, review rights, export evidence, and connect your AI assistant."><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/style.css"><link rel="stylesheet" href="/docs/docs.css"><script src="/docs/docs.js" defer></script></head><body><header><a class="brand" href="/">Proofpage / Docs</a><nav><a href="/#download">Download</a><a href="https://github.com/Mehxeo/Proofpage-OpenSource">GitHub ↗</a></nav></header><div class="docs-layout"><aside><label for="docs-search">Find in docs</label><input id="docs-search" type="search" placeholder="Search topics…"><nav aria-label="Documentation">NAV</nav><p>Made by Utsav Das.</p></aside><main><h1>Get something useful done.</h1><p>Start with a page. Keep its evidence. Check a quote or prepare a reviewed dataset.</p><p id="search-status" role="status"></p>ARTICLES</main></div></body></html>'''.replace('NAV',nav).replace('ARTICLES',articles)
(ROOT/'website/docs/index.html').write_text(page)
