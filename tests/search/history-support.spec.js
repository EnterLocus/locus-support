const { test, expect } = require('@playwright/test');

for (const width of [1440, 390, 320]) {
  test(`historical release sequence and support links at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/whats-new/');
    await expect(page.locator('.release-card').first()).toHaveAttribute('href', './1-4-4/');
    await page.locator('.release-card[href="./1-3-0/"]').click();
    await page.locator('.release-pagination a[href="../1-3-1/"]').click();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Smoother Places, clearer Real Objects.');
    await expect(page.locator('.status')).toHaveText('Release archive');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    await page.locator('.release-pagination a[href="../1-4-0/"]').click();
    await page.locator('.release-pagination a[href="../1-3-1/"]').click();
    await expect(page).toHaveURL(/\/whats-new\/1-3-1\/$/);
    for (const anchor of ['website-sign-in-after-update', 'library-downloads-when-headset-is-off']) {
      await page.goto(`/faq/#${anchor}`);
      await expect(page.locator(`details:has(#${anchor})`)).toHaveAttribute('open', '');
      await expect(page.locator(`#${anchor}`)).toBeInViewport();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    }
  });
}

for (const locale of ['zh-Hans', 'zh-Hant', 'ja', 'ko', 'de', 'fr', 'es']) {
  test(`history and new support answers stay localized in ${locale}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(`/${locale}/whats-new/1-3-0/`);
    await page.locator(`.release-pagination a[href="/${locale}/whats-new/1-3-1/"]`).click();
    await expect(page.getByRole('heading', { level: 1 })).not.toHaveText('Smoother Places, clearer Real Objects.');
    await expect(page.locator('.status')).not.toHaveText('Release archive');
    await page.locator(`.release-pagination a[href="/${locale}/whats-new/1-4-0/"]`).click();
    await expect(page).toHaveURL(new RegExp(`/${locale}/whats-new/1-4-0/$`));
    for (const anchor of ['website-sign-in-after-update', 'library-downloads-when-headset-is-off']) {
      await page.goto(`/${locale}/faq/#${anchor}`);
      const answer = page.locator(`details:has(#${anchor})`);
      await expect(answer).toHaveAttribute('open', '');
      await expect(answer).not.toContainText('Locus attempts a retry');
      await expect(answer).not.toContainText('This one-time migration');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    }
  });
}

test('new download answer is discoverable through the real search index', async ({ page }) => {
  await page.goto('/support/');
  await page.getByRole('button', { name: 'Search', exact: true }).click();
  await page.getByRole('searchbox').fill('headset downloads');
  const answer = page.locator('.search-results a[href="/faq/#library-downloads-when-headset-is-off"]');
  await expect(answer).toBeVisible();
  await answer.click();
  await expect(page.locator('details:has(#library-downloads-when-headset-is-off)')).toHaveAttribute('open', '');
});
