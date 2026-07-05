const { chromium } = require('playwright');
const OUT = __dirname + '/public';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  await page.goto('file://' + __dirname + '/../accountant_report.html', { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/08_accountant.png` });

  await page.click('#next-btn');
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/09_accountant_page2.png` });

  await browser.close();
  console.log('Accountant screenshots captured');
})();
