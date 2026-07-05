// Renders the project banner image for the Encode submission page.
const { chromium } = require('playwright');

const html = `
<!DOCTYPE html><html><body style="margin:0;background:#e6dfd0;width:1280px;height:640px;
overflow:hidden;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;color:#1a1816;position:relative;">
  <div style="position:absolute;left:80px;top:150px;">
    <div style="font-size:15px;font-weight:700;letter-spacing:0.1em;color:#4a4742;">LINE CHECK</div>
    <div style="font-size:96px;font-weight:700;letter-spacing:-0.01em;margin-top:6px;">
      the pass <span style="font-family:'Times New Roman',serif;font-style:italic;font-weight:400;font-size:54px;color:#4a4742;">v.01</span>
    </div>
    <div style="font-size:30px;color:#4a4742;margin-top:18px;max-width:640px;line-height:1.4;">
      Your data holds the answers.<br>
      <span style="font-family:'Times New Roman',serif;font-style:italic;">No one is watching it. Now something is.</span>
    </div>
  </div>
  <div style="position:absolute;right:80px;top:150px;width:360px;border:2px solid #1a1816;background:#0f0f0f;">
    <div style="padding:10px 16px;border-bottom:1px solid #333;font-family:'Courier New',monospace;font-size:12px;color:#8a8a8a;">the-pass — xero-sync</div>
    <div style="padding:16px;font-family:'Courier New',monospace;font-size:14px;line-height:1.9;color:#b8e0b8;">
      <span style="color:#8a8a8a;">$</span> python3 detect.py<br>
      477 txns pulled from Xero<br>
      duplicate &rarr; zurich, £1,800<br>
      ratio &rarr; wages 33% of sales<br>
      churn &rarr; 1 regular gone quiet<br>
      <span style="color:#e6dfd0;">84 findings written</span>
    </div>
  </div>
  <div style="position:absolute;left:80px;right:80px;bottom:46px;display:flex;justify-content:space-between;
    font-size:14px;font-weight:700;letter-spacing:0.06em;color:#4a4742;">
    <span>XERO APP &amp; AGENT HACKATHON</span><span>LONDON · JULY 2026</span>
  </div>
</body></html>`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 640 }, deviceScaleFactor: 2 });
  await page.setContent(html);
  await page.waitForTimeout(400);
  await page.screenshot({ path: process.env.HOME + '/Desktop/the-pass-submission/the-pass-banner.png' });
  await browser.close();
  console.log('banner written');
})();
