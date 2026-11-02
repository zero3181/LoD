const { chromium } = require('playwright');
const fs = require('fs');
const [,, orgId, tblId, outf] = process.argv;
(async () => {
  const b = await chromium.launch();
  for (let attempt = 1; attempt <= 4; attempt++) {
    const p = await b.newPage({ viewport: { width: 1800, height: 1400 } });
    try {
      await p.goto(`https://kosis.kr/statHtml/statHtml.do?orgId=${orgId}&tblId=${tblId}&conn_path=I2`, { waitUntil: 'domcontentloaded', timeout: 90000 });
    } catch (e) { console.log('goto err', e.message.slice(0, 80)); }
    let best = '';
    for (let i = 0; i < 10; i++) {
      await p.waitForTimeout(5000);
      const body = await p.evaluate(() => document.body ? document.body.innerText : '').catch(() => '');
      if (/upstream request failed/.test(body)) break;
      for (const f of p.frames()) { const t = await f.evaluate(() => document.body ? document.body.innerText : '').catch(() => ''); if (f.url().includes('right_layout') || /시점|항목/.test(t)) { if (t.length > best.length) best = t; } }
      if (best.length > 800) break;
    }
    console.log('attempt', attempt, 'len', best.length);
    if (best.length > 800) { fs.writeFileSync(outf, best); await p.screenshot({ path: outf + '.png' }); await b.close(); return; }
    await p.close(); await new Promise(r => setTimeout(r, 2000 * 2 ** attempt));
  }
  await b.close();
})();
