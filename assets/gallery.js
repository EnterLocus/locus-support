(() => {
  const app = document.querySelector('[data-gallery]');
  if (!app) return;
  const cards = [...app.querySelectorAll('[data-gallery-card]')];
  const placeSection = app.querySelector('[data-gallery-places]');
  const seriesSection = app.querySelector('[data-gallery-series]');
  const search = app.querySelector('[data-gallery-search]');
  const status = app.querySelector('[data-gallery-status]');
  const empty = app.querySelector('[data-gallery-empty]');
  const resetters = [...app.querySelectorAll('[data-gallery-reset]')];
  const buttons = [...app.querySelectorAll('[data-gallery-filter]')];
  const modeButtons = [...app.querySelectorAll('[data-gallery-mode]')];
  const groups = new Map();
  const active = { mode: 'places', type: 'all', access: 'all', animated: false, sound: false };

  for (const button of buttons) {
    const group = button.dataset.galleryFilter;
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(button);
    button.addEventListener('click', () => {
      const value = button.dataset.value;
      if (group === 'animated' || group === 'sound') active[group] = !active[group];
      else active[group] = value;
      render();
    });
  }
  for (const button of modeButtons) {
    button.addEventListener('click', () => {
      active.mode = button.dataset.galleryMode;
      if (active.mode === 'places') active.type = button.dataset.value;
      render();
    });
  }
  search?.addEventListener('input', render);
  resetters.forEach(button => button.addEventListener('click', reset));

  function reset() {
    active.mode = 'places'; active.type = 'all'; active.access = 'all'; active.animated = false; active.sound = false;
    if (search) search.value = '';
    render(); search?.focus();
  }

  function matches(card) {
    const query = (search?.value || '').trim().toLocaleLowerCase();
    if (query && !card.dataset.search.includes(query)) return false;
    if (active.type !== 'all' && card.dataset.type !== active.type) return false;
    if (active.access !== 'all' && card.dataset.access !== active.access) return false;
    if (active.animated && card.dataset.animated !== 'true') return false;
    return !(active.sound && card.dataset.sound !== 'true');
  }

  function render() {
    const showingSeries = active.mode === 'series';
    let visible = 0;
    cards.forEach(card => { const show = !showingSeries && matches(card); card.hidden = !show; if (show) visible += 1; });
    for (const [group, groupButtons] of groups) {
      for (const button of groupButtons) {
        const selected = group === 'animated' || group === 'sound'
          ? active[group] : active[group] === button.dataset.value;
        button.setAttribute('aria-pressed', String(selected));
      }
    }
    modeButtons.forEach(button => {
      const selected = button.dataset.galleryMode === active.mode &&
        (active.mode === 'series' || button.dataset.value === active.type);
      button.setAttribute('aria-pressed', String(selected));
    });
    app.querySelector('[data-gallery-filters]').hidden = showingSeries;
    placeSection.hidden = showingSeries;
    if (seriesSection) seriesSection.hidden = !showingSeries;
    empty.hidden = showingSeries || visible !== 0;
    status.textContent = status.dataset.galleryCount.replace('{count}', String(visible));
  }
  render();
})();
