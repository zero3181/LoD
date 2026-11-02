"""게임 프로토타입 입력용 확률표를 만든다 (디자이너·개발자 플레이, 성별 포함, 패션·실내장식 제외).

사용법:
    python build_game_params.py <klips_panel.csv> <YP2021 직업력 csv|xlsx> <출력 JSON>

klips_panel.csv 는 klips_extract_panel.py 출력. 직업력은 YP2021_JOBHIS_0608.
직군 정의는 klips_career_by_occupation.py, yp2021_jobhis_occupations.py 와 같다.
  디자이너: 청년패널은 KECO 4151·4154·4155 (패션 4152·실내장식 4153 제외).
            노동패널은 KSCO 285 하나라 패션·실내장식을 뺄 수 없다.
  개발자: KLIPS 222+223, 청년패널 KECO 1320·1331~1339.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import klips_career_by_occupation as kc  # noqa: E402
import yp2021_jobhis_occupations as yj  # noqa: E402

SEX = {1: "male", 2: "female"}
AGE3_ORDER = ["~34", "35~44", "45+"]
OCC = ["designer", "developer"]


def share_dict(states):
    v = pd.Series(states).value_counts()
    return {"n": int(v.sum()), **{k: round(float(x), 4) for k, x in (v / v.sum()).items()}}


def klips_part(path):
    d = kc.add_next(kc.prep(path))
    # 다음 해 직업 코드 (직군 전환 도착지 확인용)
    n = d.groupby("pid").shift(-1)
    d["n_occ"] = n.occ.where(n.wave == d.wave + 1)
    out = {}
    for g in OCC:
        rows = d[(d.grp == g) & d.n_grp.notna()].copy()
        same_job = (rows.n_grp == g) & (rows.n_start == rows.job_start)
        rows["state"] = np.select(
            [same_job, rows.n_grp == g, rows.n_grp == "not_employed"],
            ["same_job", "new_job_same_occupation", "not_employed"], "other_occupation")
        tr = {}
        for sex, lab in SEX.items():
            tr[lab] = {}
            for a3 in AGE3_ORDER:
                x = rows[(rows["0101"] == sex) & (rows.age3 == a3)]
                tr[lab][a3] = share_dict(x.state)
        # 다른 직업으로 옮긴 사람의 도착지
        oth = rows[rows.state == "other_occupation"]
        dest = oth.n_grp.where(oth.n_grp.isin(["designer", "developer", "planner"]), "other")
        # 임금근로 → 자영업 / 자영업 → 임금근로 (같은 직군 안에서)
        stay = rows[rows.n_grp == g]
        to_self = float(((~stay.self_emp) & (stay.n_self == True)).sum() / max((~stay.self_emp).sum(), 1))
        se = stay[stay.self_emp]
        to_wage = float((se.n_self == False).sum() / max(len(se), 1))
        # 미취업 다음 해 상태 (직전 해 이 직군)
        prev = d.groupby("pid").grp.shift(1).where(d.groupby("pid").wave.shift(1) == d.wave - 1)
        ne = d[(d.grp == "not_employed") & d.n_grp.notna() & (prev == g)]
        re = {}
        for sex, lab in SEX.items():
            x = ne[ne["0101"] == sex]
            re[lab] = share_dict(np.where(x.n_grp == g, "back_same_occupation",
                                          np.where(x.n_grp == "not_employed", "still_not_employed",
                                                   "other_occupation")))
        # 나이·성별 월임금 중앙값 (임금근로자)
        allg = d[d.grp == g]
        wage = {}
        for sex, lab in SEX.items():
            wage[lab] = {}
            for a, x in allg[allg["0101"] == sex].groupby("age_band", observed=False):
                w = x.wage.dropna()
                wage[lab][str(a)] = {"n": int(len(w)), "median": float(w.median()) if len(w) else None}
        wage_all = {str(a): {"n": int(x.wage.notna().sum()),
                             "median": float(x.wage.median()) if x.wage.notna().any() else None}
                    for a, x in allg.groupby("age_band", observed=False)}
        # 25~44세 기업 규모별 임금 배수 (같은 나이대 중앙값 대비)
        mid = allg[allg["0107"].between(25, 44) & allg.wage.notna()].copy()
        mid["ratio"] = mid.wage / mid.groupby("age_band", observed=True).wage.transform("median")
        size_mult = {s: {"n": int(len(x)), "mult": round(float(x.ratio.median()), 3)}
                     for s, x in mid.groupby("size3")}
        # 같은 나이대 안에서 임금 퍼짐 (로그 표준편차)
        mid["lr"] = np.log(mid.ratio)
        out[g] = {
            "transition": tr,
            "other_occupation_destination": share_dict(dest),
            "self_employment": {"wage_to_self_annual": round(to_self, 4), "n_wage": int((~stay.self_emp).sum()),
                                "self_to_wage_annual": round(to_wage, 4), "n_self": int(len(se))},
            "not_employed_next_year": re,
            "wage_by_sex_age": wage,
            "wage_by_age": wage_all,
            "self_income_by_age": {str(a): float(x.income_self.median()) if x.income_self.notna().any() else None
                                   for a, x in allg.groupby("age_band", observed=False)},
            "size3_wage_multiplier_25_44": size_mult,
            "wage_log_sd_within_age_25_44": round(float(mid.lr.std()), 3),
            "satisfaction_mean_1to5": {lab: round(float((6 - allg[c].where(allg[c].between(1, 5))).mean()), 2)
                                       for c, lab in kc.SAT.items()},
        }
    return out


def yp_part(path):
    j, s = yj.build_spells(yj.load(path))
    groups = {"designer": "designer_core", "developer": "developer"}
    out = {}
    first = s.sort_values(["sampid", "jobseq"]).groupby("sampid").head(1).copy()
    first["age"] = first.start_y - first.birth
    for g, key in groups.items():
        f = first[yj.GROUPS[key](first.occ)]
        sp = s[yj.GROUPS[key](s.occ)]
        res = {"n_first_jobs": int(len(f)),
               "female_share_first_job": round(float((f.gender == 2).mean()), 3)}
        res["start_age"] = {}
        res["first_wage_median"] = {}
        for sex, lab in SEX.items():
            x = f[f.gender == sex]
            a = x.age.dropna()
            res["start_age"][lab] = {"n": int(len(a)), "q25": float(a.quantile(.25)), "median": float(a.median()),
                                     "q75": float(a.quantile(.75))}
            w = x.wage_first.dropna()
            res["first_wage_median"][lab] = {"n": int(len(w)), "median": float(w.median()) if len(w) else None}
        sz = f["size"].dropna().astype(int)
        sz = sz[sz.between(1, 9)].map(dict(enumerate(yj.SIZE9, 1))).value_counts()
        res["first_job_size9"] = {"n": int(sz.sum()), **(sz / sz.sum()).reindex(yj.SIZE9).fillna(0).round(4).to_dict()}
        res["first_job_regular_share"] = round(float((f.regular == 1).sum() / f.regular.isin([1, 2]).sum()), 3)
        q = sp.loc[sp.ended, "quit"].map(yj.QUIT).value_counts()
        res["quit_reasons"] = {"n": int(q.sum()), **(q / q.sum()).round(4).to_dict()}
        # 이직 공백 (개월) 분포
        s2 = s.sort_values(["sampid", "jobseq"]).copy()
        s2["next_start"] = s2.groupby("sampid").start_idx.shift(-1)
        nx = s2[yj.GROUPS[key](s2.occ) & s2.next_start.notna() & s2.ended]
        gap = (nx.next_start - nx.end_idx).clip(lower=0)
        res["gap_months"] = {"n": int(len(gap)), "le1": round(float((gap <= 1).mean()), 3),
                             "2to6": round(float(gap.between(2, 6).mean()), 3), "gt6": round(float((gap > 6).mean()), 3),
                             "median": float(gap.median())}
        out[g] = res
    return out


def main():
    out = {
        "meta": {
            "built_from": ["data/16_ 원자료 KLIPS 12~27차", "data/14_ 원자료 YP2021 직업력"],
            "notes": [
                "디자이너: 청년패널 값은 패션·실내장식 제외(KECO 4151·4154·4155). 노동패널 값은 KSCO 285 전체(나눌 수 없음).",
                "연간 이동 = 다음 해 상태. same_job / new_job_same_occupation / other_occupation / not_employed.",
                "비가중, 표본 수 n 을 함께 적었다. n<30 칸은 게임에서 상위 칸(성별 합계)으로 대체한다.",
            ],
        },
        "klips": klips_part(sys.argv[1]),
        "yp": yp_part(sys.argv[2]),
    }
    json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
