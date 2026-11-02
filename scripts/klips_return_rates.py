"""직군을 떠난 사람이 다음 해 그 직군으로 돌아오는 비율 (노동패널 12~27차).
떠난 첫해(직전 해가 그 직군)와 그 이후를 나눠 본다. 상태: other(다른 직업 취업) / not_employed(미취업).
사용법: python scripts/klips_return_rates.py klips_panel.csv  → data/20_klips_return_rates.json"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import klips_career_by_occupation as kc

d = kc.add_next(kc.prep(sys.argv[1]))
prev = d.set_index(["pid", "wave"]).grp
res = {}
for g in ["designer", "developer"]:
    first = d[d.grp == g].groupby("pid").wave.min()
    x = d[d.pid.isin(first.index)].copy()
    x = x[x.wave > x.pid.map(first)]
    out = {}
    for state in ["other", "not_employed"]:
        r = x[(x.grp != g) & ((x.grp == "not_employed") if state == "not_employed" else (x.grp != "not_employed")) & x.n_grp.notna()]
        pv = prev.reindex(list(zip(r.pid, r.wave - 1))).values
        r = r.assign(first_year=(pv == g))
        for fy, rr in r.groupby("first_year"):
            v = rr.n_grp.map(lambda s: "back" if s == g else ("not_employed" if s == "not_employed" else "other")).value_counts(normalize=True)
            out[f"{state}_{'first' if fy else 'later'}"] = {"n": int(len(rr)), **{k: round(float(v.get(k, 0)), 3) for k in ["back", "other", "not_employed"]}}
    res[g] = out
print(json.dumps(res, ensure_ascii=False, indent=1))
json.dump(res, open(os.path.join(os.path.dirname(__file__), "..", "data", "20_klips_return_rates.json"), "w"), ensure_ascii=False, indent=1)
