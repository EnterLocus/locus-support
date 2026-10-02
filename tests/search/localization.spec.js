const { test, expect } = require('@playwright/test');

test('System follows the first preferred navigator language and an explicit locale URL wins', async ({ browser }) => {
  const context = await browser.newContext();
  await context.addInitScript(() => Object.defineProperty(navigator, 'languages', { value: ['de-DE'] }));
  const page = await context.newPage();
  await page.goto('/');
  await expect(page).toHaveURL(/\/de\/$/);
  await expect(page.locator('[data-language-select]')).toHaveValue('system');
  await page.evaluate(() => localStorage.setItem('locus-language', 'en'));
  await page.goto('/fr/faq/#lying-down');
  await expect(page).toHaveURL(/\/fr\/faq\/#lying-down$/);
  await expect(page.locator('[data-language-select]')).toHaveValue('fr');
  await context.close();
});

test('English persists, unsupported System remains English, and denied storage leaves the selector usable', async ({ browser }) => {
  const context = await browser.newContext();
  await context.addInitScript(() => Object.defineProperty(navigator, 'languages', { value: ['pt-BR'] }));
  const page = await context.newPage();
  await page.goto('/');
  await expect(page).toHaveURL(/^https?:\/\/[^/]+\/$/);
  await page.locator('[data-language-select]').selectOption('fr');
  await expect(page).toHaveURL(/\/fr\/$/);
  await page.locator('[data-language-select]').selectOption('en');
  await expect(page).toHaveURL(/^https?:\/\/[^/]+\/$/);
  await page.reload();
  await expect(page.locator('[data-language-select]')).toHaveValue('en');
  await context.close();

  const blocked = await browser.newContext();
  await blocked.addInitScript(() => {
    Object.defineProperty(window, 'localStorage', { get() { throw new DOMException('Denied', 'SecurityError'); } });
  });
  const blockedPage = await blocked.newPage();
  await blockedPage.goto('/');
  await blockedPage.locator('[data-language-select]').selectOption('ja');
  await expect(blockedPage).toHaveURL(/\/ja\/$/);
  await blocked.close();
});

test('localized search stays in the current Pagefind language and fallback FAQ preserves locale', async ({ page }) => {
  await page.goto('/fr/faq/');
  await page.locator('.search-trigger').click();
  await page.getByRole('searchbox').fill('Locus');
  await expect(page.locator('.search-results a[href^="/fr/"]')).not.toHaveCount(0);
  await page.route('**/pagefind/**', route => route.abort());
  await page.reload();
  await page.locator('.search-trigger').click();
  await page.getByRole('searchbox').fill('desk');
  await expect(page.locator('.search-results a')).toHaveAttribute('href', '/fr/faq/');
});


test('Chinese script overrides region and unsupported prefixes do not select a different language', async ({ browser }) => {
  for (const [language, path] of [['zh-Hans-TW', '/zh-Hans/'], ['zh-Hant-CN', '/zh-Hant/'], ['zh-HK', '/zh-Hant/'], ['frr-DE', '/']]) {
    const context = await browser.newContext();
    await context.addInitScript(language => Object.defineProperty(navigator, 'languages', { value: [language, 'de-DE'] }), language);
    const page = await context.newPage();
    await page.goto('/');
    await expect(page).toHaveURL(new RegExp(path.replaceAll('/', '\\/') + '$'));
    await expect(page.locator('[data-language-select]')).toHaveValue('system');
    await context.close();
  }
});


test('translated controls and language switching preserve the FAQ anchor on narrow screens', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/zh-Hans/faq/#lying-down');
  await expect(page.locator('#lying-down')).toBeInViewport();
  await page.getByRole('button', { name: '搜索', exact: true }).click();
  await page.getByRole('searchbox').fill('房间');
  await expect(page.locator('.search-results a[href^="/zh-Hans/"]')).not.toHaveCount(0);
  await page.getByRole('button', { name: '关闭搜索', exact: true }).click();
  await page.locator('[data-language-select]').selectOption('de');
  await expect(page).toHaveURL(/\/de\/faq\/#lying-down$/);
  await expect(page.locator('#lying-down')).toBeInViewport();
  await expect(page.locator('[data-language-select]')).toHaveValue('de');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});
