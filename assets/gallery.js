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
    const groups = new Map();
    const active = { type: 'all', access: 'all', animated: false, sound: false };

    for (const button of buttons) {
      const group = button.dataset.galleryFilter;
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(button);
      button.addEventListener('click', () => {
        const value = button.dataset.value;
        active[group] = group === 'animated' || group === 'sound' ? !active[group] : value;
        render();
      });
    }
    for (const button of modeButtons) {
      button.addEventListener('click', () => { active.type = button.dataset.value; render(); });
    }
    search?.addEventListener('input', render);
    resetters.forEach(button => button.addEventListener('click', reset));

    function reset() {
      active.type = 'all'; active.access = 'all'; active.animated = false; active.sound = false;
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
      const narrowed = Boolean((search?.value || '').trim()) || active.access !== 'all' || active.animated || active.sound;
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
      seriesCards.forEach(card => {
        card.hidden = narrowed || (active.type !== 'all' && card.dataset.type !== active.type);
      });
      for (const [group, groupButtons] of groups) {
        groupButtons.forEach(button => {
          const selected = group === 'animated' || group === 'sound'
            ? active[group] : active[group] === button.dataset.value;
          button.setAttribute('aria-pressed', String(selected));
        });
      }
      modeButtons.forEach(button => button.setAttribute('aria-pressed', String(active.type === button.dataset.value)));
      empty.hidden = visible !== 0;
      status.textContent = status.dataset.galleryCount.replace('{count}', String(visible));
    }
    render();
  }

  document.querySelectorAll('[data-gallery-photos]').forEach(gallery => {
    const photos = JSON.parse(gallery.dataset.photos || '[]');
    const dialog = gallery.querySelector('[data-gallery-photo-dialog]');
    if (!photos.length || !dialog) return;
    const main = gallery.querySelector('.gallery-detail-image');
    const dialogImage = gallery.querySelector('[data-gallery-photo-dialog-image]');
    const counter = gallery.querySelector('[data-gallery-photo-counter]');
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
      });
      open?.setAttribute('aria-label', format(openTemplate, index));
      if (counter) counter.textContent = format(counterTemplate, index);
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
