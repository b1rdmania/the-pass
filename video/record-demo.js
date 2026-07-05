// Records a real working demo of The Pass - one continuous browser session,
// nothing staged. Playwright drives the live app at localhost:5050 (which is
// talking to live Xero + live Claude), and the whole session is captured as
// video. Title cards are rendered in-session so no post-concat is needed.

const { chromium } = require('playwright');
const path = require('path');

const PAPER = '#e6dfd0';
const INK = '#1a1816';

const card = (big, small) => `
<!DOCTYPE html><html><body style="margin:0;background:${PAPER};height:100vh;
display:flex;flex-direction:column;justify-content:center;padding:0 8vw;
font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;color:${INK};">
<div style="font-size:64px;font-weight:700;letter-spacing:-0.01em;">${big}</div>
<div style="font-size:26px;color:#4a4742;margin-top:22px;font-family:'Times New Roman',serif;font-style:italic;">${small}</div>
</body></html>`;

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: { dir: path.join(__dirname, 'out'), size: { width: 1280, height: 800 } },
  });
  const page = await context.newPage();

  // -- intro card ------------------------------------------------------------
  await page.setContent(card(
    'the pass <span style="font-family:\'Times New Roman\',serif;font-style:italic;font-weight:400;">v.01</span>',
    'A working demo. Live Xero data, live agent — nothing staged.'
  ));
  await page.waitForTimeout(3500);

  // -- 1. dashboard overview ---------------------------------------------------
  await page.goto('http://localhost:5050/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(5500);

  // -- 2. a module with findings ----------------------------------------------
  await page.evaluate(() => window.goToPage(2));
  await page.waitForTimeout(6500);

  // -- 3. ask the agent a real question ----------------------------------------
  await page.evaluate(() => window.goToPage(10));
  await page.waitForTimeout(1200);
  await page.type('#ask-input', 'which supplier did we pay twice this year?', { delay: 55 });
  await page.waitForTimeout(700);
  await page.click('#ask-btn');
  await page.waitForFunction(
    () => (document.getElementById('ask-answer')?.textContent || '').length > 20,
    { timeout: 30000 }
  );
  await page.waitForTimeout(6500);

  // -- 4. the real re-scan ------------------------------------------------------
  await page.evaluate(() => window.goToPage(0));
  await page.waitForTimeout(1500);
  await page.click('#rescan-btn');
  // the terminal streams the detection log; the page reloads itself when done
  await page.waitForNavigation({ timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(4000);

  // -- 5. the chase draft --------------------------------------------------------
  await page.evaluate(() => window.goToPage(8));
  await page.waitForTimeout(7000);

  // -- 6. the accountant report ---------------------------------------------------
  await page.goto('file://' + path.join(__dirname, '..', 'accountant_report.html'));
  await page.waitForTimeout(6000);

  // -- outro card ------------------------------------------------------------------
  await page.setContent(card(
    'Real oversight. More value from Xero. <span style="font-family:\'Times New Roman\',serif;font-style:italic;font-weight:400;">More profit.</span>',
    'open-sandal-rkdw.here.now &nbsp;·&nbsp; the pass v.01'
  ));
  await page.waitForTimeout(3500);

  await context.close();  // flushes the video file
  const video = await page.video().path();
  console.log('recorded:', video);
  await browser.close();
})();
