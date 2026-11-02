const { chromium } = require('playwright');
const fs = require('fs');
const [,, orgId, tblId, outf] = process.argv;
(async () => {
  const b = await chromium.launch();
  for (let a = 1; a <= 6; a++) {
    const p = await b.newPage();
    await p.goto(`https://kosis.kr/statHtml/statHtml.do?orgId=${orgId}&tblId=${tblId}&conn_path=I2`, { waitUntil: 'domcontentloaded', timeout: 90000 }).catch(() => {});
    let html = '';
    for (let i = 0; i < 8 && !html; i++) { await p.waitForTimeout(5000); for (const f of p.frames()) { const c = await f.content().catch(() => ''); if (c.includes('listClassLvl')) html = c; } }
    console.log('attempt', a, html.length);
    if (html) { fs.writeFileSync(outf, html); break; }
    await p.close(); await new Promise(r => setTimeout(r, 3000 * a));
  }
  await b.close();
})();
