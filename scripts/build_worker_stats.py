"""일반 직장인(임금근로자) 통계와 디자이너 비교. 게임의 '직장인' 사건 카드 근거.

사용법:
    python build_worker_stats.py "<KLIPS 1-27차 release (Excel) 폴더>" <출력 JSON>

한국노동패널 25~27차(2022~2024 조사) 개인용, 20~59세, 임금근로자(p__0211 == 1) 사람-해 단위, 비가중.
디자이너 = 주된 일자리 KSCO 7차 285, 개발자 = 222+223(게임의 개발자 확률표와 같은 정의). 문항마다 응답이 있는 사람만 센다(해당 차수에 없는 문항은 빈칸).
"""
import json
import sys

import pandas as pd
import python_calamine as pc

VARS = ["0101", "0107", "0211", "0352", "0317", "0301", "1004", "1011", "1012", "1019", "1015", "1621",
        "2501", "2504", "4311", "4312", "4313", "4314", "4315", "4316", "4317", "4318", "4319", "4321",
        "5701", "6101", "6154", "6158", "6161", "6162", "6501", "6502", "6503", "6504", "6506", "6508",
        "6311", "6331", "6341"]
SAT = {"4311": "임금", "4312": "고용안정", "4313": "일의 내용", "4314": "근무환경", "4315": "근로시간",
       "4316": "발전가능성", "4317": "인간관계", "4318": "인사고과 공정성", "4319": "복리후생", "4321": "일자리 전반"}
LIFE = {"6501": "가족의 수입", "6502": "여가활동", "6503": "주거환경", "6504": "가족관계", "6506": "사회적 친분", "6508": "생활 전반"}
DISC = {"6311": "임금", "6331": "승진·승급", "6341": "일자리를 그만둘 때"}


def load(folder):
    frames = []
    for w in [25, 26, 27]:
        ww = f"{w:02d}"
        path = f"{folder}/klips{ww}p.xlsx"
        hdr = pc.CalamineWorkbook.from_path(path).get_sheet_by_name("Data").to_python(nrows=1)[0]
        cols = ["pid"] + [f"p{ww}{v}" for v in VARS if f"p{ww}{v}" in hdr]
        df = pd.read_excel(path, engine="calamine", usecols=cols)
        df.columns = ["pid"] + [c[3:] for c in df.columns[1:]]
        df = df.apply(pd.to_numeric, errors="coerce")
        df["year"] = 1997 + w
        frames.append(df)
        print(w, len(df), [v for v in VARS if f"p{ww}{v}" not in hdr], flush=True)
    return pd.concat(frames)


def share(s, ok):
    s = s.dropna()
    s = s[s > 0]
    return {"p": round(float(s.isin(ok).mean()), 3), "n": int(len(s))} if len(s) else None


def stats(x):
    hours = x["1004"].where(x["1004"].between(1, 100))
    ot = x[x["1011"] == 2]
    ot_h = ot["1012"].where(ot["1019"] == 1).where(lambda v: v.between(1, 60))
    tenure = (x.year - x["0301"]).where(x["0301"].between(1950, 2024))
    out = {
        "n": int(len(x)),
        "hours_mean": round(float(hours.mean()), 1),
        "hours_52plus": {"p": round(float((hours.dropna() > 52).mean()), 3), "n": int(hours.notna().sum())},
        "regular": share(x["0317"], [1]),
        "overtime": share(x["1011"], [2]),
        "overtime_hours_week_median": float(ot_h.median()) if ot_h.notna().any() else None,
        "overtime_unpaid": share(ot["1015"], [1]),
        "performance_pay": share(x["1621"], [1]),
        "union_exists": share(x["2501"], [1]),
        "union_member": {"p": round(float((x["2504"] == 1).sum() / x["2501"].isin([1, 2]).sum()), 3), "n": int(x["2501"].isin([1, 2]).sum())},
        "tenure_median": float(tenure.median()),
        "tenure_lt1": round(float((tenure.dropna() < 1).mean()), 3),
        "healthy": share(x["6101"], [1, 2]),
        "exercise_regular": share(x["6154"], [1]),
        "smoke": share(x["6158"], [1]),
        "drink": share(x["6161"], [1]),
        "drink_weekly": {"p": round(float((x["6162"] >= 3).sum() / x["6161"].isin([1, 2, 3]).sum()), 3), "n": int(x["6161"].isin([1, 2, 3]).sum())},
        "job_sat": {lab: {"sat": share(x[v], [1, 2]), "unsat": share(x[v], [4, 5])} for v, lab in SAT.items()},
        "life_sat": {lab: {"sat": share(x[v], [1, 2]), "unsat": share(x[v], [4, 5])} for v, lab in LIFE.items()},
        "discrimination": {lab: share(x[v], [1]) for v, lab in DISC.items() if v in x},
    }
    return out


def main():
    d = load(sys.argv[1])
    w = d[(d["0211"] == 1) & d["0107"].between(20, 59)]
    res = {"meta": {"built": "2026-11-04", "notes": __doc__.strip().splitlines()[3:]},
           "all": stats(w), "all_female": stats(w[w["0101"] == 2]), "all_male": stats(w[w["0101"] == 1]),
           "designer": stats(w[w["0352"] == 285]), "developer": stats(w[w["0352"].isin([222, 223])])}
    for lab, (lo, hi) in {"20s": (20, 29), "30s": (30, 39), "40s": (40, 49), "50s": (50, 59)}.items():
        res[f"all_{lab}"] = stats(w[w["0107"].between(lo, hi)])
    json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ["all", "designer", "developer"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
