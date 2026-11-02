"""data/13, 16, 17 → 프로토타입 입력 game_data.json, 그리고 src.html 에 넣어 index.html 을 만든다.

사용법 (프로젝트 폴더에서):
    python prototype/export_game_data.py

규칙
- 연간 이동: 성별 x 나이대 칸의 n 이 30 미만이면 성별 합계 칸(16_)으로 대체한다.
- 나이별 임금: 임금 응답 n 이 30 미만인 나이대는 바로 앞 나이대 값을 그대로 쓴다.
- 성별 임금 배수: 25~44세 나이대별 (성별 중앙값 / 전체 중앙값)의 평균. 성별 칸 n 20 미만은 뺀다.
"""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)  # noqa: E731
BANDS = ["20~24", "25~29", "30~34", "35~39", "40~44", "45~49", "50~54", "55~59", "60+"]
MIN_N = 30

p17 = json.load(open(D("data", "17_game_params.json")))
p16 = json.load(open(D("data", "16_klips_career_by_occupation.json")))


def carry(values):
    """[(n, median)] → 나이대별 값. n<30 이면 앞 값, 맨 앞이 비면 처음 나오는 유효값."""
    out, last = [], None
    for n, m in values:
        if n >= MIN_N and m is not None:
            last = m
        out.append(last)
    first = next(v for v in out if v is not None)
    return [v if v is not None else first for v in out]


def trans_cell(x):
    return {k: x.get(k, 0.0) for k in ["same_job", "new_job_same_occupation", "other_occupation", "not_employed"]} | {"n": x["n"]}


def role(g):
    k, y, a = p17["klips"][g], p17["yp"][g], p16[g]
    trans, used_fallback = {}, []
    for sex in ["male", "female"]:
        trans[sex] = {}
        for a3 in ["~34", "35~44", "45+"]:
            cell = k["transition"][sex][a3]
            if cell["n"] < MIN_N:
                used_fallback.append(f"{sex} {a3} (n={cell['n']})")
                cell = a["annual_transition"][a3]
            trans[sex][a3] = trans_cell(cell)
    wage = carry([(k["wage_by_age"][b]["n"], k["wage_by_age"][b]["median"]) for b in BANDS])
    ratios = {}
    for sex in ["male", "female"]:
        r = [k["wage_by_sex_age"][sex][b]["median"] / k["wage_by_age"][b]["median"]
             for b in ["25~29", "30~34", "35~39", "40~44"] if k["wage_by_sex_age"][sex][b]["n"] >= 20]
        ratios[sex] = round(sum(r) / len(r), 3)
    re = a["reentry_next_year_from_not_employed"]
    selfinc = carry([(a["by_age"][b]["n"], k["self_income_by_age"][b]) for b in BANDS])
    return {
        "weight": y["n_first_jobs"],
        "female_share": y["female_share_first_job"],
        "start_age": {s: [y["start_age"][s]["q25"], y["start_age"][s]["median"], y["start_age"][s]["q75"]] for s in ["male", "female"]},
        "first_wage": {s: round(y["first_wage_median"][s]["median"], 1) for s in ["male", "female"]},
        "first_size9": {kk: v for kk, v in y["first_job_size9"].items() if kk != "n"},
        "regular_share": y["first_job_regular_share"],
        "quit": {kk: v for kk, v in y["quit_reasons"].items() if kk != "n"},
        "quit_n": y["quit_reasons"]["n"],
        "gap": y["gap_months"],
        "trans": trans,
        "trans_fallback": used_fallback,
        "dest": {kk: v for kk, v in k["other_occupation_destination"].items() if kk != "n"},
        "dest_n": k["other_occupation_destination"]["n"],
        "to_self": k["self_employment"]["wage_to_self_annual"],
        "self_to_wage": k["self_employment"]["self_to_wage_annual"],
        "reentry": {"back": re.get("back_same_occupation", 0), "other": re.get("other_occupation", 0),
                    "still": re.get("still_not_employed", 0), "n": re["n"]},
        "wage_by_age": dict(zip(BANDS, wage)),
        "sex_wage_ratio": ratios,
        "size_mult": {s: v["mult"] for s, v in k["size3_wage_multiplier_25_44"].items()},
        "wage_log_sd": k["wage_log_sd_within_age_25_44"],
        "self_income_by_age": dict(zip(BANDS, selfinc)),
        "sat": k["satisfaction_mean_1to5"],
        "keep_observed": {kk: v["same_occupation"] for kk, v in a["still_in_occupation_after"].items()},
        "self_share_by_age": {b: a["by_age"][b]["self_employed_share"] for b in BANDS},
    }


def planner():
    a = p16["planner"]
    wage = carry([(a["by_age"][b]["n"], a["by_age"][b]["wage_median"]) for b in BANDS])
    return {
        "female_share": 0.626,  # data/14_ planner_proxy gender_female_share
        "trans": {a3: trans_cell(a["annual_transition"][a3]) for a3 in ["~34", "35~44", "45+"]},
        "wage_by_age": dict(zip(BANDS, wage)),
        "first_wage": 250.0,  # data/14_ planner_proxy first_job wage_median
    }


size = {}
with open(D("data", "13_yp2021_firm_size_transition_3band.csv")) as f:
    lab = {"소(1~29)": "S", "중(30~299)": "M", "대(300+)": "L"}
    for r in csv.DictReader(f):
        size.setdefault(lab[r["from_firm_size"]], {})[lab[r["to_firm_size"]]] = float(r["row_share"])

