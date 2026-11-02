"""청년패널 YP2021 직업력 자료로 디자이너·개발자·기획자의 커리어 확률을 계산한다.

사용법:
    python yp2021_jobhis_occupations.py <YP2021_JOBHIS_0608.xlsx 또는 .csv> <출력 JSON>

자료 구조 (직업력 코드북_0608.xlsx):
    한 행 = 응답자(sampid) x 조사차수(jobwave) x 일자리. 같은 일자리는 jobseq(일자리 고유번호)가 같다.
    jobwave 0 = 1차 조사 당시 현재 일자리의 이전 일자리 회고, 1~4 = 2021~2024년 조사.
    JOB1/2 시작 년/월, JOB67/68 종료 년/월(임금근로자만), JOB69 그만둔 이유,
    JOB6 직업 KECO 세분류, JOB13 기업체 규모 9구간, JOB50 정규직 여부,
    JOB56 급여 단위(1 연봉, 2 월평균, ...), JOB57 급여 금액(만원), JOB17~29 만족도(1~5).

직군 정의 (KECO 세분류):
    디자이너  4151~4155 (제품·패션·실내장식·시각·미디어콘텐츠)
    디자이너(게임 대상) 4151, 4154, 4155 (패션·실내장식 제외)
    개발자    1320, 1331~1339 (컴퓨터시스템 전문가, 소프트웨어 개발자)
    기획자    0241, 0243, 0244, 0261 (광고·홍보, 상품기획, 행사기획, 경영기획 사무원)
              ※ IT 서비스 기획자만 따로 나누는 코드가 없다. 대리 지표.

추정 방식:
    일자리 종료 날짜가 없으면 마지막으로 관찰된 조사 해 7월에 중도절단(관찰 끝)으로 본다.
    조사 월은 자료에 없어 7월로 가정했다.
    근속 생존은 카플란-마이어. 비임금근로자는 종료 날짜가 없어 근속 계산에서 뺀다.
"""
import json
import sys

import numpy as np
import pandas as pd

GROUPS = {
    "designer": lambda c: c.between(4151, 4155),
    "designer_core": lambda c: c.isin([4151, 4154, 4155]),
    "developer": lambda c: (c == 1320) | c.between(1331, 1339),
    "planner_proxy": lambda c: c.isin([241, 243, 244, 261]),
    "all": lambda c: c.notna(),
}
SIZE3 = {1: "S", 2: "S", 3: "S", 4: "M", 5: "M", 6: "M", 7: "L", 8: "L", 9: "L"}
SIZE9 = ["1~4", "5~9", "10~29", "30~49", "50~99", "100~299", "300~499", "500~999", "1000+"]
QUIT = {
    1: "학업 계속", 2: "전공 불일치", 3: "적성 불일치", 4: "기술 부족", 5: "동료·상사 불화",
    6: "보수·승진 불만", 7: "근무조건·환경", 8: "전망 없음", 9: "창업·개인사업", 10: "폐업·해고·사업종료",
    11: "계약 만료", 12: "건강", 13: "육아·가사", 14: "군입대", 97: "기타",
}
SAT = {
    "JOB17": "전반", "JOB18": "업무내용", "JOB20": "자기발전", "JOB21": "임금", "JOB22": "고용안정",
    "JOB23": "자율성", "JOB25": "장래성", "JOB27": "인간관계", "JOB28": "인사공정성", "JOB29": "복리후생",
}


def load(path):
    if path.endswith(".csv"):
        return pd.read_csv(path, low_memory=False)
    return pd.read_excel(path, engine="calamine")


def monthly_wage(row_unit, row_amt):
    w = pd.Series(np.nan, index=row_unit.index)
    w[row_unit == 2] = row_amt[row_unit == 2]
    w[row_unit == 1] = row_amt[row_unit == 1] / 12
    return w.where((w >= 30) & (w <= 3000))  # 비정상값 제거 (월 30만~3000만 원)


