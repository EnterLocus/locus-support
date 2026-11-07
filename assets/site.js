// Shared navigation. Search and language selection keep their existing public behavior.
(() => {
  const header = document.querySelector('.site-header');
  const nav = header?.querySelector('nav');
  if (!header || !nav) return;
  const t = text => window.LocusLocalization?.strings?.[text] || text;
  const actions = document.createElement('div');
  actions.className = 'site-actions';
  const search = nav.querySelector('.search-trigger');
  if (search) actions.append(search);
  const toggle = document.createElement('button');
  toggle.className = 'menu-toggle'; toggle.type = 'button';
  toggle.innerHTML = '<span></span><span></span>';
  toggle.setAttribute('aria-expanded', 'false');
  toggle.setAttribute('aria-label', t('Open menu'));
  nav.id = 'site-navigation'; toggle.setAttribute('aria-controls', nav.id);
  actions.append(toggle); header.append(actions); header.classList.add('is-enhanced');
  const narrow = matchMedia('(max-width: 1100px)');
  const isOpen = () => toggle.getAttribute('aria-expanded') === 'true';
  function setOpen(open, restore = false) {
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', t(open ? 'Close menu' : 'Open menu'));
    document.body.classList.toggle('menu-open', open);
    if (restore) toggle.focus();
  }
  toggle.addEventListener('click', () => setOpen(!isOpen()));
  nav.addEventListener('click', event => { if (event.target.closest('a')) setOpen(false); });
  search?.addEventListener('click', () => setOpen(false));
  document.addEventListener('keydown', event => {
    if (!isOpen() || document.querySelector('dialog[open]')) return;
    if (event.key === 'Escape') { event.preventDefault(); setOpen(false, true); }
    if (event.key === 'Tab') {
      const items = [toggle, ...nav.querySelectorAll('a, button:not([hidden]), select')];
      const index = items.indexOf(document.activeElement);
      event.preventDefault();
      items[(index + (event.shiftKey ? -1 : 1) + items.length) % items.length].focus();
    }
  });
  narrow.addEventListener('change', () => setOpen(false));
})();

import('/assets/motion/motion.js');
