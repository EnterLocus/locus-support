const { test, expect } = require('@playwright/test');
const gallery = require('../../data/gallery.json');

const placeCount = gallery.places.length;
const roomCount = gallery.places.filter(place => place.type === 'room').length;
const viewCount = gallery.places.filter(place => place.type === 'view').length;
const photoPlace = gallery.places.find(place => place.slug === 'black-hole-ring');

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

test('approved native photo captures support thumbnails, wrapping navigation, and focus-safe dialog close', async ({ page }) => {
  expect(photoPlace.photos.length).toBeGreaterThanOrEqual(3);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`/gallery/place/${photoPlace.slug}/`, { waitUntil: 'networkidle' });
  const open = page.locator('[data-gallery-photo-open]');
  const dialog = page.locator('[data-gallery-photo-dialog]');
  const counter = page.locator('[data-gallery-photo-counter]');
  await expect(page.locator('[data-gallery-photo-thumb]')).toHaveCount(photoPlace.photos.length);
  await expect(page.getByText('Rendered in Locus · Simulator')).toBeVisible();
  await expect(open).toHaveAttribute('aria-label', `Open photo 1 of ${photoPlace.photos.length}`);

  await open.click();
  await expect(dialog).toBeVisible();
  await expect(counter).toHaveText(`Photo 1 of ${photoPlace.photos.length}`);
  await page.keyboard.press('ArrowLeft');
  await expect(counter).toHaveText(`Photo ${photoPlace.photos.length} of ${photoPlace.photos.length}`);
  await expect(open).toHaveAttribute('aria-label', `Open photo ${photoPlace.photos.length} of ${photoPlace.photos.length}`);
  await page.keyboard.press('ArrowRight');
  await expect(counter).toHaveText(`Photo 1 of ${photoPlace.photos.length}`);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(open).toBeFocused();

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`/gallery/place/${photoPlace.slug}/`, { waitUntil: 'networkidle' });
  await page.locator('[data-gallery-photo-thumb]').nth(1).click();
  await expect(open).toHaveAttribute('aria-label', `Open photo 2 of ${photoPlace.photos.length}`);
  await open.click();
  await expect(dialog).toBeVisible();
  await page.locator('[data-gallery-photo-next]').click();
  await expect(counter).toHaveText(`Photo 3 of ${photoPlace.photos.length}`);
});