def build_spells(j):
    j = j.copy()
    j["wage_m"] = monthly_wage(j["JOB56"], j["JOB57"])
    j["obs_year"] = 2020 + j["jobwave"].clip(lower=1)
    j = j.sort_values(["sampid", "jobseq", "jobwave"])
    g = j.groupby(["sampid", "jobseq"])
    s = g.agg(
        occ=("JOB6", "first"), start_y=("JOB1", "first"), start_m=("JOB2", "first"),
        end_y=("JOB67", "last"), end_m=("JOB68", "last"), quit=("JOB69", "last"),
        size=("JOB13", "first"), regular=("JOB50", "first"), status=("JOB16", "first"),
        wage_first=("wage_m", "first"), last_obs=("obs_year", "max"), birth=("BIRTHy", "first"),
        gender=("gender", "first"),
        **{k: (k, "mean") for k in SAT},
    ).reset_index()
    start = s.start_y * 12 + s.start_m.fillna(6) - 1
    ended = s.end_y.notna()
    end = np.where(ended, s.end_y * 12 + s.end_m.fillna(6) - 1, s.last_obs * 12 + 6)
    s["months"] = np.maximum(end - start, 0)
    s["ended"] = ended
    s["start_idx"], s["end_idx"] = start, end
    s["wage_worker"] = s.status.between(1, 3) | s.status.isna() & s.regular.notna()
    return j, s


def km(months, ended, points=(6, 12, 24, 36, 48, 60)):
    """카플란-마이어 근속 생존율."""
    d = pd.DataFrame({"t": months, "e": ended.astype(int)}).sort_values("t")
    surv, out, n = 1.0, {}, len(d)
    at_risk = n
    for t, grp in d.groupby("t"):
        for p in points:
            if p not in out and t > p:
                out[p] = surv
        ev = grp.e.sum()
        if at_risk > 0:
            surv *= 1 - ev / at_risk
        at_risk -= len(grp)
    for p in points:
        out.setdefault(p, surv if at_risk > 0 else None)
    return {f"{p}m": (round(v, 3) if v is not None else None) for p, v in out.items()}


def group_of(code):
    for name in ["designer", "developer", "planner_proxy"]:
        if GROUPS[name](pd.Series([code])).iloc[0]:
            return name
    return "other"


