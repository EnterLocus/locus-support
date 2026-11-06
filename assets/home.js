// Keep the scenery switch manual; labels and alternatives are localized at build time.
const places = {
  day: { image: 'promo/still-02-seat-v120.jpg', slug: 'sunlit-cafe' },
  night: { image: 'screenshots/milky-way-winter-garden-v120.jpg', slug: 'winter-garden-breeze' },
  space: { image: 'screenshots/saturn-winter-garden-v120.jpg', slug: 'winter-garden-breeze' },
};
const tabs = [...document.querySelectorAll('[data-place][role="tab"]')];
const picture = document.querySelector('#place-image');
const placeLink = document.querySelector('#place-link');
const panel = document.querySelector('#place-panel');
function selectPlace(tab) {
  const place = places[tab.dataset.place];
  picture.alt = tab.dataset.imageAlt;
  placeLink.setAttribute('aria-label', tab.dataset.imageLabel);
  for (const item of tabs) {
    item.setAttribute('aria-selected', String(item === tab));
    item.tabIndex = item === tab ? 0 : -1;
  }
  picture.src = '/assets/' + place.image;
  const language = document.documentElement.lang;
  const prefix = language === 'en' ? '' : '/' + language;
  placeLink.href = `${prefix}/gallery/place/${place.slug}/`;
  panel.setAttribute('aria-labelledby', tab.id);
}
for (const [index, tab] of tabs.entries()) {
  tab.addEventListener('click', () => selectPlace(tab));
  tab.addEventListener('keydown', event => {
    const next = {
      ArrowRight: (index + 1) % tabs.length,
      ArrowLeft: (index + tabs.length - 1) % tabs.length,
      Home: 0,
      End: tabs.length - 1,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    selectPlace(tabs[next]);
    tabs[next].focus();
  });
}
for (const place of Object.values(places)) {
  const image = new Image();
  image.src = '/assets/' + place.image;
}
