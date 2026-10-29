const { test, expect } = require('@playwright/test');
const gallery = require('../../data/gallery.json');

const placeCount = gallery.places.length;
const roomCount = gallery.places.filter(place => place.type === 'room').length;
const seriesCount = gallery.series.length;

test('Gallery filters, empty state, reset, series, and place details work at desktop and mobile sizes', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/gallery/');
  await expect(page.getByRole('heading', { name: 'Find a place for what’s next.' })).toBeVisible();
  await expect(page.locator('[data-gallery-card]')).toHaveCount(placeCount);
  await expect(page.locator('[data-gallery-card]:visible')).toHaveCount(placeCount);
  expect((await page.locator('[data-gallery-card] img').first().boundingBox()).y).toBeLessThan(700);
  await expect(page.getByRole('button', { name: 'Series' })).toBeVisible();
  await expect(page.locator('.gallery-series-card')).toHaveCount(seriesCount);

  await page.getByRole('button', { name: 'Rooms' }).click();
  await expect(page.locator('[data-gallery-card]:visible')).toHaveCount(roomCount);
  await page.getByRole('button', { name: 'With sound' }).click();
  await expect(page.locator('[data-gallery-card]:visible')).toHaveCount(await page.locator('[data-gallery-card][data-type="room"][data-sound="true"]').count());

  const search = page.locator('[data-gallery-search]');
  await search.fill('does not exist in Locus');
  await expect(page.getByRole('heading', { name: 'No places match these filters.' })).toBeVisible();
  await page.getByRole('button', { name: 'Reset filters' }).last().click();
  await expect(search).toHaveValue('');
  await expect(page.locator('[data-gallery-card]:visible')).toHaveCount(placeCount);

  await page.getByRole('button', { name: 'Series' }).click();
  await page.locator('.gallery-series-card').first().click();
  await expect(page.getByRole('heading', { name: 'Places in this series' })).toBeVisible();

  await page.goto('/gallery/place/black-hole-ring/');
  await expect(page.getByRole('heading', { name: 'Event Horizon: Ring' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Credits' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Get Locus on the App Store' })).toHaveAttribute('href', 'https://apps.apple.com/app/id6802168265');

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/gallery/');
  await expect(page.locator('.gallery-filters')).toBeVisible();
  await expect(page.locator('[data-gallery-card]').first()).toBeVisible();
  expect((await page.locator('[data-gallery-card] img').first().boundingBox()).y).toBeLessThan(700);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});