def summarize(j, s, name):
    sel = GROUPS[name](s.occ)
    sp = s[sel]
    res = {"spells": int(len(sp)), "persons": int(sp.sampid.nunique())}

    # 근속 생존 (임금근로자)
    ww = sp[sp.wage_worker]
    res["tenure_survival"] = {"n": int(len(ww)), "ended": int(ww.ended.sum()), **km(ww.months, ww.ended)}
    res["tenure_months_ended_median"] = float(ww.loc[ww.ended, "months"].median()) if ww.ended.any() else None

    # 퇴사 사유
    q = sp.loc[sp.ended, "quit"].map(QUIT).value_counts()
    res["quit_reasons"] = {"n": int(q.sum()), "share": (q / q.sum()).round(3).to_dict()}

    # 다음 일자리: 같은 직군 유지 / 다른 직군, 공백 기간
    s2 = s.sort_values(["sampid", "jobseq"]).copy()
    s2["next_occ"] = s2.groupby("sampid").occ.shift(-1)
    s2["next_start"] = s2.groupby("sampid").start_idx.shift(-1)
    s2["next_size"] = s2.groupby("sampid")["size"].shift(-1)
    nx = s2[GROUPS[name](s2.occ) & s2.next_occ.notna()]
    nxg = nx.next_occ.map(group_of).value_counts()
    res["next_job_group"] = {"n": int(len(nx)), "share": (nxg / nxg.sum()).round(3).to_dict()}
    gap = (nx.next_start - nx.end_idx)[nx.ended]
    gap = gap.clip(lower=0)
    res["gap_months_between_jobs"] = {
        "n": int(gap.notna().sum()), "median": float(gap.median()) if len(gap) else None,
        "share_le_1m": round(float((gap <= 1).mean()), 3) if len(gap) else None,
        "share_gt_6m": round(float((gap > 6).mean()), 3) if len(gap) else None,
    }
    ok = nx["size"].between(1, 9) & nx.next_size.between(1, 9)
    if ok.any():
        ct = pd.crosstab(nx.loc[ok, "size"].map(SIZE3), nx.loc[ok, "next_size"].map(SIZE3))
        res["size3_transition"] = {"n": int(ok.sum()), "counts": ct.to_dict(orient="index")}

    # 관찰된 첫 일자리
    first = s.sort_values(["sampid", "jobseq"]).groupby("sampid").head(1)
    f = first[GROUPS[name](first.occ)]
    sz = f["size"].dropna().astype(int).map(dict(enumerate(SIZE9, 1))).value_counts()
    res["first_job"] = {
        "n": int(len(f)),
        "firm_size_share": (sz / sz.sum()).reindex(SIZE9).fillna(0).round(3).to_dict(),
        "wage_median": float(f.wage_first.median()) if f.wage_first.notna().any() else None,
        "regular_share": round(float((f.regular == 1).sum() / f.regular.isin([1, 2]).sum()), 3)
        if f.regular.isin([1, 2]).any() else None,
    }

    # 경력 연차별 월임금 (차수 행 기준, 경력 = 관찰 해 - 그 사람 첫 일자리 시작 해)
    first_y = s.groupby("sampid").start_y.min()
    rows = j[GROUPS[name](j.JOB6) & j.wage_m.notna() & (j.jobwave >= 1)].copy()
    rows["exp"] = (rows.obs_year - rows.sampid.map(first_y)).clip(lower=0)
    rows["exp_band"] = pd.cut(rows.exp, [-1, 0, 1, 2, 3, 5, 20], labels=["0", "1", "2", "3", "4~5", "6+"])
    wb = rows.groupby("exp_band", observed=False).wage_m.agg(["count", "median"])
    res["wage_by_experience"] = {
        k: {"n": int(v["count"]), "median": (round(float(v["median"]), 1) if v["count"] else None)}
        for k, v in wb.iterrows()
    }

    # 만족도 평균 (1~5, 9 등 무응답 제외 위해 행 단위로 다시 계산)
    sr = j[GROUPS[name](j.JOB6)]
    res["satisfaction_mean"] = {
        lab: round(float(sr[c].where(sr[c].between(1, 5)).mean()), 2) for c, lab in SAT.items()
    }
    res["gender_female_share"] = round(float((sp.gender == 2).mean()), 3)
    return res


def main():
    j = load(sys.argv[1])
    j, s = build_spells(j)
    out = {
        "meta": {
            "source": "청년패널 YP2021 1-4차 직업력 자료 (YP2021_JOBHIS_0608), 비가중",
            "groups": {
                "designer": "KECO 4151~4155", "designer_core": "KECO 4151, 4154, 4155 (패션·실내장식 제외)",
                "developer": "KECO 1320, 1331~1339", "planner_proxy": "KECO 0241, 0243, 0244, 0261 (IT 서비스 기획 코드 없음, 대리 지표)",
                "all": "전체 청년",
            },
            "notes": [
                "청년(2021년 15~29세) 표본이라 경력 초기(대략 0~6년)만 관찰된다.",
                "근속 생존은 임금근로자 일자리만. 종료 날짜 없으면 마지막 조사 해 7월에 관찰 끝으로 처리(조사 월은 가정).",
                "첫 일자리 = 패널에서 관찰된 첫 일자리. 2021년 이전 이력은 직전 일자리 하나만 회고되어 실제 첫 직장이 아닐 수 있다.",
                "기업체 규모 = JOB13. 월임금 = 월평균 또는 연봉/12, 30만~3000만 원만.",
            ],
        }
    }
    for name in GROUPS:
        out[name] = summarize(j, s, name)
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
