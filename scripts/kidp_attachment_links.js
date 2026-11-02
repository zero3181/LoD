const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  for (const t of ['2025 디자인산업통계 공표(2024년 기준)', '2025 디자인산업통계 카드뉴스']) {
    await p.goto('https://www.kidp.or.kr/?menuno=893', { waitUntil: 'domcontentloaded' });
    await p.locator(`a[title="${t}"]`).first().click();
    await p.waitForTimeout(5000); await p.waitForLoadState('networkidle');
    const links = await p.evaluate(() => [...document.querySelectorAll('a')].filter(a => /\/usr\/upload/.test(a.getAttribute('href') || '')).map(a => a.innerText.trim() + ' | ' + a.getAttribute('href')));
    console.log('==', t); console.log(links.join('\n'));
  }
  await b.close();
})();
