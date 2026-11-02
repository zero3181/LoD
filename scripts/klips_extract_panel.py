"""KLIPS 12~27차 개인 파일에서 커리어 분석용 변수만 뽑아 긴 패널(사람 x 연도) CSV로 저장한다.

사용법:
    python klips_extract_panel.py "<1-27차 release (Excel) 폴더>" <출력 CSV>

변수 (한국노동패널 1~27차년도 통합코드북 '개인용' 시트, KLI 2025-12-23 공개):
    p__0101 성별(1 남, 2 여)          p__0107 만나이
    p__0201 취업자(1)/미취업자(2)      p__0211 취업형태(1 임금, 2 내 사업, 3 무급가족)
    p__0301/0302 주된일자리 취업 년/월  p__0314 종사상지위(1 상용 2 임시 3 일용 4 고용주·자영 5 무급가족)
    p__0317 정규직(1)/비정규직(2)      p__0352 직종 KSCO 7차 3자리 (12차부터)
    p__0403 기업 전체 종업원수 범주(1 1~4 ... 10 1000+, 11 모름)
    p__1642 임금근로자 월평균임금(만원) p__1672 비임금 월평균 소득(만원)
    p__4311~4319 요인별 직무만족(1 매우 만족 ... 5 매우 불만족)
    p__4301 "현재 일에 만족"(1 전혀 그렇지 않다 ... 5 매우 그렇다)
조사연도 = 1997 + 차수 (12차 = 2009년).
"""
import sys

import pandas as pd
import python_calamine as pc

VARS = ["0101", "0107", "0201", "0211", "0301", "0302", "0314", "0317", "0352", "0403",
        "1642", "1672", "4301"] + [f"43{i}" for i in range(11, 20)]


def main():
    folder, out = sys.argv[1], sys.argv[2]
    frames = []
    for w in range(12, 28):
        ww = f"{w:02d}"
        path = f"{folder}/klips{ww}p.xlsx"
        hdr = pc.CalamineWorkbook.from_path(path).get_sheet_by_name("Data").to_python(nrows=1)[0]
        cols = ["pid"] + [f"p{ww}{v}" for v in VARS if f"p{ww}{v}" in hdr]
        df = pd.read_excel(path, engine="calamine", usecols=cols)
        df.columns = ["pid"] + [c[3:] for c in df.columns[1:]]
        df = df.apply(pd.to_numeric, errors="coerce")
        df.insert(1, "wave", w)
        df.insert(2, "year", 1997 + w)
        frames.append(df)
        print(w, df.shape, "missing:", [v for v in VARS if v not in df.columns], flush=True)
    pd.concat(frames).to_csv(out, index=False)


if __name__ == "__main__":
    main()
