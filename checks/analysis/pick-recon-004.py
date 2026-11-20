import random, json
from pathlib import Path
from collections import defaultdict
from crossprice.overlap import load_catalog
from crossprice.match import to_offer, candidate_pairs
d=Path("checks/results/recon-002/catalogs")
sk=["ayla-beauty","cos-bar","credo-beauty","dermsilk","integrity-botanicals","ohlolly","safe-chic","soko-glam","the-detox-market","thirteen-lune"]
rows=[r for s in sk for r in load_catalog(d/f"{s}.csv.gz", s)]
rb={r.key:r for r in rows}
offers=[to_offer(r) for r in rows]
pairs=[p for p in candidate_pairs(offers) if p.reason=="mutual best" and p.score>=0.5]
# one pair per product pair
seen=set(); uniq=[]
for p in pairs:
    k=(p.a[0],rb[p.a].product_id,p.b[0],rb[p.b].product_id)
    if k in seen: continue
    seen.add(k); uniq.append(p)
bands=[(0.5,0.6),(0.6,0.7),(0.7,0.8),(0.8,1.01)]
random.seed(20261120)
cap=18; load=defaultdict(set); chosen=[]
pools={b:[p for p in uniq if b[0]<=p.score<b[1]] for b in bands}
for b in pools: random.shuffle(pools[b])
progress=True
while progress:
    progress=False
    for b in bands:
        while pools[b]:
            p=pools[b].pop()
            ha,hb=rb[p.a].handle,rb[p.b].handle
            ra,rbb=p.a[0],p.b[0]
            need_a = ha not in load[ra]; need_b = hb not in load[rbb]
            if len(load[ra])+need_a>cap or len(load[rbb])+need_b>cap: continue
            load[ra].add(ha); load[rbb].add(hb); chosen.append((b,p)); progress=True
            break
from collections import Counter
print(len(chosen), Counter(b for b,_ in chosen), {k:len(v) for k,v in load.items()})
json.dump({k:sorted(v) for k,v in sorted(load.items())}, open("/tmp/handles.json","w"), indent=1)
