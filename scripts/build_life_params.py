"""게임의 가정·생활 사건용 확률표 (결혼, 이혼) 와 한 해 신입 규모 추정.

사용법:
    python build_life_params.py "<KLIPS 1-27차 release (Excel) 폴더>" <YP2021 직업력 csv> "<YP2021_EXCEL 폴더>" <출력 JSON>

1) 결혼·이혼 (한국노동패널 12~27차, 개인용 p__5501 혼인상태: 1 미혼 2 기혼 3 별거 4 이혼 5 사별)
   - 올해 미혼인 사람이 다음 해 기혼(2)인 비율 = 연간 첫 결혼 확률. 성별 x 나이(2세 단위).
   - 올해 기혼인 사람이 다음 해 이혼·별거(3, 4)인 비율 = 연간 이혼 확률. 성별 x 나이대.
   - 전체 응답자 기준(직군 무관). 디자이너·개발자(KSCO 285, 222, 223)만 따로 본 값도 함께 적는다.
2) 한 해 신입 규모 (청년패널 YP2021 1차 횡단 가중치 weight01_c)
   - 1993~1996년생 중 첫 일자리가 디자이너(4151·4154·4155)·개발자인 사람의 가중 합 / 출생연도 수.
   - 2024년까지 관찰된 첫 일자리만 센다. 늦게 시작하는 사람이 빠지므로 아래쪽 추정이다.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
import python_calamine as pc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yp2021_jobhis_occupations as yj  # noqa: E402

SEX = {1: "male", 2: "female"}


def klips_marital(folder):
    frames = []
    for w in range(12, 28):
        ww = f"{w:02d}"
        path = f"{folder}/klips{ww}p.xlsx"
        hdr = pc.CalamineWorkbook.from_path(path).get_sheet_by_name("Data").to_python(nrows=1)[0]
        want = [f"p{ww}{v}" for v in ["0101", "0107", "5501", "0352"]]
        cols = ["pid"] + [c for c in want if c in hdr]
        df = pd.read_excel(path, engine="calamine", usecols=cols)
        df.columns = ["pid"] + [c[3:] for c in df.columns[1:]]
        df = df.apply(pd.to_numeric, errors="coerce")
        df["wave"] = w
        frames.append(df)
        print(w, len(df), flush=True)
    d = pd.concat(frames).sort_values(["pid", "wave"])
    nx = d.groupby("pid").shift(-1)
    d["n_mar"] = nx["5501"].where(nx.wave == d.wave + 1)
    d = d[d.n_mar.notna() & d["5501"].between(1, 5)]
    d["playocc"] = d["0352"].isin([285, 222, 223])
    out = {"marry": {}, "divorce": {}, "marry_playocc": {}}
    for sex, lab in SEX.items():
        x = d[(d["0101"] == sex) & (d["5501"] == 1)]
        tab = {}
        for a in range(20, 50, 2):
            y = x[x["0107"].between(a, a + 1)]
            tab[f"{a}"] = {"n": int(len(y)), "p": round(float((y.n_mar == 2).mean()), 4) if len(y) else None}
        out["marry"][lab] = tab
        # 디자이너·개발자만 (나이대 넓게)
        xo = x[x.playocc]
        out["marry_playocc"][lab] = {
            k: {"n": int(len(y)), "p": round(float((y.n_mar == 2).mean()), 4) if len(y) else None}
            for k, y in {"25~29": xo[xo["0107"].between(25, 29)], "30~34": xo[xo["0107"].between(30, 34)],
                         "35~39": xo[xo["0107"].between(35, 39)]}.items()}
        m = d[(d["0101"] == sex) & (d["5501"] == 2)]
        out["divorce"][lab] = {
            k: {"n": int(len(y)), "p": round(float(y.n_mar.isin([3, 4]).mean()), 4)}
            for k, y in {"~34": m[m["0107"] <= 34], "35~44": m[m["0107"].between(35, 44)],
                         "45~59": m[m["0107"].between(45, 59)]}.items()}
    # 같은 사람들 전체 기준 생애 기혼 비율 (40~44세 단면)
    out["ever_married_40_44"] = {lab: round(float((d[(d["0101"] == s) & d["0107"].between(40, 44)]["5501"] != 1).mean()), 3)
                                 for s, lab in SEX.items()}
    return out


def yp_entrants(jobhis, yp_folder):
    j, s = yj.build_spells(yj.load(jobhis))
    w = pd.read_excel(f"{yp_folder}/YP2021_w01.xlsx", engine="calamine", usecols=["sampid", "BIRTHy", "weight01_c"])
    first = s.sort_values(["sampid", "jobseq"]).groupby("sampid").head(1).merge(w, on="sampid", how="left")
    lo, hi = 1993, 1996
    k = hi - lo + 1
    res = {"cohorts": f"{lo}~{hi}년생", "births_per_year_weighted": int(round(w[w.BIRTHy.between(lo, hi)].weight01_c.sum() / k, -3))}
    for g, key in {"designer": "designer_core", "developer": "developer"}.items():
        f = first[yj.GROUPS[key](first.occ) & first.BIRTHy.between(lo, hi)]
        res[g] = {"n": int(len(f)), "per_year": int(round(f.weight01_c.sum() / k, -2))}
    return res


def main():
    out = {"meta": {"built": "2026-11-02", "notes": __doc__.strip().splitlines()[2:]},
           "klips": klips_marital(sys.argv[1]), "yp_entrants": yp_entrants(sys.argv[2], sys.argv[3])}
    json.dump(out, open(sys.argv[4], "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
