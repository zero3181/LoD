// 사람마다 다른 '떠나는 성향'(감마분포 배수)을 노동패널 실제 값에 맞춘다.
// 맞추는 값 (role 마다):
//   mean  : 배수의 평균
//   shape : 감마분포 모양 (작을수록 사람 사이 차이가 크다, 1000 = 차이 없음)
//   fade  : 45세부터 해마다 차이를 남기는 비율 (1 = 평생 그대로, 0.8 = 해마다 20%씩 평균으로 다가감)
// 목표 (2026-11-02):
//   1) 30세 이하에 처음 그 직군으로 관찰된 사람이 1·3·5·10·12·15년 뒤 같은 직군인 비율 (노동패널, 그 해 패널에 남은 사람 기준)
//   2) 나이대별 5년 유지율: 그 나이대(25~29 ... 50~54)에 그 직군으로 처음 보인 사람이 5년 뒤 같은 직군인 비율 (노동패널, 패널에 남은 사람 기준)
//      15년 넘는 구간은 관찰값이 없어서, 중년 이후 유지는 이 값으로 잡는다. 표본이 1)의 10·15년보다 크다.
//   3) 2020~2024 노동패널 그 직군 취업자의 나이 분포 (30세 미만 / 30대 / 40대 / 50대, 60세 미만만)
//      게임 쪽은 매년 같은 수가 들어온다고 보고 굴린 나이 분포. 실제는 최근 신입이 늘어 젊은 쪽으로 쏠려 있을 수 있다.
// 사용법: node calibrate.js index.html
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const js = html.split("<script>")[1].split("</script>")[0];
const el = () => ({ dataset: {}, innerHTML: "", querySelector: () => el(), querySelectorAll: () => [] });
global.document = { getElementById: () => el() }; global.window = {}; global.setTimeout = () => 0; global.clearTimeout = () => {};
const api = new Function(js + "\nreturn {R, newPerson, step, advanceAge};")();
const KEEP = {
  designer: { 1: [0.73, 92], 3: [0.66, 67], 5: [0.56, 57], 10: [0.23, 30], 12: [0.33, 24], 15: [0.45, 11] },
  developer: { 1: [0.87, 158], 3: [0.77, 110], 5: [0.70, 83], 10: [0.69, 45], 12: [0.57, 35], 15: [0.64, 22] },
};
const BAND = {
  designer: { 25: [0.58, 43], 30: [0.51, 45], 35: [0.60, 48], 40: [0.68, 28], 45: [0.71, 14], 50: [0.62, 8] },
  developer: { 25: [0.70, 64], 30: [0.75, 91], 35: [0.78, 101], 40: [0.75, 68], 45: [0.89, 37], 50: [0.88, 16] },
};
const AGE_RAW = { designer: [24.1, 34.7, 30.9, 8.9], developer: [16.2, 35.4, 33.5, 14.2] };
const AGE = Object.fromEntries(Object.entries(AGE_RAW).map(([k, v]) => { const s = v.reduce((a, b) => a + b, 0); return [k, v.map((x) => x / s)]; }));
// 10·12·15년 값은 거의 같은 사람들을 세 번 센 것이라 각각 n/3 무게만 준다 (합치면 한 번 센 것과 같다).
const LONG = ["10", "12", "15"];
const AGE_W = +(process.env.AGE_W ?? 0); // 나이 분포는 중간 유입·신입 규모 변화가 섞인 단면값이라 기본은 확인용(무게 0). AGE_W=300 으로 함께 맞출 수 있다.

