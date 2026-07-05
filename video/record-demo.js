// Records the working demo of The Pass - one continuous browser session,
// nothing staged. Narrative cards are rendered in-session between real
// segments; everything between them is the live app talking to live Xero.

const { chromium } = require('playwright');
const path = require('path');

const PAPER = '#e6dfd0';
const INK = '#1a1816';

const card = (big, small, bigSize = 58) => `
<!DOCTYPE html><html><body style="margin:0;background:${PAPER};height:100vh;
display:flex;flex-direction:column;justify-content:center;padding:0 8vw;
font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;color:${INK};">
<div style="font-size:${bigSize}px;font-weight:700;letter-spacing:-0.01em;line-height:1.2;">${big}</div>
${small ? `<div style="font-size:25px;color:#4a4742;margin-top:22px;font-family:'Times New Roman',serif;font-style:italic;line-height:1.5;">${small}</div>` : ''}
</body></html>`;

const it = (s) => `<span style="font-family:'Times New Roman',serif;font-style:italic;font-weight:400;color:#4a4742;">${s}</span>`;

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: { dir: path.join(__dirname, 'out'), size: { width: 1280, height: 800 } },
  });
  const page = await context.newPage();

  // -- 1. open ---------------------------------------------------------------
  await page.setContent(card(
    `the pass ${it('v.01')}`,
    'A line check for a hospitality operator’s Xero books. Live data, live agent — nothing staged.',
    72
  ));
  await page.waitForTimeout(3800);

  // -- 2. the trust card -------------------------------------------------------
  await page.setContent(card(
    `Five deterministic detectors.<br>36 months. ${it('No LLM in the detection loop.')}`,
    'It cannot hallucinate a finding — every number below comes from the ledger.'
  ));
  await page.waitForTimeout(4000);

  // -- 3. dashboard overview ----------------------------------------------------
  await page.goto('http://localhost:5050/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(5000);

  // -- 4. the modules, one slow scroll -------------------------------------------
  await page.evaluate(() => window.goToPage(1));
  await page.waitForTimeout(2000);
  for (let i = 0; i < 6; i++) {
    await page.evaluate(() => window.scrollBy({ top: 700, behavior: 'smooth' }));
    await page.waitForTimeout(1400);
  }

  // -- 5. the agent card -----------------------------------------------------------
  await page.setContent(card(`then the agent.`,
    'Claude with tools — it decides for itself what to pull from Xero.'));
  await page.waitForTimeout(3000);

  // -- 6. live question: the five-tool-call one --------------------------------------
  await page.goto('http://localhost:5050/', { waitUntil: 'networkidle' });
  await page.evaluate(() => window.goToPage(3));
  await page.waitForTimeout(1200);
  await page.type('#ask-input', 'which supplier did we pay twice this year, and how much is at stake?', { delay: 45 });
  await page.waitForTimeout(600);
  await page.click('#ask-btn');
  await page.waitForFunction(
    () => (document.getElementById('ask-answer')?.textContent || '').length > 20,
    { timeout: 45000 }
  );
  await page.waitForTimeout(8000);

  // -- 7. the live card ---------------------------------------------------------------
  await page.setContent(card(`and none of this is a tape.`,
    'Watch it re-derive everything from Xero, from scratch, right now.'));
  await page.waitForTimeout(3000);

  // -- 8. the real re-scan ---------------------------------------------------------------
  await page.goto('http://localhost:5050/', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);
  await page.click('#rescan-btn');
  await page.waitForNavigation({ timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(3500);

  // -- 9. the accountant report -------------------------------------------------------------
  await page.goto('file://' + path.join(__dirname, '..', 'accountant_report.html'));
  await page.waitForTimeout(5000);

  // -- 10. close ---------------------------------------------------------------------------
  await page.setContent(card(
    `Real oversight. More value from Xero. ${it('More profit.')}`,
    'open-sandal-rkdw.here.now &nbsp;·&nbsp; github.com/b1rdmania/the-pass'
  ));
  await page.waitForTimeout(4000);

  await context.close();
  const video = await page.video().path();
  console.log('recorded:', video);
  await browser.close();
})();
