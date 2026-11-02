"""KLIPS 12~27차(2009~2024) 긴 패널로 디자이너·개발자·기획자의 장기 커리어 통계를 계산한다.

사용법:
    python klips_career_by_occupation.py <klips_extract_panel.py 출력 CSV> <출력 JSON>

직군 (KSCO 7차 소분류, p__0352):
    designer      285 디자이너 (제품·패션·실내장식·시각·웹/멀티미디어 전부. 소분류라 더 나눌 수 없다)
    developer     222 컴퓨터 시스템 및 소프트웨어 전문가 + 223 데이터 및 네트워크 관련 전문가
                  (12~20차에 222가 해마다 223으로 옮겨 가는 분류 변환 문제가 있어 둘을 합친다)
    planner       273 상품 기획·홍보 및 조사 전문가 (IT 서비스 기획만 따로 없음)
비가중 표본 수치. 21차(2018)에 통합표본이 추가되어 표본이 늘었다.
"""
import json
import sys

import numpy as np
import pandas as pd

GROUPS = {"designer": [285], "developer": [222, 223], "planner": [273]}
AGE_BANDS = [19, 24, 29, 34, 39, 44, 49, 54, 59, 120]
AGE_LABELS = ["20~24", "25~29", "30~34", "35~39", "40~44", "45~49", "50~54", "55~59", "60+"]
AGE3 = {"20~24": "~34", "25~29": "~34", "30~34": "~34", "35~39": "35~44", "40~44": "35~44"}
SAT = {"4311": "임금", "4312": "고용안정", "4313": "일의 내용", "4314": "근무환경", "4315": "근로시간",
       "4316": "발전가능성", "4317": "인간관계", "4318": "인사공정성", "4319": "복리후생"}


def prep(path):
    d = pd.read_csv(path)
    d["employed"] = d["0201"] == 1
    d["occ"] = d["0352"].where(d.employed)
    d["grp"] = "other"
    for g, codes in GROUPS.items():
        d.loc[d.occ.isin(codes), "grp"] = g
    d.loc[~d.employed, "grp"] = "not_employed"
    d["age_band"] = pd.cut(d["0107"], AGE_BANDS, labels=AGE_LABELS)
    d["age3"] = d.age_band.astype(str).map(AGE3).fillna("45+")
    d["self_emp"] = d["0314"] == 4
    d["wage"] = d["1642"].where(d["1642"].between(30, 5000))
    d["income_self"] = d["1672"].where(d["1672"].between(1, 10000))
    d["size3"] = d["0403"].map({1: "S", 2: "S", 3: "S", 4: "M", 5: "M", 6: "M", 7: "M", 8: "L", 9: "L", 10: "L"})
    d["job_start"] = d["0301"] * 12 + d["0302"].fillna(6)
    return d.sort_values(["pid", "wave"])


def add_next(d):
    n = d.groupby("pid").shift(-1)
    consecutive = n.wave == d.wave + 1
    d["n_grp"] = n.grp.where(consecutive)
    d["n_self"] = n.self_emp.where(consecutive)
    d["n_start"] = n.job_start.where(consecutive)
    d["n_wage"] = n.wage.where(consecutive)
    d["n_size3"] = n.size3.where(consecutive)
    return d


def shares(s):
    v = s.value_counts()
    return {"n": int(v.sum()), **(v / v.sum()).round(3).to_dict()} if v.sum() else {"n": 0}


def transitions(rows, g):
    """다음 해 상태: 같은 일자리 / 같은 직군 새 일자리 / 다른 직업 / 미취업. 자영업 전환은 따로."""
    r = rows[rows.n_grp.notna()]
    same_job = (r.n_grp == g) & (r.n_start == r.job_start)
    state = np.select(
        [same_job, r.n_grp == g, r.n_grp == "not_employed"],
        ["same_job", "new_job_same_occupation", "not_employed"], "other_occupation")
    out = shares(pd.Series(state))
    out["to_self_employed_share"] = round(float(((~r.self_emp) & (r.n_self == True)).mean()), 3)
    return out


