"""Build the prebuilt building data (data/*.json) for Hus för hus from an OpenStreetMap .pbf extract.

Mirrors the browser loader in index.html (toFeature, matchPlaces, enrichWiki) so the
features have exactly the shape the app would otherwise download from Overpass.

usage: python build_buildings.py <extract.osm.pbf> <out-dir>
   e.g. python build_buildings.py Stockholm.osm.pbf data
Extract: https://download.bbbike.org/osm/bbbike/Stockholm/Stockholm.osm.pbf (needs: pip install osmium)
"""
import json, math, re, sys, time, urllib.request, urllib.parse
import osmium

BOUNDS = dict(s=59.225, w=17.76, n=59.43, e=18.20)
CELL_W, CELL_H = 0.025, 0.0125
NOW = time.gmtime().tm_year
CACHE_VERSION = 4
YEAR_KEYS = ["start_date", "building:start_date", "construction_date", "year_of_construction", "building:year", "year_built"]
PLACE_KEYS = ["amenity", "tourism", "shop", "office", "historic", "leisure", "craft"]
UA = "hus-for-hus-build/1.0 (https://github.com/kanaaraman/hus-for-hus-air)"

X0, X1 = math.floor(BOUNDS["w"] / CELL_W), math.floor(BOUNDS["e"] / CELL_W)
Y0, Y1 = math.floor(BOUNDS["s"] / CELL_H), math.floor(BOUNDS["n"] / CELL_H)
GW, GE, GS, GN = X0 * CELL_W, (X1 + 1) * CELL_W, Y0 * CELL_H, (Y1 + 1) * CELL_H   # the loader's cell grid
CELLS = [f"{x}_{y}" for x in range(X0, X1 + 1) for y in range(Y0, Y1 + 1)]


def r6(v): return round(v * 1e6) / 1e6
def inside_grid(x, y): return GW <= x <= GE and GS <= y <= GN


def parse_year(v):
    if not v: return None
    v = str(v).strip()
    c = re.match(r"^(?:~|late |early |mid )?\s*C(\d{1,2})\b", v, re.I)
    if c: return (int(c.group(1)) - 1) * 100 + 50
    m = re.search(r"(\d{4})", v)
    if m and 1000 <= int(m.group(1)) <= NOW: return int(m.group(1))
    return None


def in_ring(x, y, ring):
    ins, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi: ins = not ins
        j = i
    return ins


def ring_coords(r): return [[r6(n.lon), r6(n.lat)] for n in r]


feats, places = [], []
fp = osmium.FileProcessor(sys.argv[1]).with_locations().with_areas()
for o in fp:
    tg = {t.k: t.v for t in o.tags}
    if not tg: continue
    if o.is_area():
        if "building" in tg:
            polys = []
            for outer in o.outer_rings():
                ring = ring_coords(outer)
                if len(ring) < 4: continue
                polys.append([ring] + [ring_coords(i) for i in o.inner_rings(outer)])
            if not polys: continue
            outer = polys[0][0]
            cx = r6(sum(c[0] for c in outer) / len(outer)); cy = r6(sum(c[1] for c in outer) / len(outer))
            if not in_ring(cx, cy, outer): cx, cy = outer[0]
            if not inside_grid(cx, cy): continue
            p = {"i": ("w" if o.from_way() else "r") + str(o.orig_id()), "cx": cx, "cy": cy}
            for k in YEAR_KEYS:
                y = parse_year(tg.get(k))
                if y: p["y"] = y; p["s"] = "osm"; break
            if tg.get("name"): p["n"] = tg["name"]
            if tg.get("addr:street"): p["a"] = " ".join(v for v in (tg["addr:street"], tg.get("addr:housenumber")) if v)
            try: h = float(tg.get("height", "").replace("m", "").strip())
            except ValueError: h = 0
            try: lv = float(tg.get("building:levels", ""))
            except ValueError: lv = 0
            if h > 0: p["h"] = h
            elif lv > 0: p["h"] = round((lv * 3.2 + 1) * 10) / 10
            if re.fullmatch(r"Q\d+", tg.get("wikidata", "")): p["q"] = tg["wikidata"]
            geom = {"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1 else {"type": "MultiPolygon", "coordinates": polys}
            feats.append({"type": "Feature", "properties": p, "geometry": geom})
        elif tg.get("name") and any(k in tg for k in PLACE_KEYS):     # a named shop/museum mapped as an area
            xs, ys = [], []
            for outer in o.outer_rings():
                for n in outer: xs.append(n.lon); ys.append(n.lat)
            if xs: places.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, tg))
    elif o.is_node() and o.location.valid():
        if (tg.get("name") and any(k in tg for k in PLACE_KEYS)) or ("addr:street" in tg and "addr:housenumber" in tg):
            places.append((o.location.lon, o.location.lat, tg))