# 사람마다 다른 '떠나는 성향' 배수 (감마분포, 45세부터 해마다 fade 만큼만 차이를 남김).
# prototype/calibrate.js 로 사람을 따라간 두 관찰값에 맞춘 '떠나는 확률' 배수 (2026-11-02 v3).
#   1) 30세 이하에 처음 그 직군으로 관찰된 사람의 1·3·5·10·12·15년 뒤 같은 직군 비율 (10·12·15년은 거의 같은 사람들이라 각각 n/3 무게)
#   2) 나이대별(25~29 ... 50~54) 그 직군이던 사람의 5년 뒤 같은 직군 비율
# v2 는 2020~24 취업자 나이 분포까지 맞추느라 사람마다 차이를 크게 두었는데, 그 결과 30~40대가 5년 동안 95% 남아
#   실제(75~78%)보다 훨씬 오래 남았다. 나이 분포에는 중간에 다른 일에서 들어오는 사람과 신입 규모 변화가 섞여 있어 목표에서 뺐다(확인용).
# 결과: 사람 사이 차이 없음(shape 1000), 떠나는 확률 × 디자이너 0.9, 개발자 0.7.
#   디자이너: 목표 유지 73/66/56/23/33/45%, 5년 58/51/60/68/71/62% → 게임 85/65/50/27/22/17%, 50/50/63/62/68/71%
#   개발자:   목표 유지 87/77/70/69/57/64%, 5년 70/75/78/75/89/88% → 게임 92/81/72/54/51/46%, 72/73/83/82/86/84%
HETERO = {"designer": {"mean": 0.9, "shape": 1000, "fade": 1},
          "developer": {"mean": 0.7, "shape": 1000, "fade": 1}}
# 나이대별 5년 유지율 [값, n] (보정 목표, scripts/klips_keep_by_age_band.py: 그 나이대에 처음 그 직군으로 보인 해 기준)
KEEP_BAND = {"designer": {"25": [0.58, 43], "30": [0.51, 45], "35": [0.60, 48], "40": [0.68, 28], "45": [0.71, 14], "50": [0.62, 8]},
             "developer": {"25": [0.70, 64], "30": [0.75, 91], "35": [0.78, 101], "40": [0.75, 68], "45": [0.89, 37], "50": [0.88, 16]}}
# 노동패널에서 30세 이하에 처음 그 직군으로 관찰된 사람의 k년 뒤 같은 직군 비율 [값, n] (보정 목표)
KEEP_YOUNG = {"designer": {"1y": [0.73, 92], "3y": [0.66, 67], "5y": [0.56, 57], "10y": [0.23, 30], "12y": [0.33, 24], "15y": [0.45, 11]},
              "developer": {"1y": [0.87, 158], "3y": [0.77, 110], "5y": [0.70, 83], "10y": [0.69, 45], "12y": [0.57, 35], "15y": [0.64, 22]}}
# 2020~2024 노동패널 취업자 나이 분포 (60세 미만으로 다시 나눔), n
AGE_DIST = {"designer": {"share": [0.244, 0.352, 0.313, 0.090], "n": 369},
            "developer": {"share": [0.163, 0.356, 0.337, 0.143], "n": 1082}}

# 결혼·이혼·신입 규모 (scripts/build_life_params.py → data/18_)
life = json.load(open(D("data", "18_life_params.json")))
# 노동패널 결혼 확률은 결혼한 사람이 조사에서 빠지는 탓에 낮게 잡힌다. 2020 인구총조사 30대 미혼율
# (남 50.8%, 여 33.6%)에 맞도록 성별 배수를 곱한다(2026-11-02 이분법으로 맞춤). 평균 첫 결혼 나이는 남 33.5, 여 31.6세가 된다.
MARRY_SCALE = {"male": 1.6, "female": 1.67}
LIFE = {
    "marry": {s: {int(a): v["p"] for a, v in life["klips"]["marry"][s].items()} for s in ["male", "female"]},
    "marry_n": {s: {int(a): v["n"] for a, v in life["klips"]["marry"][s].items()} for s in ["male", "female"]},
    "marry_scale": MARRY_SCALE,
    "divorce": {s: {k: v["p"] for k, v in life["klips"]["divorce"][s].items()} for s in ["male", "female"]},
    "entrants": life["yp_entrants"],
}

game = {
    "built": "2026-11-02",
    "life": LIFE,
    # 일반 직장인(임금근로자) 비교 통계 (scripts/build_worker_stats.py → data/19_)
    "worker": {k: v for k, v in json.load(open(D("data", "19_worker_stats.json"))).items() if k in ["all", "all_male", "all_female", "designer"]},
    "roles": {g: role(g) | {"hetero": HETERO[g], "keep_young": KEEP_YOUNG[g], "keep_band": KEEP_BAND[g], "age_dist": AGE_DIST[g]} for g in ["designer", "developer"]}
             | {
              "planner": planner()},
    "size_move": size,
}
out = D("prototype", "game_data.json")
json.dump(game, open(out, "w"), ensure_ascii=False, indent=1)

src = open(D("prototype", "src.html")).read()
html = src.replace("/*GAME_DATA*/{}", json.dumps(game, ensure_ascii=False, separators=(",", ":")))
open(D("prototype", "index.html"), "w").write(html)
print("fallback cells:", {g: game["roles"][g]["trans_fallback"] for g in ["designer", "developer"]})
print("wage:", {g: game["roles"][g]["wage_by_age"] for g in game["roles"]})
print("sex ratio:", {g: game["roles"][g]["sex_wage_ratio"] for g in ["designer", "developer"]})
