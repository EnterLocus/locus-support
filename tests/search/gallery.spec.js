const { test, expect } = require('@playwright/test');
const gallery = require('../../data/gallery.json');

const placeCount = gallery.places.length;
const roomCount = gallery.places.filter(place => place.type === 'room').length;
const viewCount = gallery.places.filter(place => place.type === 'view').length;
const photoPlace = gallery.places.find(place => place.slug === 'black-hole-ring');
const displayAlbum = place => [place.image, ...(place.photos || []).filter(photo =>
  photo.url !== place.image.url && (!place.image.sha256 || photo.sha256 !== place.image.sha256)
)];

test('Gallery folds eligible Series, then unfolds matching Places for filters and search', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/gallery/');
  await expect(page.getByRole('heading', { name: 'Find a place for what’s next.' })).toBeVisible();
  await expect(page.locator('[data-gallery-card]')).toHaveCount(placeCount);
  await expect(page.locator('[data-gallery-series-card]')).toHaveCount(8);
  await expect(page.locator('[data-gallery-card][data-series-member]:visible')).toHaveCount(0);
  await expect(page.locator('[data-gallery-status]')).toHaveText(`${placeCount} places`);
  await expect(page.getByRole('button', { name: 'Series' })).toHaveCount(0);
  expect((await page.locator('.gallery-grid > :visible img').first().boundingBox()).y).toBeLessThan(700);

  await page.getByRole('button', { name: 'Views' }).click();
  await expect(page.locator('[data-gallery-series-card][data-type="view"]:visible')).toHaveCount(5);
  await expect(page.locator('[data-gallery-card][data-series-member]:visible')).toHaveCount(0);
  await expect(page.locator('[data-gallery-status]')).toHaveText(`${viewCount} places`);

  const search = page.locator('[data-gallery-search]');
  await search.fill('after dark');
  await expect(page.locator('[data-gallery-series-card]:visible')).toHaveCount(0);
  await expect(page.locator('[data-gallery-card]:visible')).toHaveCount(5);
  await expect(page.locator('[data-gallery-status]')).toHaveText('5 places');
  await search.fill('Bei Nacht');
  await expect(page.locator('[data-gallery-card]:visible')).toHaveCount(5);

  await page.getByRole('button', { name: 'Reset filters' }).last().click();
  await expect(search).toHaveValue('');
  await expect(page.locator('[data-gallery-series-card]:visible')).toHaveCount(8);
  await page.getByRole('button', { name: 'Rooms' }).click();
  await expect(page.locator('[data-gallery-status]')).toHaveText(`${roomCount} places`);
  await page.getByRole('button', { name: 'With sound' }).click();
  await expect(page.locator('[data-gallery-series-card]:visible')).toHaveCount(0);
  await expect(page.locator('[data-gallery-card]:visible')).toHaveCount(
    await page.locator('[data-gallery-card][data-type="room"][data-sound="true"]').count()
  );
  const recent = place => Math.max(...['addedAt', 'updatedAt'].map(key => Date.parse(place[key] || '') || 0));
  const expectedRooms = gallery.places.filter(place => place.type === 'room' && place.hasSound)
    .sort((a, b) => recent(b) - recent(a) || a.title.localeCompare(b.title))
    .map(place => place.slug);
  const visibleRooms = await page.locator('[data-gallery-card]:visible').evaluateAll(cards =>
    cards.map(card => ({ slug: card.querySelector('a').pathname.split('/').filter(Boolean).pop(),
                       top: card.getBoundingClientRect().top, left: card.getBoundingClientRect().left }))
      .sort((a, b) => a.top - b.top || a.left - b.left).map(card => card.slug));
  expect(visibleRooms).toEqual(expectedRooms);

  await page.goto('/gallery/place/black-hole-ring/');
  await expect(page.getByRole('heading', { name: 'Event Horizon: Ring' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Into Space' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Credits' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Get Locus on the App Store' })).toHaveAttribute('href', 'https://apps.apple.com/app/id6802168265');

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/gallery/');
  await expect(page.locator('.gallery-filters')).toBeVisible();
  expect((await page.locator('.gallery-grid > :visible img').first().boundingBox()).y).toBeLessThan(700);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});

test('cover-first albums retain native captures, switch captions, and close dialogs with focus restored', async ({ page }) => {
  expect(photoPlace.photos.length).toBeGreaterThanOrEqual(3);
  const album = displayAlbum(photoPlace);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/gallery/place/${photoPlace.slug}/`, { waitUntil: 'networkidle' });
  const open = page.locator('[data-gallery-photo-open]');
  const dialog = page.locator('[data-gallery-photo-dialog]');
  const counter = page.locator('[data-gallery-photo-counter]');
  const caption = page.locator('[data-gallery-photo-caption]');
  const dialogCaption = page.locator('[data-gallery-photo-dialog-caption]');
  await expect(page.locator('[data-gallery-photo-thumb]')).toHaveCount(album.length);
  await expect(caption).toHaveText('Cover image');
  await expect(open).toHaveAttribute('aria-label', `Open photo 1 of ${album.length}`);

  await open.click();
  await expect(dialog).toBeVisible();
  await expect(dialogCaption).toHaveText('Cover image');
  await expect(counter).toHaveText(`Photo 1 of ${album.length}`);
  await page.keyboard.press('ArrowLeft');
  await expect(counter).toHaveText(`Photo ${album.length} of ${album.length}`);
  await expect(caption).toHaveText('Rendered in Locus · Simulator');
  await expect(dialogCaption).toHaveText('Rendered in Locus · Simulator');
  await expect(open).toHaveAttribute('aria-label', `Open photo ${album.length} of ${album.length}`);
  await page.keyboard.press('ArrowRight');
  await expect(counter).toHaveText(`Photo 1 of ${album.length}`);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(open).toBeFocused();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/gallery/place/${photoPlace.slug}/`, { waitUntil: 'networkidle' });
  await page.locator('[data-gallery-photo-thumb]').nth(1).click();
  await expect(caption).toHaveText('Rendered in Locus · Simulator');
  await expect(open).toHaveAttribute('aria-label', `Open photo 2 of ${album.length}`);
  await open.click();
  await expect(dialog).toBeVisible();
  await page.locator('[data-gallery-photo-next]').click();
  await expect(counter).toHaveText(`Photo 3 of ${album.length}`);
});

test('catalog thumbnails cover cards while Series context survives photo browsing and reload', async ({ page }) => {
  const series = gallery.series.find(item => item.id === 'mansions');
  for (const locale of ['', '/zh-Hans']) {
    await page.setViewportSize({ width: locale ? 390 : 1440, height: locale ? 844 : 1000 });
    await page.goto(`${locale}/gallery/series/${series.id}/`);
    const card = page.locator('[data-gallery-card]').first();
    const href = await card.locator('a').getAttribute('href');
    expect(href).toContain('?series=mansions');
    const slug = new URL(href, 'http://localhost').pathname.split('/').filter(Boolean).pop();
    const place = gallery.places.find(item => item.slug === slug);
    await expect(card.locator('img')).toHaveAttribute('src', place.image.url);
    await card.locator('a').click();
    const back = page.locator('[data-gallery-back]');
    await expect(back).toHaveAttribute('href', `${locale}/gallery/series/mansions/`);
    await expect(page.locator('[data-gallery-photo-thumb]')).toHaveCount(displayAlbum(place).length);
    await page.locator('[data-gallery-photo-thumb]').nth(1).click();
    await page.locator('[data-gallery-photo-open]').click();
    await page.keyboard.press('Escape');
    await page.reload();
    await expect(back).toHaveAttribute('href', `${locale}/gallery/series/mansions/`);
    await back.click();
    await expect(page).toHaveURL(new RegExp(`${locale}/gallery/series/mansions/$`));
    for (const query of ['', '?series=after-dark', '?series=https://example.com']) {
      await page.goto(`${locale}/gallery/place/${place.slug}/${query}`);
      await expect(page.locator('[data-gallery-back]')).toHaveAttribute('href', `${locale}/gallery/`);
    }
  }
});

test('the two approved new Rooms explain availability and retain native albums', async ({ page }) => {
  const ids = ['space.japanese-courtyard-mansion', 'space.pacific-palapa-house'];
  const rooms = gallery.places.filter(place => ids.includes(place.id));
  expect(rooms).toHaveLength(ids.length);
  expect(gallery.places.filter(place => place.previewRelease).every(place => ids.includes(place.id))).toBe(true);
  for (const place of rooms) {
    await page.goto(`/zh-Hans/gallery/place/${place.slug}/`);
    if (place.previewRelease) {
      await expect(page.locator('.release-preview')).toHaveText(`Locus ${place.previewRelease} 预览`);
      await expect(page.getByText(`将在 Locus ${place.previewRelease} 上架后推出。`)).toBeVisible();
      await expect(page.locator('.gallery-cta')).toHaveCount(0);
    } else {
      await expect(page.locator('.release-preview')).toHaveCount(0);
      await expect(page.locator('.gallery-cta')).toBeVisible();
    }
    await expect(page.locator('[data-gallery-photo-thumb]')).toHaveCount(displayAlbum(place).length);
    expect(place.photos.length).toBeGreaterThanOrEqual(3);
  }
});
