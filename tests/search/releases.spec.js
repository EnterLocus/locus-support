const { test, expect } = require('@playwright/test');

// Exercise release links without smooth scrolling racing locator stability.
test.use({ reducedMotion: 'reduce' });
test.beforeEach(async ({ page }) => {
  // Navigation assertions do not depend on the external player responding.
  await page.route('https://www.youtube-nocookie.com/**', route => route.abort());
});

for (const width of [1440, 390, 320]) {
  test(`1.4.1 entry and release navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    // Release navigation should not wait for the third-party video player.
    await page.goto('/#whats-new', { waitUntil: 'domcontentloaded' });
    const entry = page.locator('.whats-new-latest');
    await expect(entry).toContainText('New in Locus 1.4.1');
    await expect(page.locator('#whats-new-title')).toHaveText('Move your desk to outer space.');
    await expect(page.locator('#whats-new [data-youtube-id="ZSZR2hGGOCk"], #whats-new iframe[src*="/embed/ZSZR2hGGOCk?"]')).toHaveCount(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await entry.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `.scratch/release-home-${width}.png` });
    await entry.focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/whats-new\/1-4-1\/$/);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Choose the music for your Room.');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({ path: `.scratch/release-article-${width}.png`, fullPage: true });
    await page.locator('.release-pagination a[href="../1-4-0/"]').click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Move your desk to outer space.');
    await page.locator('.release-pagination a[href="../1-4-1/"]').click();
    await expect(page).toHaveURL(/\/whats-new\/1-4-1\/$/);
    await page.locator('.release-back').click();
    await expect(page.locator('.release-card').first()).toHaveAttribute('href', './1-4-1/');
    await page.screenshot({ path: `.scratch/release-archive-${width}.png` });
    await page.locator('.release-card').first().click();
    await expect(page).toHaveURL(/\/whats-new\/1-4-1\/$/);
  });
}

for (const locale of ['zh-Hans', 'zh-Hant', 'ja', 'ko', 'de', 'fr', 'es']) {
  test(`localized 1.4.1 entry stays in ${locale} on mobile`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/${locale}/`, { waitUntil: 'domcontentloaded' });
    const entry = page.locator('.whats-new-latest');
    await expect(entry).not.toContainText('Global music');
    await entry.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({ path: `.scratch/release-home-${locale}.png` });
    await entry.click();
    await expect(page).toHaveURL(new RegExp(`/${locale}/whats-new/1-4-1/$`));
    await expect(page.getByRole('heading', { level: 1 })).not.toHaveText('Choose the music for your Room.');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({ path: `.scratch/release-article-${locale}.png`, fullPage: true });
    await page.locator('.release-pagination a').first().click();
    await expect(page).toHaveURL(new RegExp(`/${locale}/whats-new/1-4-0/$`));
  });
}