print(f"{len(feats)} buildings, {len(places)} places/addresses", file=sys.stderr)

# grid index so "which building is this point in?" is fast (same as pipAdd/featureAt)
PC = 0.002
PIP = {}
for f in feats:
    g = f["geometry"]; ring = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
    xs = [c[0] for c in ring]; ys = [c[1] for c in ring]
    for x in range(math.floor(min(xs) / PC), math.floor(max(xs) / PC) + 1):
        for y in range(math.floor(min(ys) / PC), math.floor(max(ys) / PC) + 1):
            PIP.setdefault((x, y), []).append(f)


def feature_at(x, y):
    for f in PIP.get((math.floor(x / PC), math.floor(y / PC)), []):
        g = f["geometry"]; polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        if any(in_ring(x, y, p[0]) for p in polys): return f
    return None


for x, y, tg in places:                       # matchPlaces
    f = feature_at(x, y)
    if not f: continue
    p = f["properties"]
    name = tg.get("name") if any(k in tg for k in PLACE_KEYS) else None
    if name and name != p.get("n"):
        lst = p.setdefault("in", [])
        if name not in lst and len(lst) < 12: lst.append(name)
    if tg.get("addr:street") and tg.get("addr:housenumber"):
        a = tg["addr:street"] + " " + tg["addr:housenumber"]
        if not p.get("a"): p["a"] = a
        elif a != p["a"]:
            al = p.setdefault("al", [])
            if a not in al and len(al) < 20: al.append(a)

# enrichWiki: Wikidata photo (P18), inception year (P571), en/sv Wikipedia titles
WIKI = {}
qids = sorted({f["properties"]["q"] for f in feats if "q" in f["properties"]})
print(f"Wikidata: {len(qids)} items", file=sys.stderr)
for i in range(0, len(qids), 50):
    batch = qids[i:i + 50]
    url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=claims|sitelinks"
           "&sitefilter=enwiki|svwiki&ids=" + "|".join(batch))
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                d = json.load(r); break
        except Exception as e:
            print("  retry", i, e, file=sys.stderr); time.sleep(5 * (attempt + 1)); d = {}
    for q, ent in (d.get("entities") or {}).items():
        c, rec = ent.get("claims") or {}, {}
        def val(prop):
            try: return c[prop][0]["mainsnak"]["datavalue"]["value"]
            except (KeyError, IndexError, TypeError): return None
        img = val("P18")
        if img: rec["img"] = img
        t = val("P571")
        inc = parse_year(t["time"].lstrip("+")) if isinstance(t, dict) and t.get("time") else None
        if inc: rec["inc"] = inc
        sl = ent.get("sitelinks") or {}
        if "enwiki" in sl: rec["en"] = sl["enwiki"]["title"]
        if "svwiki" in sl: rec["sv"] = sl["svwiki"]["title"]
        if rec: WIKI[q] = rec
    time.sleep(0.5)
for f in feats:
    p = f["properties"]; w = WIKI.get(p.get("q"))
    if not w: p.pop("q", None); continue
    if w.get("img"): p["p"] = 1
    if w.get("inc"): p["y"] = w["inc"]; p["s"] = "wd"

# split into area chunks so the app can load the part of the city in view first
CHUNK_W, CHUNK_H = 0.1, 0.05
chunks = {}
for f in feats:
    p = f["properties"]
    chunks.setdefault(f"{math.floor(p['cx'] / CHUNK_W)}_{math.floor(p['cy'] / CHUNK_H)}", []).append(f)
outdir = sys.argv[2]
import os; os.makedirs(outdir, exist_ok=True)
for name in os.listdir(outdir):
    if name.endswith(".json"): os.remove(os.path.join(outdir, name))
index = {"v": CACHE_VERSION, "savedOn": int(time.time() * 1000), "source": os.path.basename(sys.argv[1]),
         "done": CELLS, "chunks": []}
for k, fs in sorted(chunks.items()):
    x, y = map(int, k.split("_"))
    wiki = {q: WIKI[q] for q in {f["properties"].get("q") for f in fs} if q in WIKI}
    with open(os.path.join(outdir, k + ".json"), "w", encoding="utf-8") as fh:
        json.dump({"features": fs, "wiki": wiki}, fh, ensure_ascii=False, separators=(",", ":"))
    index["chunks"].append({"k": k, "cx": round((x + .5) * CHUNK_W, 4), "cy": round((y + .5) * CHUNK_H, 4), "n": len(fs)})
with open(os.path.join(outdir, "index.json"), "w", encoding="utf-8") as fh:
    json.dump(index, fh, separators=(",", ":"))
withy = sum(1 for f in feats if "y" in f["properties"])
print(f"wrote {outdir}: {len(feats)} buildings in {len(chunks)} chunks, {withy} with a year, {len(WIKI)} wiki records", file=sys.stderr)
