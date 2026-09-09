// Search stays on this site: Pagefind's static index is loaded on demand.
function revealAnchor() {
  let id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
  const target = document.getElementById(id);
  if (!target) return;
  const details = target.closest('details');
  if (details) {
    details.open = true;
    requestAnimationFrame(() => target.scrollIntoView({ block: 'start' }));
  }
}
window.addEventListener('hashchange', revealAnchor);
revealAnchor();

const trigger = document.querySelector('.search-trigger');
if (trigger) {
  const dialog = document.createElement('dialog');
  dialog.className = 'search-dialog';
  dialog.setAttribute('aria-labelledby', 'search-title');
  dialog.innerHTML = `
    <div class="search-top"><h2 id="search-title">Search Locus</h2><button class="search-close" type="button" aria-label="Close search">✕</button></div>
    <label class="search-label" for="site-search">Search the website</label>
    <input id="site-search" type="search" placeholder="Search questions, guides, and more…" autocomplete="off" spellcheck="false" autofocus>
    <p class="search-status" role="status" aria-live="polite">Find answers across FAQ and guides.</p>
    <ul class="search-results" aria-label="Search results"></ul>
    <div class="search-help">Try <button type="button" data-query="lying down">lying down</button>, <button type="button" data-query="Room Lights">Room Lights</button>, or <button type="button" data-query="imports">imports</button>.</div>`;
  document.body.append(dialog);
  const input = dialog.querySelector('input');
  const status = dialog.querySelector('.search-status');
  const results = dialog.querySelector('.search-results');
  let engine, timer, generation = 0;
  function loadEngine() {
    if (!engine) engine = import('/pagefind/pagefind.js').catch(error => { engine = null; throw error; });
    return engine;
  }
  function close() { generation++; clearTimeout(timer); dialog.close(); }
  trigger.hidden = false;
  trigger.addEventListener('click', () => { dialog.showModal(); input.focus(); });
  dialog.querySelector('.search-close').addEventListener('click', close);
  dialog.addEventListener('click', event => { if (event.target === dialog) close(); });
  dialog.addEventListener('close', () => trigger.focus());
  dialog.addEventListener('cancel', () => { generation++; clearTimeout(timer); });
  dialog.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); close(); }
  }, true);
  document.addEventListener('keydown', event => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      if (dialog.open) close(); else { dialog.showModal(); input.focus(); }
    }
  });
  // Only text and search highlights from the index enter result excerpts.
  function excerpt(html) {
    const parsed = new DOMParser().parseFromString(html, 'text/html');
    const fragment = document.createDocumentFragment();
    function append(node, parent) {
      if (node.nodeType === Node.TEXT_NODE) parent.append(document.createTextNode(node.textContent));
      else {
        const next = node.nodeName === 'MARK' ? document.createElement('mark') : parent;
        if (next !== parent) parent.append(next);
        for (const child of node.childNodes) append(child, next);
      }
    }
    for (const child of parsed.body.childNodes) append(child, fragment);
    return fragment;
  }
  async function search() {
    const own = ++generation;
    const query = input.value.trim();
    results.replaceChildren();
    if (!query) { status.textContent = 'Find answers across FAQ and guides.'; return; }
    status.textContent = 'Searching…';
    try {
      const pagefind = await loadEngine();
      const response = await pagefind.search(query);
      const pages = await Promise.all(response.results.map(result => result.data()));
      if (own !== generation) return;
      const seen = new Set();
      for (const page of pages) {
        for (const part of page.sub_results?.length ? page.sub_results : [{...page, title: page.meta.title}]) {
          const url = new URL(part.url, location.origin);
          if (url.origin !== location.origin || seen.has(url.href)) continue;
          seen.add(url.href);
          const item = document.createElement('li');
          const link = document.createElement('a');
          link.href = url.pathname + url.hash;
          const label = document.createElement('span'); label.className = 'search-source'; label.textContent = page.meta.title;
          const title = document.createElement('strong'); title.textContent = part.title;
          const text = document.createElement('p'); text.append(excerpt(part.excerpt));
          link.append(label, title, text);
          link.addEventListener('click', event => {
            if (url.pathname === location.pathname && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
              close();
              // Clicking the current hash does not emit hashchange.
              requestAnimationFrame(revealAnchor);
            }
          });
          item.append(link); results.append(item);
        }
      }
      const count = results.children.length;
      status.textContent = count ? `${count} ${count === 1 ? 'result' : 'results'}` : 'No results. Try another word, or browse the FAQ.';
    } catch {
      if (own !== generation) return;
      status.textContent = 'Search is unavailable right now. Try again, or browse the FAQ.';
      const item = document.createElement('li'); const link = document.createElement('a');
      link.href = '/faq/'; link.textContent = 'Browse the FAQ'; item.append(link); results.append(item);
    }
  }
  input.addEventListener('input', () => { generation++; clearTimeout(timer); timer = setTimeout(search, 120); });
  dialog.querySelectorAll('[data-query]').forEach(button => button.addEventListener('click', () => {
    clearTimeout(timer); input.value = button.dataset.query; input.focus(); search();
  }));
}
