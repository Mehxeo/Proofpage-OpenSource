const search=document.getElementById('docs-search');
search.addEventListener('input',()=>{const query=search.value.toLowerCase().trim();let count=0;document.querySelectorAll('[data-doc]').forEach(article=>{article.hidden=!!query&&!article.textContent.toLowerCase().includes(query);if(!article.hidden)count++;});document.getElementById('search-status').textContent=query?`${count} matching topics`:'';});
document.querySelectorAll('aside a').forEach(link=>link.addEventListener('click',()=>{search.value='';search.dispatchEvent(new Event('input'));}));