function run(role, N) {
  const keep = Object.fromEntries(Object.keys(KEEP[role]).map((k) => [k, 0]));
  let young = 0;
  const ages = [0, 0, 0, 0];
  const band = Object.fromEntries(Object.keys(BAND[role]).map((b) => [b, [0, 0]]));
  let to60 = 0;
  for (let i = 0; i < N; i++) {
    const sex = Math.random() < api.R[role].female_share ? "female" : "male";
    const P = api.newPerson(role, sex);
    const y = P.startAge <= 30; if (y) young++;
    const hist = {};
    for (let t = 0; t < 45; t++) {
      if (t > 0) { api.step(P); api.advanceAge(P); }
      if (P.end) break;
      const inRole = ["wage", "self", "leave"].includes(P.status) && P.role === role; // 쉼·다른 직업(away)은 빼고
      hist[P.age] = inRole;
      if (y && inRole && keep[t] !== undefined) keep[t]++;
      if (inRole && P.age < 60) ages[P.age < 30 ? 0 : P.age < 40 ? 1 : P.age < 50 ? 2 : 3]++;
    }
    if (hist[59]) to60++;
    for (const b in band) {
      let a0 = null;
      for (let a = +b; a < +b + 5; a++) if (hist[a]) { a0 = a; break; }
      if (a0 !== null && a0 + 5 <= 59) { band[b][0]++; if (hist[a0 + 5]) band[b][1]++; }
    }
  }
  for (const k in keep) keep[k] /= young;
  for (const b in band) band[b] = band[b][1] / band[b][0];
  const s = ages.reduce((a, b) => a + b, 0);
  return { keep, band, to60: to60 / N, age: ages.map((x) => x / s) };
}
function loss(role, r) {
  const a = Object.entries(KEEP[role]).reduce((s, [k, [o, n]]) => s + (LONG.includes(k) ? n / 3 : n) * (r.keep[k] - o) ** 2, 0);
  const b = AGE_W * r.age.reduce((s, x, i) => s + (x - AGE[role][i]) ** 2, 0);
  const c = Object.entries(BAND[role]).reduce((s, [k, [o, n]]) => s + n * (r.band[k] - o) ** 2, 0);
  return { total: a + b + c, keep: a, age: b, band: c };
}
const fmt = (r) => `keep ${Object.entries(r.keep).map(([k, v]) => `${k}y ${(v * 100).toFixed(0)}`).join(" ")} | band ${Object.entries(r.band).map(([k, v]) => `${k} ${(v * 100).toFixed(0)}`).join(" ")} | age ${r.age.map((x) => (x * 100).toFixed(0)).join("/")} | to60 ${(r.to60 * 100).toFixed(1)}`;
const out = {};
for (const role of (process.env.ROLES || "designer,developer").split(",")) {
  let best = null;
  for (const mean of [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6, 1.8, 2.1])
    for (const shape of [0.15, 0.2, 0.3, 0.4, 0.5, 0.7, 1, 1000])
      for (const fade of [1, 0.9, 0.8, 0.7, 0.6, 0.5, 0.35, 0]) {
        if (shape === 1000 && fade !== 1) continue;
        api.R[role].hetero = { mean, shape, fade };
        const r = run(role, 3000);
        const l = loss(role, r);
        if (!best || l.total < best.l.total) best = { mean, shape, fade, l, r };
      }
  api.R[role].hetero = { mean: best.mean, shape: best.shape, fade: best.fade };
  const fin = run(role, 12000);
  delete api.R[role].hetero;
  const base = run(role, 12000);
  out[role] = { mean: best.mean, shape: best.shape, fade: best.fade };
  console.log(`${role} best mean ${best.mean} shape ${best.shape} fade ${best.fade} loss ${JSON.stringify(loss(role, fin))}`);
  console.log("  game  ", fmt(fin));
  console.log("  no het", fmt(base), JSON.stringify(loss(role, base)));
  console.log("  target", `keep ${Object.entries(KEEP[role]).map(([k, [v]]) => `${k}y ${(v * 100).toFixed(0)}`).join(" ")} | band ${Object.entries(BAND[role]).map(([k, [v]]) => `${k} ${(v * 100).toFixed(0)}`).join(" ")} | age ${AGE[role].map((x) => (x * 100).toFixed(0)).join("/")}`);
}
console.log(JSON.stringify(out));
