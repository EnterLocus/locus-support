const { test, expect } = require('@playwright/test');

const releases = [
  ['/whats-new/1-4-0/', 'ZSZR2hGGOCk'],
  ['/whats-new/1-3-0/', 'bahHCqyB9M4'],
  ['/whats-new/1-2/', 'nO2B7MP0uzI'],
  ['/whats-new/1-1-5/', 'RPbFXq5-KVE'],
  ['/whats-new/1-1-3/', 'XfSBNZlIKw4'],
  ['/whats-new/1-1/', '77sy7ONjdCU'],
  ['/whats-new/1-0/', 'zg7WsyTJT4Q'],
];

test('homepage offers an explicit film action without starting an embedded player', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await expect(page.getByRole('link', { name: 'Play Locus promotional video', exact: true })).toHaveAttribute('href', 'https://www.youtube.com/watch?v=NJuKWTs2BRw');
  await expect(page.locator('iframe')).toHaveCount(0);
});

test('mobile release films autoplay muted when scrolled into view and fit the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.route('https://www.youtube-nocookie.com/**', route => route.abort());
  for (const [url, id] of releases) {
    await page.goto(url);
    const video = page.locator('.youtube-video');
    await video.scrollIntoViewIfNeeded();
    await expect(video.locator('iframe')).toHaveAttribute('src', `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=1&playsinline=1&rel=0&loop=1&playlist=${id}`);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    const size = await video.boundingBox();
    expect(size.width).toBeGreaterThanOrEqual(200);
    expect(size.height).toBeGreaterThanOrEqual(200);
  }
});

test('without visibility observation, release-film keyboard activation still loads a muted player', async ({ page }) => {
  await page.addInitScript(() => { delete window.IntersectionObserver; });
  await page.route('https://www.youtube-nocookie.com/**', route => route.abort());
  await page.goto('/whats-new/1-4-0/');
  await expect(page.locator('.youtube-video iframe')).toHaveCount(0);
  const play = page.locator('a[data-youtube-id="ZSZR2hGGOCk"]');
  await play.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.youtube-video iframe')).toHaveAttribute('src', /autoplay=1&mute=1/);
});

test('without JavaScript, posters remain direct YouTube links', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4186/');
  await expect(page.getByRole('link', { name: 'Play Locus promotional video', exact: true })).toHaveAttribute('href', 'https://www.youtube.com/watch?v=NJuKWTs2BRw');
  await expect(page.locator('iframe')).toHaveCount(0);
  await context.close();
});

test('homepage download and film actions stay inside small phone viewports', async ({ page }) => {
  for (const width of [320, 360, 375, 390]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto('/');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `no sideways scroll at ${width}px`).toBeTruthy();
    for (const selector of ['.hero .app-store-link', '.hero .film-link']) {
      const action = page.locator(selector);
      await expect(action).toBeInViewport();
      const bounds = await action.boundingBox();
      expect(bounds.x).toBeGreaterThanOrEqual(0);
      expect(bounds.x + bounds.width).toBeLessThanOrEqual(width);
    }
  }
});
