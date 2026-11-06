const { test, expect } = require('@playwright/test');

for (const viewport of [{ width: 390, height: 844 }, { width: 1280, height: 900 }]) {
  test(`Room example fits a ${viewport.width}px viewport`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto('/gothic-mountain-library/');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    // Long SHA-256 digests and model entity names must wrap rather than make
    // the entire article wider than a phone viewport.
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
    await expect(page.locator('main img')).toHaveCount(3);
    expect(await page.locator('main img').evaluateAll(images => images.every(img => img.complete && img.naturalWidth > 0))).toBe(true);
    await page.screenshot({ path: `.scratch/room-example-${viewport.width}-full.png`, fullPage: true });
    await page.screenshot({ path: `.scratch/room-example-${viewport.width}.png` });
  });
}
