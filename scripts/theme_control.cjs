const assert = require('node:assert/strict');

// Exercise the same menu interaction used by clients, including narrow screens.
async function setTheme(page, theme) {
  if (await page.locator('html').getAttribute('data-theme') === theme) return;
  const collapsed = await page.locator('body').evaluate(e => e.classList.contains('ks-collapsed'));
  if (collapsed) {
    const mobile = page.locator('.ks-mobile-toggle');
    await (await mobile.isVisible() ? mobile : page.locator('.ks-toggle')).click();
  }
  const settings = page.locator('.kt-settings');
  if (await settings.getAttribute('open') === null) await settings.locator('summary').click();
  const toggle = page.getByRole('switch', { name: 'Tema escuro' });
  await toggle.click();
  assert.equal(await toggle.getAttribute('aria-checked'), String(theme === 'dark'));
  assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
  await settings.locator('summary').click();
  if (page.viewportSize().width <= 640 && await page.locator('.ks-mobile-toggle').isVisible()) {
    await page.locator('.ks-toggle').click();
  }
}
module.exports = { setTheme };
