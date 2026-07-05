// Captures real screenshots of The Pass running live - not mockups.
// Screen 1: real Xero UI (the actual bank transaction record)
// Screen 2: dashboard overview
// Screen 3: a warning module expanded
// Screen 4: the live agent mid-question and with a real answer
// Screen 5: the terminal after a real re-scan
// Screen 6: the drafted chase message
// Screen 7: the accountant report

const { chromium } = require('playwright');
const fs = require('fs');

const OUT = __dirname + '/public';

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  // 1. Dashboard overview (page 0)
  await page.goto('http://localhost:5050/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${OUT}/01_overview.png` });

  // 2. Jump to Recurring Suppliers module (page 2) via goToPage
  await page.evaluate(() => window.goToPage(2));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/02_module.png` });

  // 3. Go to the chat page (last page: 9 modules + overview = index 10), ask a real question
  await page.evaluate(() => window.goToPage(10));
  await page.waitForTimeout(300);
  await page.fill('#ask-input', 'did we get overcharged on card fees recently?');
  await page.screenshot({ path: `${OUT}/03_question_typed.png` });
  await page.click('#ask-btn');
  await page.waitForSelector('#ask-meta', { state: 'visible', timeout: 20000 });
  await page.waitForFunction(
    () => document.getElementById('ask-answer').textContent.length > 20,
    { timeout: 20000 }
  );
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/04_answer.png` });

  // 4. Real re-scan - back to overview page where the terminal lives
  await page.evaluate(() => window.goToPage(0));
  await page.waitForTimeout(300);
  await page.click('#rescan-btn');
  await page.waitForTimeout(4000);
  await page.screenshot({ path: `${OUT}/05_rescan_progress.png` });

  // detect.py takes real seconds against live Xero - wait for the actual
  // reload navigation the JS triggers when the scan completes
  await page.waitForNavigation({ timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(1000);
  await page.screenshot({ path: `${OUT}/06_rescan_done.png` });

  // jump to the receivables/chase module
  await page.evaluate(() => window.goToPage(8));
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/07_chase_draft.png` });

  // 5. Accountant report - not served by server.py, load the file directly
  await page.goto('file://' + __dirname + '/../accountant_report.html', { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/08_accountant.png` });

  // 6. Second page of the accountant report too (shows the pagination)
  await page.click('#next-btn');
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${OUT}/09_accountant_page2.png` });

  await browser.close();
  console.log('All screenshots captured to', OUT);
})();
