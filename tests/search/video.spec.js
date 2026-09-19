const { test, expect } = require('@playwright/test');

const releases = [
  ['/whats-new/1-1-5/', 'RPbFXq5-KVE'],
  ['/whats-new/1-1-3/', 'XfSBNZlIKw4'],
  ['/whats-new/1-1/', '77sy7ONjdCU'],
  ['/whats-new/1-0/', 'zg7WsyTJT4Q'],
];

test('visible videos autoplay muted without stealing focus and retain blocked-provider fallback', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  // Simulate an unavailable external provider, while running the real site.
  await page.route('https://www.youtube-nocookie.com/**', route => route.abort());
  await page.goto('/');
  const card = page.locator('.hero-video-card');
  await card.scrollIntoViewIfNeeded();
  const iframe = card.locator('iframe');
  await expect(iframe).toHaveCount(1);
  await expect(iframe).toHaveAttribute('src', /embed\/bJln-6GMXlQ\?autoplay=1&mute=1&playsinline=1/);
  await expect(iframe).toHaveAttribute('title', 'Locus promotional video');
  await expect(iframe).not.toBeFocused();
  await expect(page.getByRole('link', { name: 'Watch on YouTube', exact: true }).first()).toHaveAttribute('href', 'https://www.youtube.com/watch?v=bJln-6GMXlQ');
  // The second film is still below the viewport and has not connected.
  await expect(page.getByRole('link', { name: 'Play the Locus 1.1.5 release film', exact: true })).toHaveCount(1);
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

test('without visibility observation, keyboard activation still loads a muted player', async ({ page }) => {
  await page.addInitScript(() => { delete window.IntersectionObserver; });
  await page.route('https://www.youtube-nocookie.com/**', route => route.abort());
  await page.goto('/');
  await expect(page.locator('.youtube-video iframe')).toHaveCount(0);
  const play = page.getByRole('link', { name: 'Play Locus promotional video', exact: true });
  await play.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('.hero-video-card iframe')).toHaveAttribute('src', /autoplay=1&mute=1/);
});

test('without JavaScript, posters remain direct YouTube links', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4186/');
  await expect(page.getByRole('link', { name: 'Play Locus promotional video', exact: true })).toHaveAttribute('href', 'https://www.youtube.com/watch?v=bJln-6GMXlQ');
  await expect(page.locator('iframe')).toHaveCount(0);
  await context.close();
});

test('the homepage hero film stays inside the page on small phones', async ({ page }) => {
  await page.route('https://www.youtube-nocookie.com/**', route => route.abort());
  // The 200px floor the player needs turns into a 356px minimum width through
  // the 16:9 ratio; the hero grid must not let that widen the page.
  for (const width of [320, 360, 375, 390]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto('/');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `no sideways scroll at ${width}px`).toBeTruthy();
    const main = await page.locator('main').boundingBox();
    const card = await page.locator('.hero-video-card').boundingBox();
    expect(card.x + card.width, `hero card ends with the page column at ${width}px`).toBeLessThanOrEqual(main.x + main.width + 0.5);
    const video = await page.locator('.hero-video-card .youtube-video').boundingBox();
    expect(video.width).toBeGreaterThanOrEqual(200);
    expect(video.height).toBeGreaterThanOrEqual(200);
  }
});
