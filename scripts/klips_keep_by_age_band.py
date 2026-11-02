import sys
sys.path.insert(0, "/Users/yk/Dev/BeDesigner/designer-game-handoff/scripts")
import pandas as pd
import klips_career_by_occupation as kc
d = kc.add_next(kc.prep(sys.argv[1]))
st = d.set_index(["pid","wave"]).grp
print(d.grp.value_counts().to_dict())
for g in ["developer","designer"]:
    r = d[d.grp==g]
    print("==", g)
    for lo,hi in [(25,29),(30,34),(35,39),(40,44),(45,49),(50,54)]:
        # 이 나이대에 그 직군으로 처음 보인 해 (사람당 1번)
        x = r[r["0107"].between(lo,hi)].groupby("pid").head(1)
        out=[]
        for k in [5,10]:
            later = st.reindex(list(zip(x.pid, x.wave+k))).dropna()
            out.append(f"{k}y {(later==g).mean():.0%} (n={len(later)})")
        print(f"{lo}-{hi}세 그 직군 → ", " | ".join(out), " start n", len(x))
