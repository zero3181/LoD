const { chromium } = require('playwright');
const S = process.argv[2];
const fs = require('fs');
const LOG = S + '/play3.txt';
const out = (s) => fs.appendFileSync(LOG, s + '\n');
async function life(b, n) {
  const ctx = await b.newContext({ viewport: { width: 1280, height: 900 }, locale: 'ko-KR' });
  const p = await ctx.newPage();
  await p.goto('https://1in8b.life/ko/', { waitUntil: 'networkidle' });
  await p.getByText('약 30분', { exact: true }).first().click();
  await p.getByRole('button', { name: '태어나기' }).first().click();
  await p.waitForTimeout(4000);
  const birth = await p.evaluate(() => document.body.innerText);
  const bm = birth.match(/\d{4}년 \d+월, [^\n]+/);
  out(`\n\n######## LIFE ${n}: ${bm ? bm[0] : '?'}`);
  await p.getByText('삶을 시작하기', { exact: true }).first().click();
  await p.waitForTimeout(1500);
  await p.getByRole('button', { name: '자동 결정' }).first().click().catch(()=>{});
  await p.getByRole('button', { name: '16×' }).first().click().catch(()=>{});
  let lastAge = '', stall = 0, maxAge = 0; const seen = new Set(); const t0 = Date.now();
  while (Date.now() - t0 < 40 * 60 * 1000) {
    await p.waitForTimeout(2500);
    const info = await p.evaluate(() => {
      const t = document.body.innerText;
      const m = t.match(/80억 분의 1\s*\n?\s*(\d+)\s*\n?\s*세/);
      const dlg = [...document.querySelectorAll('[role=dialog], dialog, [class*=modal], [class*=dialog], [class*=sheet]')].filter(e => e.offsetParent || getComputedStyle(e).position === 'fixed').map(e => e.innerText.trim()).filter(x => x.length > 20);
      const btns = [...document.querySelectorAll('button')].filter(b => b.offsetParent).map(b => b.innerText.trim()).filter(Boolean);
      return { age: m ? +m[1] : null, dlg, btns, ended: /사망 기록 · RECORD OF DEATH/.test(t) };
    });
    if (info.age) maxAge = Math.max(maxAge, info.age);
    for (const d of info.dlg) { const k = d.slice(0, 120); if (!seen.has(k)) { seen.add(k); out(`\n### DIALOG @age ${info.age}\n` + d.slice(0, 2000)); } }
    if (info.ended) {
      const full = await p.evaluate(() => document.body.innerText);
      const m = full.match(/향년 (\d+)세/); const age = m ? +m[1] : maxAge;
      out(`\n### END age ${age}\n` + full.slice(0, 3500));
      if (age >= 65) { fs.writeFileSync(S + '/end-old.txt', full); await p.screenshot({ path: S + '/shots/20-old-end.png', fullPage: true }); }
      await ctx.close(); return age;
    }
    if (info.age === lastAge) stall++; else { stall = 0; lastAge = info.age; }
    if (info.age && [30, 50, 70].includes(info.age)) await p.screenshot({ path: S + `/shots/21-l${n}-age${info.age}.png` });
    if (stall >= 2) {
      const cands = ['넘어가기', '계속', '이어 살기', '확인', '닫기', '건너뛰기', '다음'];
      let clicked = false;
      for (const c of cands) { const l = p.getByRole('button', { name: c }); if (await l.count()) { await l.first().click().catch(()=>{}); clicked = true; break; } }
      if (!clicked) { const l = p.locator('button').filter({ hasText: /^1\n/ }); if (await l.count()) await l.first().click().catch(()=>{}); else await p.mouse.click(640, 450); }
      stall = 0;
    }
  }
  out('### TIMEOUT maxAge ' + maxAge); await ctx.close(); return maxAge;
}
(async () => {
  fs.writeFileSync(LOG, '');
  const b = await chromium.launch();
  for (let n = 1; n <= 6; n++) { const a = await life(b, n); out(`>>> life ${n} ended at ${a}`); if (a >= 65) break; }
  await b.close();
})();
