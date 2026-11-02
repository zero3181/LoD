"""청년패널 YP2021 1~4차에서 디자이너 집계와 규모 이동표를 다시 계산한다.

사용법:
    python yp2021_designer_check.py <YP2021_w01~w04 CSV가 있는 폴더>

입력 CSV는 고용정보원 엑셀 파일을 UTF-8 CSV로 변환한 것 (파일명 YP2021_w01.csv ~ w04.csv).
엑셀을 openpyxl로 바로 열면 'synchVertical' 오류가 나서 LibreOffice로 변환했다:
    soffice --headless --convert-to csv:"Text - txt - csv (StarCalc)":44,34,76 YP2021_w0*.xlsx

변수 (YP2021 1-4차 조사 코드북_0227.xlsx 'C(경제활동상태)' 시트로 확인, 2026-11-02):
    y{w}c106  현재 일자리 직업 KECO   (디자이너 4151 제품, 4152 패션, 4153 실내장식, 4154 시각, 4155 미디어콘텐츠)
    y{w}c106x 현재 일자리 직업 KSCO   (디자이너 2951~2955, 순서 동일)
    y{w}c109  사업체(사업장) 규모 9구간 (1:1~4명 ... 9:1000명 이상) - 다른 에이전트가 사용
    y{w}c110  기업체 규모 9구간 (같은 구간) - 게임에는 이것을 쓴다
              원자료에서도 c110 < c109 인 경우는 1차 5,361명 중 2명뿐.
    y{w}c111  종사상 지위 (1 상용, 2 임시, 3 일용, 4 고용원 있는 자영업, 5 고용원 없는 자영업, 6 무급가족)
    y{w}c112  [임] 지난 조사 이후 새 일자리 여부 (1 예, 2 같은 일자리), 2차부터
    w{w}wage_now  현재 월평균 임금 (만원)
"""
import sys

import pandas as pd

WAVES = ["01", "02", "03", "04"]


def load(folder):
    return {
        w: pd.read_csv(f"{folder}/YP2021_w{w}.csv", low_memory=False).set_index("sampid")
        for w in WAVES
    }


def num(s):
    return pd.to_numeric(s, errors="coerce")


def band3(s):
    return pd.cut(s, [0, 3.5, 6.5, 9.5], labels=["소(1~29)", "중(30~299)", "대(300+)"])


def current_designers(W):
    for w in WAVES:
        df = W[w]
        is_d = num(df[f"y{w}c106"]).between(4151, 4155)
        wage = num(df[f"w{w}wage_now"])
        wage = wage[is_d & (wage > 0)]
        size = num(df.loc[is_d, f"y{w}c109"]).value_counts().sort_index().astype(int).to_dict()
        print(f"wave {w}: designers={int(is_d.sum())} wage_median={wage.median():.1f} size(c109)={size}")


def transitions(W, rule="before", size_var="c109"):
    """rule: before=이직 전 디자이너, after=이직 후 디자이너, both=전후 모두."""
    frames = []
    for a, b in zip(WAVES, WAVES[1:]):
        A, B = W[a], W[b]
        ids = A.index.intersection(B.index)
        d0 = num(A.loc[ids, f"y{a}c106"]).between(4151, 4155)
        d1 = num(B.loc[ids, f"y{b}c106"]).between(4151, 4155)
        is_d = {"before": d0, "after": d1, "both": d0 & d1}[rule]
        moved = num(B.loc[ids, f"y{b}c112"]) == 1
        s0 = num(A.loc[ids, f"y{a}{size_var}"])
        s1 = num(B.loc[ids, f"y{b}{size_var}"])
        ok = is_d & moved & (s0 > 0) & (s1 > 0)
        frames.append(pd.DataFrame({"from": band3(s0[ok]), "to": band3(s1[ok])}))
    x = pd.concat(frames)
    print(f"\n[{rule}, {size_var}] pairs={len(x)}")
    print(pd.crosstab(x["from"], x["to"], normalize="index").round(2))


BANDS9 = ["1~4", "5~9", "10~29", "30~49", "50~99", "100~299", "300~499", "500~999", "1000+"]


def all_movers(W, size_var="c109", wage_only=False):
    """전체 청년 이직자(c112=1)의 9구간 규모 이동 행렬. 차수 쌍(1→2, 2→3, 3→4)을 합친다.
    wage_only=True 면 이직 전후 모두 임금근로자(c111 1~3)만."""
    frames = []
    for a, b in zip(WAVES, WAVES[1:]):
        A, B = W[a], W[b]
        ids = A.index.intersection(B.index)
        moved = num(B.loc[ids, f"y{b}c112"]) == 1
        s0 = num(A.loc[ids, f"y{a}{size_var}"])
        s1 = num(B.loc[ids, f"y{b}{size_var}"])
        ok = moved & s0.between(1, 9) & s1.between(1, 9)
        if wage_only:
            ok &= num(A.loc[ids, f"y{a}c111"]).between(1, 3) & num(B.loc[ids, f"y{b}c111"]).between(1, 3)
        frames.append(pd.DataFrame({"from": s0[ok].astype(int), "to": s1[ok].astype(int)}))
    x = pd.concat(frames)
    counts = pd.crosstab(x["from"], x["to"]).reindex(index=range(1, 10), columns=range(1, 10), fill_value=0)
    counts.index = counts.columns = BANDS9
    return counts


def show_all_movers(W):
    for size_var in ["c109", "c110"]:
        for wage_only in [False, True]:
            c = all_movers(W, size_var, wage_only)
            label = "임금근로자만" if wage_only else "전체"
            print(f"\n[전체 청년 이직자, {size_var}, {label}] pairs={int(c.values.sum())}")
            print("행 합계:", c.sum(axis=1).to_dict())
            print((c.div(c.sum(axis=1), axis=0)).round(3).to_string())


if __name__ == "__main__":
    W = load(sys.argv[1])
    current_designers(W)
    for size_var in ["c109", "c110"]:
        for rule in ["after", "before", "both"]:
            transitions(W, rule, size_var)
    show_all_movers(W)