def summarize(d, g):
    rows = d[d.grp == g]
    res = {"person_years": int(len(rows)), "persons": int(rows.pid.nunique())}
    ab = rows.groupby("age_band", observed=False)
    res["by_age"] = {
        str(a): {
            "n": int(len(x)),
            "female_share": round(float((x["0101"] == 2).mean()), 3) if len(x) else None,
            "wage_median": float(x.wage.median()) if x.wage.notna().any() else None,
            "self_employed_share": round(float(x.self_emp.mean()), 3) if len(x) else None,
            "self_income_median": float(x.income_self.median()) if x.income_self.notna().any() else None,
            "regular_share": round(float((x["0317"] == 1).sum() / x["0317"].isin([1, 2]).sum()), 3)
            if x["0317"].isin([1, 2]).any() else None,
            "firm_size3": shares(x.size3.dropna()),
        }
        for a, x in ab
    }
    res["annual_transition"] = {"all": transitions(rows, g)}
    for a3, x in rows.groupby("age3"):
        res["annual_transition"][a3] = transitions(x, g)
    for sex, lab in [(1, "male"), (2, "female")]:
        res["annual_transition"][lab] = transitions(rows[rows["0101"] == sex], g)

    # 직군을 떠나 미취업이 된 사람이 다음 해 같은 직군으로 돌아오는 비율
    left = d[(d.grp == "not_employed") & d.n_grp.notna()].copy()
    prev = d.groupby("pid").grp.shift(1).where(d.groupby("pid").wave.shift(1) == d.wave - 1)
    left = left[prev.loc[left.index] == g]
    res["reentry_next_year_from_not_employed"] = shares(pd.Series(
        np.where(left.n_grp == g, "back_same_occupation",
                 np.where(left.n_grp == "not_employed", "still_not_employed", "other_occupation"))))

    # 처음 관찰된 해 기준 k년 뒤에도 같은 직군인 비율 (그 해에 패널에 남아 있는 사람만)
    first = rows.groupby("pid").wave.min()
    status = d.set_index(["pid", "wave"]).grp
    surv = {}
    for k in [1, 2, 3, 5, 7, 10]:
        keys = [(p, w + k) for p, w in first.items()]
        later = status.reindex(keys).dropna()
        surv[f"{k}y"] = {"n": int(len(later)), "same_occupation": round(float((later == g).mean()), 3),
                         "not_employed": round(float((later == "not_employed").mean()), 3)}
    res["still_in_occupation_after"] = surv

    # 임금 변화: 같은 일자리 vs 이직 (전후 모두 임금 있는 경우), 연간 로그 변화 중앙값
    w = rows[rows.wage.notna() & rows.n_wage.notna() & (rows.n_grp == g)]
    ch = np.log(w.n_wage / w.wage)
    stay = w.n_start == w.job_start
    res["wage_change_yoy_median"] = {
        "same_job": {"n": int(stay.sum()), "pct": round(float(np.expm1(ch[stay].median()) * 100), 1)},
        "job_change": {"n": int((~stay).sum()),
                       "pct": round(float(np.expm1(ch[~stay].median()) * 100), 1) if (~stay).any() else None},
    }
    # 같은 직군 이직 시 기업 규모 이동
    m = rows[(rows.n_grp == g) & (rows.n_start != rows.job_start) & rows.size3.notna() & rows.n_size3.notna()]
    if len(m):
        res["size3_transition_on_job_change"] = {
            "n": int(len(m)),
            "counts": pd.crosstab(m.size3, m.n_size3).to_dict(orient="index"),
        }
    res["satisfaction_mean_1to5_high_is_good"] = {
        lab: round(float((6 - rows[c].where(rows[c].between(1, 5))).mean()), 2) for c, lab in SAT.items()
    }
    return res


def main():
    d = add_next(prep(sys.argv[1]))
    out = {"meta": {
        "source": "한국노동패널(KLIPS) 12~27차(2009~2024) 개인, 비가중",
        "groups": {"designer": "KSCO7 285", "developer": "KSCO7 222+223", "planner": "KSCO7 273"},
        "notes": [
            "주된 일자리 기준. 같은 일자리 = 다음 해 취업 시작 년·월이 같음.",
            "만족도는 원자료(1 매우 만족)를 뒤집어 5 = 매우 만족으로 표시.",
            "기업 규모 = 전체 종업원수 범주(p__0403), 모름 제외.",
            "21차(2018)부터 통합표본 추가.",
        ]}}
    for g in GROUPS:
        out[g] = summarize(d, g)
    allemp = d[d.employed].copy()
    out["all_employed_wage_by_age"] = {
        str(a): float(x.wage.median()) for a, x in allemp.groupby("age_band", observed=False) if x.wage.notna().any()
    }
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
