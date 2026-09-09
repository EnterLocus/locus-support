const { test, expect } = require('@playwright/test');

test('searches FAQ answers and guides, opens answers, and supports keyboard dismissal', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  const search = page.getByRole('searchbox');
  await expect(search).toBeFocused();
  await page.screenshot({ path: '.scratch/search-default.png' });
  await search.fill('lying down');
  const answer = page.locator('.search-results a').filter({ hasText: 'Can I use Locus while lying down?' });
  await expect(answer).toHaveCount(1);
  await page.screenshot({ path: '.scratch/search-desktop.png' });
  await answer.click();
  await expect(page).toHaveURL(/\/faq\/#lying-down$/);
  await expect(page.locator('details').filter({ hasText: 'Can I use Locus while lying down?' })).toHaveAttribute('open', '');
  await expect(page.getByText('Available in Locus Dev TestFlight 1.1.2 (10) and later.')).toBeVisible();
  await page.screenshot({ path: '.scratch/faq-desktop.png' });
  await page.keyboard.press('Control+k');
  await search.fill('Original file');
  await expect(page.locator('.search-results a[href^="/online-views/"]').first()).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('dialog')).not.toBeVisible();
  await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeFocused();
});

test('mobile layout, no results, clearing and direct FAQ links', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/faq/#lying-down');
  await expect(page.locator('#lying-down')).toBeInViewport();
  await page.screenshot({ path: '.scratch/faq-mobile.png' });
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await page.getByRole('searchbox').fill('lying down');
  await expect(page.locator('.search-results a')).not.toHaveCount(0);
  await page.screenshot({ path: '.scratch/search-mobile.png' });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.getByRole('searchbox').fill('quasar pineapple');
  await expect(page.getByRole('status')).toHaveText('No results. Try another word, or browse the FAQ.');
  await page.screenshot({ path: '.scratch/search-empty-mobile.png' });
  await page.getByRole('searchbox').fill('');
  await expect(page.getByRole('status')).toHaveText('Find answers across FAQ and guides.');
  await expect(page.locator('.search-results a')).toHaveCount(0);
  await page.getByRole('button', { name: 'Close search' }).click();
});

test('unavailable index gives a usable fallback', async ({ page }) => {
  await page.route('**/pagefind/**', route => route.abort());
  await page.goto('/support/');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await page.getByRole('searchbox').fill('desk');
  await expect(page.getByRole('status')).toHaveText('Search is unavailable right now. Try again, or browse the FAQ.');
  await expect(page.getByRole('link', { name: 'Browse the FAQ', exact: true })).toHaveAttribute('href', '/faq/');
});
