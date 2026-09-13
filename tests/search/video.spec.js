const { test, expect } = require('@playwright/test');

const releases = [
  ['/whats-new/1-1-3/', 'XfSBNZlIKw4'],
  ['/whats-new/1-1/', '77sy7ONjdCU'],
  ['/whats-new/1-0/', 'zg7WsyTJT4Q'],
];

test('videos connect only after activation, support keyboard and retain fallback links', async ({ page }) => {
  const youtubeRequests = [];
  page.on('request', request => {
    if (/youtube|ytimg|googlevideo/.test(request.url())) youtubeRequests.push(request.url());
  });
  // Simulate the external provider being blocked, without replacing site behavior.
  await page.route('https://www.youtube-nocookie.com/**', route => route.abort());
  await page.goto('/');
  await expect(page.locator('.youtube-video iframe')).toHaveCount(0);
  expect(youtubeRequests).toEqual([]);
  const play = page.getByRole('link', { name: 'Play Locus promotional video', exact: true });
  await play.focus();
  await page.keyboard.press('Enter');
  const iframe = page.locator('.youtube-video iframe');
  await expect(iframe).toHaveCount(1);
  await expect(iframe).toHaveAttribute('src', /youtube-nocookie.com\/embed\/q7mVdPEqJ2o\?/);
  await expect(iframe).toHaveAttribute('title', 'Locus promotional video');
  await expect(page.getByRole('link', { name: 'Watch on YouTube', exact: true }).first()).toHaveAttribute('href', 'https://www.youtube.com/watch?v=q7mVdPEqJ2o');
  await expect(page.getByRole('link', { name: 'Play Locus 1.1.3 promotional video', exact: true })).toBeVisible();
});

test('mobile posters and release films stay within the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await page.screenshot({ path: '.scratch/youtube-mobile-home.png', fullPage: false });
  const hero = page.locator('.hero-video-card');
  await hero.scrollIntoViewIfNeeded();
  await page.screenshot({ path: '.scratch/youtube-mobile-player.png' });
  for (const [url, id] of releases) {
    await page.goto(url);
    const play = page.locator('.youtube-video-cover');
    await expect(play).toHaveAttribute('href', `https://www.youtube.com/watch?v=${id}`);
    await expect(page.locator('.youtube-video iframe')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    const size = await play.boundingBox();
    expect(size.width).toBeGreaterThanOrEqual(200);
    expect(size.height).toBeGreaterThanOrEqual(200);
  }
  await page.screenshot({ path: '.scratch/youtube-mobile-release.png' });
});

test('without JavaScript, posters remain direct YouTube links', async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto('http://127.0.0.1:4186/');
  await expect(page.getByRole('link', { name: 'Play Locus promotional video', exact: true })).toHaveAttribute('href', 'https://www.youtube.com/watch?v=q7mVdPEqJ2o');
  await expect(page.locator('iframe')).toHaveCount(0);
  await context.close();
});
