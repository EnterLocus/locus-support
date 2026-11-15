(() => {
  const app = document.querySelector('[data-gallery]');
  if (app) {
    const cards = [...app.querySelectorAll('[data-gallery-card]')];
    const seriesCards = [...app.querySelectorAll('[data-gallery-series-card]')];
    const grid = app.querySelector('.gallery-grid');
    const foldedOrder = [...grid.children];
    const recentOrder = [...cards].sort((a, b) =>
      Number(a.dataset.galleryRecentOrder) - Number(b.dataset.galleryRecentOrder));
    let previousNarrowed;
    const search = app.querySelector('[data-gallery-search]');
    const status = app.querySelector('[data-gallery-status]');
    const empty = app.querySelector('[data-gallery-empty]');
    const resetters = [...app.querySelectorAll('[data-gallery-reset]')];
    const buttons = [...app.querySelectorAll('[data-gallery-filter]')];
    const modeButtons = [...app.querySelectorAll('[data-gallery-mode]')];
    const extras = [...app.querySelectorAll('[data-gallery-example-extra]')];
    const moreExamples = app.querySelector('[data-gallery-more-examples]');
    const placesSection = app.querySelector('[data-gallery-places]');
    const toggles = new Set(['animated', 'sound', 'example']);
    const groups = new Map();
    const active = { type: 'all', access: 'all', animated: false, sound: false, example: false };

    for (const button of buttons) {
      const group = button.dataset.galleryFilter;
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(button);
      button.addEventListener('click', () => {
        const value = button.dataset.value;
        active[group] = toggles.has(group) ? !active[group] : value;
        if (group === 'example') syncExampleURL();
        render();
      });
    }
    for (const button of modeButtons) {
      button.addEventListener('click', () => { active.type = button.dataset.value; render(); });
    }
    search?.addEventListener('input', render);
    resetters.forEach(button => button.addEventListener('click', reset));
    // `?examples` opens the Gallery with only downloadable examples shown.
    if (groups.has('example') && new URLSearchParams(location.search).has('examples')) active.example = true;

    function syncExampleURL() {
      const params = new URLSearchParams(location.search);
      if (active.example) params.set('examples', ''); else params.delete('examples');
      const query = params.toString().replace(/(^|&)examples=(?=&|$)/, '$1examples');
      history.replaceState(history.state, '', location.pathname + (query ? `?${query}` : '') + location.hash);
    }

    function reset() {
      const hadExample = active.example;
      active.type = 'all'; active.access = 'all'; active.animated = false; active.sound = false; active.example = false;
      if (search) search.value = '';
      if (hadExample) syncExampleURL();
      render(); search?.focus();
    }

    function matches(card) {
      const query = (search?.value || '').trim().toLocaleLowerCase();
      if (query && !card.dataset.search.includes(query)) return false;
      if (active.type !== 'all' && card.dataset.type !== active.type) return false;
      if (active.access !== 'all' && card.dataset.access !== active.access) return false;
      if (active.animated && card.dataset.animated !== 'true') return false;
      if (active.example && card.dataset.example !== 'true') return false;
      return !(active.sound && card.dataset.sound !== 'true');
    }

    function render() {
      const narrowed = Boolean((search?.value || '').trim()) || active.access !== 'all' || active.animated || active.sound || active.example;
      if (narrowed !== previousNarrowed) {
        // Move the actual nodes so visual order and keyboard order agree.
        grid.replaceChildren(...(narrowed ? [...recentOrder, ...seriesCards] : foldedOrder));
        previousNarrowed = narrowed;
      }
      let visible = 0;
      cards.forEach(card => {
        const show = matches(card);
        card.hidden = narrowed ? !show : Boolean(card.dataset.seriesMember) || !show;
        if (show) visible += 1;
      });
      let extrasVisible = 0;
      extras.forEach(card => {
        const show = active.example && matches(card);
        card.hidden = !show;
        if (show) extrasVisible += 1;
      });
      if (moreExamples) moreExamples.hidden = extrasVisible === 0;
      seriesCards.forEach(card => {
        card.hidden = narrowed || (active.type !== 'all' && card.dataset.type !== active.type);
      });
      for (const [group, groupButtons] of groups) {
        groupButtons.forEach(button => {
          const selected = toggles.has(group) ? active[group] : active[group] === button.dataset.value;
          button.setAttribute('aria-pressed', String(selected));
        });
      }
      modeButtons.forEach(button => button.setAttribute('aria-pressed', String(active.type === button.dataset.value)));
      empty.hidden = visible !== 0 || extrasVisible !== 0;
      // Only off-Gallery examples match: show them without an empty Places grid above.
      placesSection.hidden = visible === 0 && extrasVisible !== 0;
      status.textContent = status.dataset.galleryCount.replace('{count}', String(visible));
    }
    render();
  }

  const back = document.querySelector('[data-gallery-back]');
  if (back) {
    const source = new URLSearchParams(location.search).get('series');
    // Only this Place's generated memberships can change the return target.
    const target = JSON.parse(back.dataset.galleryReturnOptions || '[]')
      .find(item => item.id === source);
    if (target) {
      back.href = target.url;
      back.textContent = `← ${target.label}`;
    }
  }

  document.querySelectorAll('[data-gallery-photos]').forEach(gallery => {
    const photos = JSON.parse(gallery.dataset.photos || '[]');
    const dialog = gallery.querySelector('[data-gallery-photo-dialog]');
    if (!photos.length || !dialog) return;
    const main = gallery.querySelector('.gallery-detail-image');
    const dialogImage = gallery.querySelector('[data-gallery-photo-dialog-image]');
    const counter = gallery.querySelector('[data-gallery-photo-counter]');
    const caption = gallery.querySelector('[data-gallery-photo-caption]');
    const dialogCaption = gallery.querySelector('[data-gallery-photo-dialog-caption]');
    const thumbs = [...gallery.querySelectorAll('[data-gallery-photo-thumb]')];
    const open = gallery.querySelector('[data-gallery-photo-open]');
    let index = 0;
    const format = (template, current) => template.replace('{current}', String(current + 1)).replace('{total}', String(photos.length));
    const counterTemplate = counter?.dataset.template || 'Photo {current} of {total}';
    const openTemplate = open?.dataset.template || 'Open photo {current} of {total}';

    function setPhoto(next) {
      index = (next + photos.length) % photos.length;
      const photo = photos[index];
      [main, dialogImage].filter(Boolean).forEach(image => {
        image.src = photo.url; image.width = photo.width; image.height = photo.height;
        image.alt = `${gallery.closest('.gallery-detail')?.querySelector('h1')?.textContent || ''} — ${photo.caption}`;
      });
      open?.setAttribute('aria-label', format(openTemplate, index));
      if (counter) counter.textContent = format(counterTemplate, index);
      if (caption) caption.textContent = photo.caption;
      if (dialogCaption) dialogCaption.textContent = photo.caption;
      thumbs.forEach((thumb, thumbIndex) => thumb.setAttribute('aria-current', String(thumbIndex === index)));
    }
    open?.addEventListener('click', () => dialog.showModal());
    gallery.querySelector('[data-gallery-photo-close]')?.addEventListener('click', () => dialog.close());
    gallery.querySelector('[data-gallery-photo-previous]')?.addEventListener('click', () => setPhoto(index - 1));
    gallery.querySelector('[data-gallery-photo-next]')?.addEventListener('click', () => setPhoto(index + 1));
    thumbs.forEach((thumb, thumbIndex) => thumb.addEventListener('click', () => setPhoto(thumbIndex)));
    dialog.addEventListener('keydown', event => {
      if (event.key === 'ArrowLeft') { event.preventDefault(); setPhoto(index - 1); }
      if (event.key === 'ArrowRight') { event.preventDefault(); setPhoto(index + 1); }
    });
    setPhoto(0);
  });
})();
