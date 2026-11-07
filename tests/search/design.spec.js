const { test, expect } = require('@playwright/test');

test('homepage keeps the official download badge and switches real Places with keyboard support', async ({ page }) => {
  await page.goto('/');
  const badge = page.locator('.hero .app-store-link');
  await expect(badge).toHaveAttribute('href', 'https://apps.apple.com/app/id6802168265');
  await expect(badge.locator('img')).toHaveAttribute('src', './assets/download-on-the-app-store.svg');
  const image = page.locator('#place-image');
  await page.getByRole('tab', { name: 'After dark', exact: true }).click();
  await expect(image).toHaveAttribute('src', '/assets/screenshots/milky-way-winter-garden-v120.jpg');
  await expect(page.locator('#place-panel')).toHaveAttribute('aria-labelledby', 'night-tab');
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#space-tab')).toBeFocused();
  await expect(image).toHaveAttribute('src', '/assets/screenshots/saturn-winter-garden-v120.jpg');
  await page.screenshot({ path: '.scratch/design/places-space.png' });
  await page.keyboard.press('Home');
  await expect(page.locator('#day-tab')).toHaveAttribute('aria-selected', 'true');
  await expect(image).toHaveAttribute('src', '/assets/promo/still-02-seat-v120.jpg');
});

test('mobile navigation retains search, keyboard dismissal and language selection', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Search', exact: true })).toBeVisible();
  const toggle = page.getByRole('button', { name: 'Open menu', exact: true });
  await toggle.click();
  await expect(page.locator('[data-language-select]')).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('link').first()).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(toggle).toBeFocused();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await toggle.click();
  await page.screenshot({ path: '.scratch/design/mobile-menu.png' });
  await page.locator('[data-language-select]').selectOption('zh-Hans');
  await expect(page).toHaveURL(/\/zh-Hans\/$/);
  await expect(page.locator('html')).toHaveAttribute('lang', 'zh-Hans');
  await page.getByRole('tab').nth(1).click();
  await expect(page.locator('#place-link')).toHaveAttribute('href', '/zh-Hans/gallery/place/winter-garden-breeze/');
  await expect(page.locator('#place-image')).not.toHaveAttribute('alt', 'Winter Garden beneath the Milky Way, with snowy mountains beyond the windows');
});

test('page families use the shared responsive shell without horizontal overflow', async ({ page }) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 900 });
    for (const path of ['/', '/gallery/', '/tutorials/', '/first-place/', '/faq/', '/whats-new/1-4-6/', '/support/', '/privacy/', '/reference/locusplace-format/']) {
      await page.goto(path);
      await expect(page.locator('.site-header .brand')).toBeVisible();
      await expect(page.locator('.search-trigger')).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
      if (width === 390) {
        await page.getByRole('button', { name: 'Open menu', exact: true }).click();
      }
      await expect(page.getByRole('navigation', { name: 'Primary navigation' }).getByRole('link', { name: 'Gallery', exact: true })).toBeVisible();
      await expect(page.locator('[data-language-select]')).toBeVisible();
      if (width === 390) await page.keyboard.press('Escape');
      await page.screenshot({ path: `.scratch/design/${width}-${path.replaceAll('/', '_') || 'home'}.png` });
    }
  }
});

test('localized homepages keep their actions in the first screen', async ({ page }) => {
  for (const [locale, width, height] of [['de', 1440, 900], ['zh-Hans', 390, 844], ['ja', 390, 844], ['ko', 390, 844]]) {
    await page.setViewportSize({ width, height });
    await page.goto(`/${locale}/`);
    await expect(page.locator('.hero .app-store-link')).toBeInViewport();
    await expect(page.locator('html')).toHaveAttribute('lang', locale);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.screenshot({ path: `.scratch/design/home-${locale}.png` });
  }
});

test('long document titles and asset filenames stay readable on narrow phones', async ({ page }) => {
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    for (const locale of ['', 'zh-Hans', 'zh-Hant', 'ja', 'ko', 'de', 'fr', 'es']) {
      await page.goto(`${locale ? '/' + locale : ''}/asset-rights/`);
      await page.evaluate(() => document.fonts.ready);
      await expect(page.locator('#demo-room-notices')).toContainText('white_plaster_02_Diffuse_Subtle.jpg');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    }
    await page.goto('/de/privacy/');
    await page.evaluate(() => document.fonts.ready);
    await expect(page.locator('h1')).toHaveText('Locus Datenschutzerklärung');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  }
});
