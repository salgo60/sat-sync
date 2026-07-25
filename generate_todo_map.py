#!/usr/bin/env python3
"""Generate sat_todo_map.html — mobile-friendly TODO map for SAT POI data gaps."""

import json, urllib.request, urllib.parse, datetime, re, time, os

POIS_URL   = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
TRAIL_URL  = "https://map.stockholmarchipelagotrail.com/data/trail.jsonld"
SECTIONS_URL = "https://map.stockholmarchipelagotrail.com/data/sections-index.json"
AED_URL    = "https://map.stockholmarchipelagotrail.com/api/aed"
PIERS_URL  = "https://map.stockholmarchipelagotrail.com/data/piers-identity.json"
COMMONS_CATEGORY = "Stockholm_Archipelago_Trail"
COMMONS_API  = "https://commons.wikimedia.org/w/api.php"
MAPILLARY_API = "https://graph.mapillary.com/images"
MAPILLARY_TOKEN = os.getenv("MAPILLARY_TOKEN", "").strip()
OUTPUT     = "sat_todo_map.html"

HEADERS = {"User-Agent": "sat-sync/todo-map 1.0"}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def parse_wkt_point(value):
    m = re.match(r"Point\(([-0-9.]+)\s+([-0-9.]+)\)", str(value or ""))
    if not m:
        return None, None
    lon = float(m.group(1))
    lat = float(m.group(2))
    return lat, lon

def fetch_wikidata_pier_data(sat_ids):
    if not sat_ids:
        return {}
    values = " ".join(f"\"{s}\"" for s in sat_ids if s)
    query = f"""
SELECT ?satId ?item ?itemLabel ?coord WHERE {{
  VALUES ?satId {{ {values} }}
  ?item wdt:P14545 ?satId .
  OPTIONAL {{ ?item wdt:P625 ?coord . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "sv,en". }}
}}
"""
    url = "https://query.wikidata.org/sparql?query=" + urllib.parse.quote(query) + "&format=json"
    data = fetch(url)
    out = {}
    for b in data.get("results", {}).get("bindings", []):
        sat_id = b.get("satId", {}).get("value", "")
        item_url = b.get("item", {}).get("value", "")
        qid = item_url.rsplit("/", 1)[-1] if item_url else ""
        label = b.get("itemLabel", {}).get("value", "")
        lat, lon = parse_wkt_point(b.get("coord", {}).get("value", ""))
        out[sat_id] = {
            "qid": qid,
            "label": label,
            "lat": lat,
            "lon": lon,
        }
    return out

def fetch_commons_geotagged(root_category: str) -> list[dict]:
    """Fetch all geotagged files from a Commons category tree (depth=1 subcats + root)."""
    def api_get(params: dict, retries: int = 3) -> dict:
        params["format"] = "json"
        url = COMMONS_API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "sat-sync/todo-map 1.0 (https://github.com/salgo60/sat-sync)"})
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    wait = 2 ** (attempt + 1)
                    print(f"  ⏳ 429 rate-limit, väntar {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        raise RuntimeError(f"Commons API misslyckades efter {retries} försök")

    # 1. Collect all categories to scan: root + direct subcategories
    categories = [root_category]
    cont = {}
    while True:
        params = {"action": "query", "list": "categorymembers",
                  "cmtitle": f"Category:{root_category}", "cmtype": "subcat",
                  "cmlimit": "500"}
        params.update(cont)
        data = api_get(params)
        for m in data["query"]["categorymembers"]:
            title = m["title"]  # "Category:SAT Sandhamn"
            categories.append(title[len("Category:"):])
        if "continue" not in data:
            break
        cont = data["continue"]

    # 2. For each category, fetch files with coordinates + metadata.
    # The same file often appears in many categories; keep the richest metadata seen.
    photos_by_title: dict[str, dict] = {}
    for i, cat in enumerate(categories):
        time.sleep(1.0)  # Commons API: 1 req/sec to avoid 429
        print(f"  [{i+1}/{len(categories)}] {cat[:50]}", end="\r", flush=True)
        cont2 = {}
        while True:
            params = {
                "action": "query",
                "generator": "categorymembers",
                "gcmtitle": f"Category:{cat}",
                "gcmtype": "file",
                "gcmlimit": "500",
                "prop": "coordinates|imageinfo",
                "iiprop": "url|thumburl|extmetadata",
                "iiextmetadatalanguage": "sv",
                "iiurlwidth": "200",
            }
            params.update(cont2)
            data = api_get(params)
            for page in (data.get("query") or {}).get("pages", {}).values():
                coords_list = page.get("coordinates") or []
                if not coords_list:
                    continue
                c = coords_list[0]
                title = page.get("title", "")
                mid = page.get("pageid")
                ii = (page.get("imageinfo") or [{}])[0]
                thumb = ii.get("thumburl") or ii.get("url") or ""
                em = ii.get("extmetadata") or {}
                date_raw = (em.get("DateTimeOriginal") or em.get("DateTime") or {}).get("value", "")
                artist_html = (em.get("Artist") or {}).get("value", "")
                cats_raw = (em.get("Categories") or {}).get("value", "")
                cats = [c2.strip() for c2 in cats_raw.split("|") if c2.strip()] if cats_raw else []
                page_url = "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))
                candidate = {
                    "lat": c["lat"],
                    "lon": c["lon"],
                    "title": title[len("File:"):] if title.startswith("File:") else title,
                    "thumb": thumb,
                    "url": page_url,
                    "mid": mid,
                    "date": date_raw,
                    "artist": artist_html,
                    "cats": cats,
                }

                existing = photos_by_title.get(title)
                if not existing:
                    photos_by_title[title] = candidate
                    continue

                # Merge in richer values from later category hits.
                if (not existing.get("thumb")) and candidate.get("thumb"):
                    existing["thumb"] = candidate["thumb"]
                if (not existing.get("date")) and candidate.get("date"):
                    existing["date"] = candidate["date"]
                if (not existing.get("artist")) and candidate.get("artist"):
                    existing["artist"] = candidate["artist"]
                if len(existing.get("cats", [])) < len(candidate.get("cats", [])):
                    existing["cats"] = candidate["cats"]
                if (not existing.get("mid")) and candidate.get("mid"):
                    existing["mid"] = candidate["mid"]
            if "continue" not in data:
                break
            cont2 = data["continue"]
    return list(photos_by_title.values())

def _iter_geojson_coords(node):
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "FeatureCollection":
            for f in node.get("features", []):
                yield from _iter_geojson_coords(f)
            return
        if node_type == "Feature":
            yield from _iter_geojson_coords(node.get("geometry", {}))
            return
        coords = node.get("coordinates")
        if coords is not None:
            yield from _iter_geojson_coords(coords)
            return
    if isinstance(node, list):
        if len(node) >= 2 and isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            yield float(node[1]), float(node[0])  # lat, lon
            return
        for part in node:
            yield from _iter_geojson_coords(part)

def _mapillary_fetch_json(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                return {"data": []}
            time.sleep(0.6 * (attempt + 1))
    return {"data": []}

def _mapillary_item(item: dict) -> dict | None:
    image_id = str(item.get("id", ""))
    geom = item.get("computed_geometry") or {}
    pt = geom.get("coordinates") or []
    if not image_id or len(pt) < 2:
        return None
    creator = (item.get("creator") or {}).get("username", "")
    return {
        "id": image_id,
        "lat": pt[1],
        "lon": pt[0],
        "capturedAt": item.get("captured_at"),
        "thumb": item.get("thumb_1024_url", ""),
        "creator": creator,
        "url": f"https://www.mapillary.com/app/?pKey={image_id}",
    }

def merge_mapillary_images(*groups: list[dict]) -> list[dict]:
    by_id: dict[str, dict] = {}
    for group in groups:
        for item in group:
            image_id = str(item.get("id", ""))
            if not image_id:
                continue
            if image_id not in by_id:
                by_id[image_id] = item
    return list(by_id.values())

def section_bbox_from_pois(raw_pois: list[dict], section_name: str):
    name = section_name.lower().strip()
    pts = []
    for f in raw_pois:
        p = f.get("properties") or {}
        sec = str(p.get("section") or "").lower().strip()
        if sec != name:
            continue
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if len(coords) < 2:
            continue
        pts.append((coords[1], coords[0]))  # lat, lon
    if not pts:
        return None
    lats = [lat for lat, _ in pts]
    lons = [lon for _, lon in pts]
    return (min(lons), min(lats), max(lons), max(lats))

def fetch_mapillary_images_in_bbox_grid(token: str, bbox: tuple[float, float, float, float], padding: float = 0.01, tile_size: float = 0.04) -> list[dict]:
    min_lon, min_lat, max_lon, max_lat = bbox
    min_lon -= padding
    min_lat -= padding
    max_lon += padding
    max_lat += padding

    images: list[dict] = []
    lat = min_lat
    tile_index = 0
    while lat < max_lat:
        lon = min_lon
        while lon < max_lon:
            tile_index += 1
            tile_bbox = f"{lon},{lat},{min(lon + tile_size, max_lon)},{min(lat + tile_size, max_lat)}"
            params = {
                "access_token": token,
                "fields": "id,captured_at,computed_geometry,thumb_1024_url,creator",
                "bbox": tile_bbox,
                "limit": "200",
            }
            url = MAPILLARY_API + "?" + urllib.parse.urlencode(params)
            page_count = 0
            while url and page_count < 8:
                data = _mapillary_fetch_json(url)
                for raw in data.get("data", []):
                    parsed = _mapillary_item(raw)
                    if parsed:
                        images.append(parsed)
                url = (data.get("paging") or {}).get("next")
                page_count += 1
                time.sleep(0.15)
            lon += tile_size
        lat += tile_size
    return merge_mapillary_images(images)

def fetch_mapillary_images_near_trail(trail_geojson, token: str, max_boxes: int = 20) -> list[dict]:
    if not token:
        return []
    coords = list(_iter_geojson_coords(trail_geojson))
    if not coords:
        return []
    step = max(1, len(coords) // max_boxes)
    sampled = coords[::step]
    if coords[-1] not in sampled:
        sampled.append(coords[-1])

    images: list[dict] = []
    for i, (lat, lon) in enumerate(sampled, start=1):
        d = 0.02  # bbox area = 0.0016 (under 0.010 API limit)
        bbox = f"{lon-d},{lat-d},{lon+d},{lat+d}"
        params = {
            "access_token": token,
            "fields": "id,captured_at,computed_geometry,thumb_1024_url,creator",
            "bbox": bbox,
            "limit": "120",
        }
        url = MAPILLARY_API + "?" + urllib.parse.urlencode(params)
        data = _mapillary_fetch_json(url)
        for item in data.get("data", []):
            parsed = _mapillary_item(item)
            if parsed:
                images.append(parsed)
        if i % 10 == 0:
            print(f"  … Mapillary-rutor: {i}/{len(sampled)}", end="\r", flush=True)
        time.sleep(0.15)
    return merge_mapillary_images(images)

print("📥 Hämtar POI...")
raw_pois = fetch(POIS_URL)["features"]
print(f"  ✅ {len(raw_pois)} POI")

print("📥 Hämtar leden...")
trail_raw = fetch(TRAIL_URL)
trail_geojson = trail_raw if trail_raw.get("type") == "FeatureCollection" else {"type":"FeatureCollection","features":[{"type":"Feature","geometry":trail_raw.get("geometry",{}),"properties":{}}]}
print("  ✅ Ledgeometri hämtad")

print("📥 Hämtar sections...")
sections_index = fetch(SECTIONS_URL)
print(f"  ✅ {len(sections_index)} sektioner")

print("📥 Hämtar AED...")
try:
    aed_raw = fetch(AED_URL)
    aed_features = aed_raw.get("features", [])
    print(f"  ✅ {len(aed_features)} AED-platser")
except Exception as e:
    print(f"  ⚠️ AED fel: {e}")
    aed_features = []

aed_data = []
for f in aed_features:
    geom = f.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if len(coords) < 2:
        continue
    p = f.get("properties") or {}
    addr = p.get("address") or {}
    aed_data.append({
        "lat": coords[1], "lon": coords[0],
        "name": p.get("name", "AED"),
        "owner": p.get("owner", ""),
        "opening_hours": p.get("opening_hours", ""),
        "street": addr.get("street", ""),
        "city": addr.get("city", ""),
    })

print("📥 Hämtar piers identity...")
try:
    piers_identity = fetch(PIERS_URL)
    print(f"  ✅ {len(piers_identity)} piers-poster")
except Exception as e:
    print(f"  ⚠️ Piers identity fel: {e}")
    piers_identity = {}

piers_data = []
missing_pier_sat_ids = []
if piers_identity:
    print("📥 Hämtar piers-koordinater från Wikidata...")
    try:
        sat_ids = sorted({(v or {}).get("satId", "") for v in piers_identity.values() if (v or {}).get("satId", "")})
        wd_by_sat_id = fetch_wikidata_pier_data(sat_ids)
    except Exception as e:
        print(f"  ⚠️ Wikidata pier-koordinater fel: {e}")
        wd_by_sat_id = {}

    for uid, v in piers_identity.items():
        sat_id = (v or {}).get("satId", "")
        wd = wd_by_sat_id.get(sat_id)
        if not wd or wd.get("lat") is None or wd.get("lon") is None:
            missing_pier_sat_ids.append(sat_id or f"uid:{uid}")
            continue
        gtfs = ((v or {}).get("concordances") or {}).get("gtfs") or []
        piers_data.append({
            "uid": uid,
            "satId": sat_id,
            "name": (v or {}).get("name", ""),
            "slug": (v or {}).get("slug", ""),
            "gtfsCount": len(gtfs),
            "wikidataQid": wd.get("qid", ""),
            "wikidataLabel": wd.get("label", ""),
            "lat": wd.get("lat"),
            "lon": wd.get("lon"),
        })
    print(f"  ✅ {len(piers_data)} piers med koordinater")
    if missing_pier_sat_ids:
        print(f"  ⚠️ {len(missing_pier_sat_ids)} piers saknar koordinater i Wikidata")

print("📥 Hämtar Commons-foton (geotaggade)...")
try:
    commons_data = fetch_commons_geotagged(COMMONS_CATEGORY)
    print(f"  ✅ {len(commons_data)} geotaggade Commons-foton")
except Exception as e:
    print(f"  ⚠️ Commons fel: {e}")
    commons_data = []

mapillary_data = []
if MAPILLARY_TOKEN:
    print("📥 Hämtar Mapillary-bilder nära leden...")
    try:
        mapillary_data = fetch_mapillary_images_near_trail(trail_geojson, MAPILLARY_TOKEN)
        print(f"  ✅ {len(mapillary_data)} Mapillary-bilder nära leden")

        landsort_bbox = section_bbox_from_pois(raw_pois, "landsort")
        if landsort_bbox:
            print("📥 Kompletterar Mapillary kring Landsort...")
            landsort_images = fetch_mapillary_images_in_bbox_grid(MAPILLARY_TOKEN, landsort_bbox)
            before = len(mapillary_data)
            mapillary_data = merge_mapillary_images(mapillary_data, landsort_images)
            added = len(mapillary_data) - before
            print(f"  ✅ Landsort: +{added} (totalt {len(mapillary_data)})")
        else:
            print("  ⚠️ Landsort-sektion hittades inte i POI-data")
    except Exception as e:
        print(f"  ⚠️ Mapillary fel: {e}")
else:
    print("  ℹ️ Mapillary hoppas över (ingen MAPILLARY_TOKEN satt)")

generated_at = datetime.datetime.now().strftime("%Y%m%d %H:%M")

# Build POI list with missing-data flags
pois = []
for f in raw_pois:
    props = f["properties"]
    geom  = f.get("geometry") or {}
    coords = geom.get("coordinates") or []
    lat = coords[1] if len(coords) >= 2 else None
    lon = coords[0] if len(coords) >= 2 else None
    if lat is None: continue

    same_as = props.get("sameAs") or []
    osm_ref = next((s for s in same_as if s.startswith("osm:")), None)
    wd_ref  = next((s for s in same_as if s.startswith("wikidata:")), None)

    missing = []
    if not osm_ref: missing.append("osm")
    if not wd_ref:  missing.append("wikidata")
    if not props.get("image"): missing.append("image")

    pois.append({
        "id": props.get("id",""),
        "name": props.get("name",""),
        "section": props.get("section",""),
        "category": props.get("category",""),
        "lat": lat, "lon": lon,
        "osm": osm_ref,
        "wikidata": wd_ref,
        "image": bool(props.get("image")),
        "website": props.get("website",""),
        "fixme": props.get("fixme",""),
        "note": props.get("note",""),
        "missing": missing,
    })

# Stage summary
from collections import defaultdict
stage_stats = defaultdict(lambda: {"total":0,"no_osm":0,"no_wd":0,"no_img":0})
for p in pois:
    s = p["section"]
    stage_stats[s]["total"] += 1
    if "osm"       in p["missing"]: stage_stats[s]["no_osm"] += 1
    if "wikidata"  in p["missing"]: stage_stats[s]["no_wd"]  += 1
    if "image"     in p["missing"]: stage_stats[s]["no_img"] += 1

pois_json        = json.dumps(pois,        ensure_ascii=False)
trail_json       = json.dumps(trail_geojson, ensure_ascii=False)
stage_stats_json = json.dumps(dict(stage_stats), ensure_ascii=False)
aed_json         = json.dumps(aed_data,    ensure_ascii=False)
piers_json       = json.dumps(piers_data,  ensure_ascii=False)
missing_piers_json = json.dumps(sorted(missing_pier_sat_ids), ensure_ascii=False)
commons_json     = json.dumps(commons_data, ensure_ascii=False)
mapillary_json   = json.dumps(mapillary_data, ensure_ascii=False)

html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
  <title id="page-title-el">SAT TODO – Vad saknas?</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: system-ui, sans-serif; background:#f0f4f8; color:#1e293b; }}
    #app {{ display:flex; flex-direction:column; height:100dvh; }}

    /* Header */
    .top-bar {{ background: linear-gradient(135deg,#0f766e,#0d4f49); color:#fff; padding:10px 14px; display:flex; align-items:center; gap:10px; flex-shrink:0; }}
    .top-bar h1 {{ margin:0; font-size:1.05rem; flex:1; }}
    .top-bar .meta {{ font-size:0.7rem; opacity:0.75; white-space:nowrap; }}
    .top-bar a {{ color:#99f6e4; text-decoration:none; font-size:0.75rem; }}

    /* Tabs */
    .tabs {{ display:flex; background:#fff; border-bottom:2px solid #e2e8f0; flex-shrink:0; }}
    .tab {{ flex:1; padding:10px 4px; text-align:center; font-size:0.8rem; font-weight:600; color:#64748b; cursor:pointer; border:none; background:none; }}
    .tab.active {{ color:#0f766e; border-bottom:2px solid #0f766e; margin-bottom:-2px; }}

    /* Filter bar */
    .filter-bar {{ background:#fff; padding:8px 12px; display:flex; gap:8px; align-items:center; flex-wrap:wrap; border-bottom:1px solid #e2e8f0; flex-shrink:0; }}
    .filter-bar select {{ flex:1; min-width:120px; padding:6px 8px; border:1px solid #cbd5e1; border-radius:6px; font-size:0.85rem; }}
    .filter-bar .toggles {{ display:flex; gap:6px; flex-wrap:wrap; }}
    .chip {{ display:inline-flex; align-items:center; gap:4px; padding:5px 10px; border-radius:20px; font-size:0.78rem; font-weight:600; cursor:pointer; border:2px solid transparent; user-select:none; }}
    .chip.osm    {{ background:#fee2e2; color:#991b1b; border-color:#fca5a5; }}
    .chip.wd     {{ background:#fef3c7; color:#92400e; border-color:#fcd34d; }}
    .chip.img    {{ background:#ede9fe; color:#5b21b6; border-color:#c4b5fd; }}
    .chip.notes  {{ background:#dbeafe; color:#1e40af; border-color:#93c5fd; }}
    .chip.off    {{ opacity:0.45; }}
    .loc-btn {{ padding:6px 12px; background:#0f766e; color:#fff; border:none; border-radius:6px; font-size:0.85rem; font-weight:600; cursor:pointer; white-space:nowrap; }}
    .loc-btn:active {{ background:#0d6b64; }}

    /* Map */
    #map {{ flex:1; min-height:0; }}

    /* List */
    #list-view {{ flex:1; min-height:0; overflow:auto; display:none; padding:8px 10px; }}
    .todo-table-wrap {{ background:#fff; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,0.08); overflow:auto; }}
    .todo-table {{ width:100%; border-collapse:collapse; font-size:0.8rem; min-width:860px; }}
    .todo-table th, .todo-table td {{ border-bottom:1px solid #e2e8f0; padding:8px; text-align:left; vertical-align:top; }}
    .todo-table th {{ position:sticky; top:0; background:#f8fafc; z-index:1; font-size:0.72rem; text-transform:uppercase; letter-spacing:.02em; color:#475569; }}
    .todo-table tr:last-child td {{ border-bottom:none; }}
    .todo-table .poi-name {{ font-weight:600; }}
    .todo-table .missing-tags {{ display:flex; gap:4px; flex-wrap:wrap; }}
    .muted {{ color:#94a3b8; }}
    .mini-chip {{ padding:2px 6px; border-radius:10px; font-size:0.68rem; font-weight:700; }}
    .mini-chip.osm {{ background:#fee2e2; color:#991b1b; }}
    .mini-chip.wd  {{ background:#fef3c7; color:#92400e; }}
    .mini-chip.img {{ background:#ede9fe; color:#5b21b6; }}
    .poi-goto {{ font-size:1rem; cursor:pointer; background:none; border:none; padding:2px; }}

    /* OSM note popup */
    .note-popup {{ font-size:0.82rem; max-width:200px; }}
    .note-popup strong {{ display:block; margin-bottom:4px; }}

    /* footer */
    .page-footer {{ background:#fff; border-top:1px solid #e2e8f0; padding:8px 14px; font-size:0.72rem; color:#94a3b8; text-align:center; flex-shrink:0; }}
    .page-footer a {{ color:#0f766e; }}
  </style>
</head>
<body>
<div id="app">

  <div class="top-bar">
    <h1 id="top-title">🗺️ SAT TODO – Vad saknas?</h1>
    <div class="meta">
      {generated_at} &nbsp;
      <a href="sat_poi_dashboard.html" id="top-dashboard-link">Dashboard</a>
    </div>
    <button id="lang-toggle" onclick="toggleLang()" style="margin-left:8px;padding:4px 10px;background:rgba(255,255,255,0.2);color:#fff;border:1px solid rgba(255,255,255,0.5);border-radius:6px;font-size:0.75rem;font-weight:600;cursor:pointer">English</button>
  </div>

  <div class="tabs">
    <button class="tab active" id="tab-map" onclick="showTab('map')">🗺️ Karta</button>
    <button class="tab" id="tab-list" onclick="showTab('list')">📋 Lista</button>
  </div>

  <div class="filter-bar">
    <select id="stageFilter" onchange="applyFilters()">
      <option value="all" id="stage-all-opt">Alla etapper</option>
    </select>
    <select id="categoryFilter" onchange="applyFilters()">
      <option value="all" id="cat-all-opt">Alla kategorier</option>
    </select>
    <button class="loc-btn" id="loc-btn" onclick="locateMe()">📍 Nära mig</button>
  </div>

  <div id="map"></div>
  <div id="list-view"></div>

  <div class="page-footer">
    <a href="sat_poi_dashboard.html">SAT POI Dashboard</a> ·
    <a href="whats_new.html">What's new</a> ·
    <a href="https://github.com/salgo60/sat-sync" target="_blank">GitHub</a>
  </div>
</div>

<script>
(function() {{
  const ALL_POIS = {pois_json};
  const TRAIL_GEOJSON = {trail_json};
  const STAGE_STATS = {stage_stats_json};
  const AED_POINTS = {aed_json};
  const PIER_POINTS = {piers_json};
  const MISSING_PIER_SAT_IDS = {missing_piers_json};
  const COMMONS_PHOTOS = {commons_json};
  const MAPILLARY_IMAGES = {mapillary_json};
  const OSM_TAG_CACHE = {{}};
  const WD_ENTITY_CACHE = {{}};

  // ── i18n ──────────────────────────────────────────────────────────────────
  const i18n = {{
    sv: {{
      title: 'SAT TODO \u2013 Vad saknas?',
      tabMap: '\U0001f5fe Karta',
      tabList: '\U0001f4cb Lista',
      allStages: 'Alla etapper',
      allCategories: 'Alla kategorier',
      nearMe: '\U0001f4cd N\xe4ra mig',
      langToggle: 'English',
      layerMissingOsm: '\u274c Saknar OSM-l\xe4nk',
      layerMissingWd: '\U0001f4cb Saknar Wikidata',
      layerMissingImg: '\U0001f4f7 Saknar bild',
      layerWheelchair: '\u267f Wheelchair',
      layerMissingWheelchair: '\u25fb\ufe0f Saknar Wheelchair',
      layerIncPoi: 'Inkonsekvens POI',
      layerIncOsmWd: 'Inkonsekvens OSM saknar koppling WD',
      layerIncWdOsm: 'Inkonsekvens WD saknar koppling OSM',
      layerNotes: '\U0001f4ac OSM Notes',
      layerAed: '\U0001f9e1 Hj\xe4rtstartare (AED)',
      layerPiers: '\u26f4 Bryggor (piers)',
      layerCommons: '\U0001f4f7 Commons-foton',
      layerMapillary: '\U0001f4f8 Mapillary-bilder',
      deselectAllLayers: 'Avmarkera alla lager',
      missingWd: 'Saknar Wikidata',
      missingImg: 'Saknar bild',
      satMap: '\U0001f5fe SAT-kartan',
      satJson: '\U0001f9fe SAT JSON',
      osmLink: '\U0001f517 OSM',
      idEditor: '\u270f\ufe0f iD editor',
      deepHistory: '\U0001f570\ufe0f OSM Deep history',
      mapkiHistory: '\U0001f4cd Mapki history',
      noOsmLink: '\u274c Ingen OSM-l\xe4nk',
      noWdLink: '\u274c Ingen Wikidata-l\xe4nk',
      wikidataLink: '\U0001f4da Wikidata',
      website: '\U0001f310 Webbplats',
      wikimap: '\U0001f5fe Wikimap',
      createNote: '\U0001f4ac Skapa OSM Note h\xe4r',
      incCheck: '\u26a0\ufe0f Inkonsekvens-kontroll',
      incDesc1: 'Inkonsekvens POI: Wikidata P14545 har SAT-ID men OSM saknar <code>ref:stockholmarchipelagotrail</code>.',
      incDesc2: 'Inkonsekvens OSM saknar koppling WD: OSM saknar/avviker i taggen <code>wikidata</code>.',
      incDesc3: 'Inkonsekvens WD saknar koppling OSM: Wikidata saknar OSM-ID (node/way/relation) tillbaka till objektet.',
      controls: 'Kontroller:',
      noObjects: 'Inga objekt matchar aktiva filter.',
      thStage: 'Etapp', thPoi: 'POI', thOsmName: 'OSM name', thCategory: 'Kategori',
      thMissing: 'Saknas', thFixme: 'fixme (OSM)', thNote: 'note (OSM)',
      thCheckDate: 'check_date (OSM)', thLinks: 'L\xe4nkar',
      noName: '(utan namn)', showOnMap: 'Visa p\xe5 karta',
      yourPosition: '\U0001f4cd Din position',
      geoNotSupported: 'Geolocation st\xf6ds inte i din webbl\xe4sare.',
      geoError: 'Kunde inte h\xe4mta position: ',
      openOnOsm: '\xd6ppna p\xe5 OSM',
      noText: '(ingen text)',
    }},
    en: {{
      title: 'SAT TODO \u2013 What\u2019s missing?',
      tabMap: '\U0001f5fe Map',
      tabList: '\U0001f4cb List',
      allStages: 'All stages',
      allCategories: 'All categories',
      nearMe: '\U0001f4cd Near me',
      langToggle: 'Svenska',
      layerMissingOsm: '\u274c Missing OSM link',
      layerMissingWd: '\U0001f4cb Missing Wikidata',
      layerMissingImg: '\U0001f4f7 Missing image',
      layerWheelchair: '\u267f Wheelchair',
      layerMissingWheelchair: '\u25fb\ufe0f Missing Wheelchair',
      layerIncPoi: 'Inconsistency POI',
      layerIncOsmWd: 'Inconsistency OSM missing WD link',
      layerIncWdOsm: 'Inconsistency WD missing OSM link',
      layerNotes: '\U0001f4ac OSM Notes',
      layerAed: '\U0001f9e1 Defibrillator (AED)',
      layerPiers: '\u26f4 Piers',
      layerCommons: '\U0001f4f7 Commons photos',
      layerMapillary: '\U0001f4f8 Mapillary images',
      deselectAllLayers: 'Deselect all layers',
      missingWd: 'Missing Wikidata',
      missingImg: 'Missing image',
      satMap: '\U0001f5fe SAT map',
      satJson: '\U0001f9fe SAT JSON',
      osmLink: '\U0001f517 OSM',
      idEditor: '\u270f\ufe0f iD editor',
      deepHistory: '\U0001f570\ufe0f OSM Deep history',
      mapkiHistory: '\U0001f4cd Mapki history',
      noOsmLink: '\u274c No OSM link',
      noWdLink: '\u274c No Wikidata link',
      wikidataLink: '\U0001f4da Wikidata',
      website: '\U0001f310 Website',
      wikimap: '\U0001f5fe Wikimap',
      createNote: '\U0001f4ac Create OSM Note here',
      incCheck: '\u26a0\ufe0f Inconsistency check',
      incDesc1: 'Inconsistency POI: Wikidata P14545 has SAT ID but OSM is missing <code>ref:stockholmarchipelagotrail</code>.',
      incDesc2: 'Inconsistency OSM missing WD link: OSM is missing or wrong in the <code>wikidata</code> tag.',
      incDesc3: 'Inconsistency WD missing OSM link: Wikidata is missing OSM ID (node/way/relation) back to the object.',
      controls: 'Checks:',
      noObjects: 'No objects match the active filters.',
      thStage: 'Stage', thPoi: 'POI', thOsmName: 'OSM name', thCategory: 'Category',
      thMissing: 'Missing', thFixme: 'fixme (OSM)', thNote: 'note (OSM)',
      thCheckDate: 'check_date (OSM)', thLinks: 'Links',
      noName: '(no name)', showOnMap: 'Show on map',
      yourPosition: '\U0001f4cd Your position',
      geoNotSupported: 'Geolocation not supported in your browser.',
      geoError: 'Could not get location: ',
      openOnOsm: 'Open on OSM',
      noText: '(no text)',
    }},
  }};

  let lang = 'sv';
  function t(k) {{ return (i18n[lang] || i18n.sv)[k] || k; }}

  function applyLanguage() {{
    document.documentElement.lang = lang;
    document.title = t('title');
    document.getElementById('page-title-el').textContent = t('title');
    const top = document.getElementById('top-title');
    if (top) top.textContent = '\U0001f5fe ' + t('title');
    document.getElementById('tab-map').textContent = t('tabMap');
    document.getElementById('tab-list').textContent = t('tabList');
    document.getElementById('stage-all-opt').textContent = t('allStages');
    document.getElementById('cat-all-opt').textContent = t('allCategories');
    document.getElementById('loc-btn').textContent = t('nearMe');
    document.getElementById('lang-toggle').textContent = t('langToggle');
    rebuildLayerControl();
    if (document.getElementById('tab-list').classList.contains('active')) renderList();
  }}

  window.toggleLang = function() {{
    lang = lang === 'sv' ? 'en' : 'sv';
    applyLanguage();
    saveStateInUrl();
  }};

  // State
  let currentStage = 'all';
  let currentCategory = 'all';
  let locationMarker = null;
  let osmNotesLoaded = false;
  let renderVersion = 0;
  let initialTab = 'map';
  let isRestoringState = false;

  // ── Map setup ──────────────────────────────────────────────────────────────
  const map = L.map('map', {{ zoomControl: true }}).setView([59.3, 18.9], 8);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19, attribution: '© OpenStreetMap'
  }}).addTo(map);

  // Trail
  L.geoJSON(TRAIL_GEOJSON, {{ style: {{ color:'#0f766e', weight:3, opacity:0.6 }} }}).addTo(map);

  // Zoom to trail bounds
  try {{
    const tb = L.geoJSON(TRAIL_GEOJSON).getBounds();
    if (tb.isValid()) map.fitBounds(tb, {{ padding: [20,20] }});
  }} catch(e) {{}}

  // ── Stage + category filters ───────────────────────────────────────────────
  const stageFilter = document.getElementById('stageFilter');
  const categoryFilter = document.getElementById('categoryFilter');
  const stages = [...new Set(ALL_POIS.map(p => p.section).filter(Boolean))].sort();
  stages.forEach(s => {{
    const o = document.createElement('option');
    o.value = s; o.textContent = s.charAt(0).toUpperCase() + s.slice(1);
    stageFilter.appendChild(o);
  }});
  const categories = [...new Set(ALL_POIS.map(p => p.category).filter(Boolean))].sort();
  categories.forEach(c => {{
    const o = document.createElement('option');
    o.value = c; o.textContent = c.charAt(0).toUpperCase() + c.slice(1);
    categoryFilter.appendChild(o);
  }});

  // ── Icons ──────────────────────────────────────────────────────────────────
  function makeIcon(missing) {{
    const colors = [];
    if (missing.includes('osm'))      colors.push('#ef4444');
    if (missing.includes('wikidata')) colors.push('#f59e0b');
    if (missing.includes('image'))    colors.push('#8b5cf6');
    const bg = colors[0] || '#64748b';
    const count = missing.length;
    return L.divIcon({{
      className: '',
      html: `<div style="width:22px;height:22px;border-radius:50%;background:${{bg}};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff">${{count}}</div>`,
      iconSize: [22,22], iconAnchor: [11,11], popupAnchor: [0,-12]
    }});
  }}

  function makeTagIcon(bg, label) {{
    return L.divIcon({{
      className: '',
      html: `<div style="width:22px;height:22px;border-radius:50%;background:${{bg}};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:#fff">${{label}}</div>`,
      iconSize: [22,22], iconAnchor: [11,11], popupAnchor: [0,-12]
    }});
  }}

  const wheelchairIcon = makeTagIcon('#16a34a', '♿');
  const missingWheelchairIcon = makeTagIcon('#64748b', '?');
  const inconsistencyPoiIcon = makeTagIcon('#dc2626', '!');
  const inconsistencyOsmWdIcon = makeTagIcon('#f97316', 'W');
  const inconsistencyWdOsmIcon = makeTagIcon('#2563eb', 'O');

  // ── Problem layers (one per issue type) ───────────────────────────────────
  const layerMissingOsm = L.layerGroup().addTo(map);
  const layerMissingWd  = L.layerGroup().addTo(map);
  const layerMissingImg = L.layerGroup().addTo(map);
  const osmNotesLayer   = L.layerGroup().addTo(map);
  const layerWheelchair = L.layerGroup();
  const layerMissingWheelchair = L.layerGroup();
  const layerInconsistencyPoi = L.layerGroup();
  const layerInconsistencyOsmMissingWd = L.layerGroup();
  const layerInconsistencyWdMissingOsm = L.layerGroup();
  const layerAed = L.layerGroup();
  const layerPiers = L.layerGroup();
  const layerCommons = L.layerGroup();
  const layerMapillary = L.layerGroup();
  const layerByKey = {{
    osm: layerMissingOsm,
    wd: layerMissingWd,
    img: layerMissingImg,
    wc: layerWheelchair,
    mwc: layerMissingWheelchair,
    inc: layerInconsistencyPoi,
    incpoi: layerInconsistencyPoi,
    incosm: layerInconsistencyOsmMissingWd,
    incwd: layerInconsistencyWdMissingOsm,
    notes: osmNotesLayer,
    aed: layerAed,
    piers: layerPiers,
    commons: layerCommons,
    mly: layerMapillary,
  }};

  // Layer control — shown in map top-right
  let layerControl = null;
  function deselectAllLayers() {{
    Object.values(layerByKey).forEach((layer) => {{
      if (map.hasLayer(layer)) map.removeLayer(layer);
    }});
    saveStateInUrl();
  }}

  function rebuildLayerControl() {{
    if (layerControl) layerControl.remove();
    layerControl = L.control.layers(null, {{
      [t('layerMissingOsm')]:   layerMissingOsm,
      [t('layerMissingWd')]:    layerMissingWd,
      [t('layerMissingImg')]:   layerMissingImg,
      [t('layerWheelchair')]:   layerWheelchair,
      [t('layerMissingWheelchair')]: layerMissingWheelchair,
      [t('layerIncPoi')]:       layerInconsistencyPoi,
      [t('layerIncOsmWd')]:     layerInconsistencyOsmMissingWd,
      [t('layerIncWdOsm')]:     layerInconsistencyWdMissingOsm,
      [t('layerNotes')]:        osmNotesLayer,
      [t('layerAed')]:          layerAed,
      [t('layerPiers')]:        layerPiers,
      [t('layerCommons')]:      layerCommons,
      [t('layerMapillary')]:    layerMapillary,
    }}, {{ collapsed: false, position: 'topright' }}).addTo(map);

    const container = layerControl.getContainer();
    if (container) {{
      const actionWrap = document.createElement('div');
      actionWrap.style.padding = '6px 8px 8px';
      actionWrap.style.borderTop = '1px solid #e2e8f0';
      actionWrap.style.background = '#fff';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.textContent = t('deselectAllLayers');
      btn.style.width = '100%';
      btn.style.fontSize = '12px';
      btn.style.padding = '5px 8px';
      btn.style.border = '1px solid #cbd5e1';
      btn.style.borderRadius = '6px';
      btn.style.background = '#f8fafc';
      btn.style.cursor = 'pointer';
      btn.onclick = (ev) => {{
        ev.preventDefault();
        ev.stopPropagation();
        deselectAllLayers();
      }};
      actionWrap.appendChild(btn);
      container.appendChild(actionWrap);
      L.DomEvent.disableClickPropagation(actionWrap);
      L.DomEvent.disableScrollPropagation(actionWrap);
    }}
  }}

  map.on('overlayadd', (ev) => {{
    if (
      ev.layer === layerWheelchair ||
      ev.layer === layerMissingWheelchair ||
      ev.layer === layerInconsistencyPoi ||
      ev.layer === layerInconsistencyOsmMissingWd ||
      ev.layer === layerInconsistencyWdMissingOsm
    ) {{
      renderMarkers();
    }}
    saveStateInUrl();
  }});
  map.on('overlayremove', saveStateInUrl);
  map.on('moveend', saveStateInUrl);

  function optionExists(selectEl, value) {{
    return Array.from(selectEl.options).some((o) => o.value === value);
  }}

  function getActiveLayerKeys() {{
    return Object.entries(layerByKey)
      .filter(([, layer]) => map.hasLayer(layer))
      .map(([key]) => key);
  }}

  function applyLayerState(keys) {{
    const set = new Set(keys);
    Object.entries(layerByKey).forEach(([key, layer]) => {{
      const shouldBeOn = set.has(key);
      const isOn = map.hasLayer(layer);
      if (shouldBeOn && !isOn) map.addLayer(layer);
      if (!shouldBeOn && isOn) map.removeLayer(layer);
    }});
    // Ensure lazy layers are populated when enabled via URL state on first load.
    if (map.hasLayer(layerAed)) loadAed();
    if (map.hasLayer(layerPiers)) loadPiers();
    if (map.hasLayer(layerCommons)) loadCommons();
    if (map.hasLayer(layerMapillary)) loadMapillary();
  }}

  function saveStateInUrl() {{
    if (isRestoringState) return;
    const c = map.getCenter();
    const z = map.getZoom();
    const params = new URLSearchParams();
    params.set('stage', currentStage || 'all');
    params.set('category', currentCategory || 'all');
    params.set('tab', document.getElementById('tab-list').classList.contains('active') ? 'list' : 'map');
    params.set('lat', c.lat.toFixed(6));
    params.set('lon', c.lng.toFixed(6));
    params.set('z', String(z));
    params.set('layers', getActiveLayerKeys().join(','));
    if (lang !== 'sv') params.set('lang', lang);
    const stateStr = params.toString();
    if (window.location.protocol === 'file:') {{
      if (window.location.hash.slice(1) !== stateStr) {{
        window.location.hash = stateStr;
      }}
      return;
    }}
    const next = `${{window.location.pathname}}?${{stateStr}}`;
    window.history.replaceState({{}}, '', next);
  }}

  function applyStateFromUrl() {{
    let params = new URLSearchParams(window.location.search);
    if ([...params.keys()].length === 0 && window.location.hash.length > 1) {{
      params = new URLSearchParams(window.location.hash.slice(1));
    }}
    if ([...params.keys()].length === 0) return;
    isRestoringState = true;
    const stage = params.get('stage') || 'all';
    const category = params.get('category') || 'all';
    const tab = params.get('tab') || 'map';
    const lat = Number(params.get('lat'));
    const lon = Number(params.get('lon'));
    const z = Number(params.get('z'));
    const layers = (params.get('layers') || '').split(',').map(s => s.trim()).filter(Boolean);
    const urlLang = params.get('lang');
    if (urlLang === 'en' || urlLang === 'sv') lang = urlLang;

    if (optionExists(stageFilter, stage)) {{
      stageFilter.value = stage;
      currentStage = stage;
    }}
    if (optionExists(categoryFilter, category)) {{
      categoryFilter.value = category;
      currentCategory = category;
    }}
    if (Number.isFinite(lat) && Number.isFinite(lon) && Number.isFinite(z)) {{
      map.setView([lat, lon], z);
    }}
    if (layers.length > 0) applyLayerState(layers);
    if (tab === 'list' || tab === 'map') initialTab = tab;
    isRestoringState = false;
  }}

  function filteredPois() {{
    return ALL_POIS.filter(p => {{
      if (currentStage !== 'all' && p.section !== currentStage) return false;
      if (currentCategory !== 'all' && p.category !== currentCategory) return false;
      return true;
    }});
  }}

  function parseOsmRef(osmRef) {{
    if (!osmRef || !osmRef.startsWith('osm:')) return null;
    const parts = osmRef.split(':');
    if (parts.length !== 3) return null;
    return {{ type: parts[1], id: parts[2] }};
  }}

  async function fetchOsmTags(osmRef) {{
    if (!osmRef) return null;
    if (Object.prototype.hasOwnProperty.call(OSM_TAG_CACHE, osmRef)) return OSM_TAG_CACHE[osmRef];
    const parsed = parseOsmRef(osmRef);
    if (!parsed) {{
      OSM_TAG_CACHE[osmRef] = null;
      return null;
    }}
    try {{
      const url = `https://api.openstreetmap.org/api/0.6/${{parsed.type}}/${{parsed.id}}.json`;
      const resp = await fetch(url);
      if (!resp.ok) {{
        OSM_TAG_CACHE[osmRef] = null;
        return null;
      }}
      const data = await resp.json();
      const tags = (data.elements && data.elements[0] && data.elements[0].tags) ? data.elements[0].tags : {{}};
      OSM_TAG_CACHE[osmRef] = tags;
      return tags;
    }} catch (e) {{
      OSM_TAG_CACHE[osmRef] = null;
      return null;
    }}
  }}

  function parseWikidataRef(wdRef) {{
    if (!wdRef) return null;
    const raw = String(wdRef);
    if (raw.startsWith('wikidata:')) return raw.slice('wikidata:'.length);
    if (raw.startsWith('Q')) return raw;
    return null;
  }}

  function normalizeSatId(v) {{
    return String(v || '')
      .trim()
      .toLowerCase()
      .replace(/^https?:\\/\\/map\\.stockholmarchipelagotrail\\.com\\/?\\?/i, '')
      .replace(/^https?:\\/\\/map\\.stockholmarchipelagotrail\\.com\\/api\\/objects\\//i, '')
      .replace(/^sat%3apoi%3a/i, 'sat:poi:');
  }}

  function satIdMatches(values, satId) {{
    const want = normalizeSatId(satId);
    const short = want.replace(/^sat:poi:/, '');
    return values.some((v) => {{
      const n = normalizeSatId(v);
      return n === want || n.endsWith(short) || n.includes(want);
    }});
  }}

  async function fetchWikidataEntity(wdRef) {{
    const qid = parseWikidataRef(wdRef);
    if (!qid) return null;
    if (Object.prototype.hasOwnProperty.call(WD_ENTITY_CACHE, qid)) return WD_ENTITY_CACHE[qid];
    try {{
      const url = `https://www.wikidata.org/wiki/Special:EntityData/${{qid}}.json`;
      const resp = await fetch(url);
      if (!resp.ok) {{
        WD_ENTITY_CACHE[qid] = null;
        return null;
      }}
      const data = await resp.json();
      const entity = data?.entities?.[qid] || null;
      WD_ENTITY_CACHE[qid] = entity;
      return entity;
    }} catch (_e) {{
      WD_ENTITY_CACHE[qid] = null;
      return null;
    }}
  }}

  function wikidataSatRefs(entity) {{
    const claims = entity?.claims?.P14545 || [];
    return claims
      .map((c) => c?.mainsnak?.datavalue?.value)
      .filter((v) => typeof v === 'string' && v.trim());
  }}

  function hasWikidataOsmBacklink(entity, osmRef) {{
    const parsed = parseOsmRef(osmRef);
    if (!entity || !parsed) return false;
    const propByType = {{ node: 'P11693', way: 'P10689', relation: 'P402' }};
    const prop = propByType[parsed.type];
    if (!prop) return false;
    const claims = entity?.claims?.[prop] || [];
    return claims.some((c) => String(c?.mainsnak?.datavalue?.value || '') === String(parsed.id));
  }}

  function buildPopup(p, inconsistencyInfo = null) {{
    const tags = p.missing.map(tag => {{
      const labels = {{osm: t('missingOsm'), wikidata: t('missingWd'), image: t('missingImg')}};
      const colors = {{osm:'#ef4444', wikidata:'#f59e0b', image:'#8b5cf6'}};
      return `<span style="background:${{colors[tag]||'#888'}};color:#fff;padding:1px 6px;border-radius:10px;font-size:11px;margin-right:3px">${{labels[tag]||tag}}</span>`;
    }}).join('');
    const osmUrl = p.osm ? `https://www.openstreetmap.org/${{p.osm.replace('osm:node:','node/').replace('osm:way:','way/').replace('osm:relation:','relation/')}}` : null;
    const idUrl  = p.osm ? `https://www.openstreetmap.org/edit?editor=id&${{p.osm.replace('osm:','')}}#map=18/${{p.lat}}/${{p.lon}}` : null;
    const osmType = p.osm ? p.osm.replace('osm:','').split(':')[0] : null;
    const osmId   = p.osm ? p.osm.replace('osm:','').split(':')[1] : null;
    const deepHistoryUrl = osmType && osmId ? `https://osmlab.github.io/osm-deep-history/#/${{osmType}}/${{osmId}}` : null;
    const mapkiUrl = `https://mapki.com/map/#15/${{p.lat}}/${{p.lon}}`;
    const wdUrl  = p.wikidata ? `https://www.wikidata.org/wiki/${{p.wikidata.replace('wikidata:','')}}` : null;
    const satMapUrl = p.id ? `https://map.stockholmarchipelagotrail.com/?${{p.id}}` : null;
    const satJsonUrl = p.id ? `https://map.stockholmarchipelagotrail.com/api/objects/${{encodeURIComponent(p.id)}}` : null;
    const newNoteUrl = `https://www.openstreetmap.org/note/new#map=18/${{p.lat}}/${{p.lon}}`;
    const wikimapUrl = `https://wikimap.toolforge.org/?lat=${{p.lat}}&lon=${{p.lon}}&zoom=15&lang=en&wp=false&cluster=false`;
    const inconsistencyHtml = inconsistencyInfo
      ? `<details style="margin-top:6px"><summary>${{t('incCheck')}}</summary><div style="font-size:12px;margin-top:4px">${{inconsistencyInfo}}</div></details>`
      : `<details style="margin-top:6px"><summary>${{t('incCheck')}}</summary><div style="font-size:12px;margin-top:4px">${{t('controls')}}<br>1) ${{t('incDesc1')}}<br>2) ${{t('incDesc2')}}<br>3) ${{t('incDesc3')}}</div></details>`;
    return `<div style="min-width:160px;font-size:13px">
      <strong>${{escapeHtml(p.name)}}</strong><br>
      <small style="color:#64748b">${{escapeHtml(p.section)}} · ${{escapeHtml(p.category)}}</small><br>
      <div style="margin:5px 0">${{tags}}</div>
      ${{satMapUrl ? `<div><a href="${{satMapUrl}}" target="_blank">${{t('satMap')}}</a> · <a href="${{satJsonUrl}}" target="_blank">${{t('satJson')}}</a></div>` : ''}}
      ${{osmUrl ? `<div><a href="${{osmUrl}}" target="_blank">${{t('osmLink')}}</a> · <a href="${{idUrl}}" target="_blank">${{t('idEditor')}}</a></div>` : `<div style="color:#ef4444;font-size:11px">${{t('noOsmLink')}}</div>`}}
      ${{deepHistoryUrl ? `<div><a href="${{deepHistoryUrl}}" target="_blank">${{t('deepHistory')}}</a></div>` : ''}}
      <div><a href="${{mapkiUrl}}" target="_blank">${{t('mapkiHistory')}}</a></div>
      ${{wdUrl  ? `<div><a href="${{wdUrl}}" target="_blank">${{t('wikidataLink')}}</a></div>` : `<div style="color:#f59e0b;font-size:11px">${{t('noWdLink')}}</div>`}}
      ${{p.website ? `<div><a href="${{p.website}}" target="_blank">${{t('website')}}</a></div>` : ''}}
      <div style="margin-top:6px;border-top:1px solid #e2e8f0;padding-top:5px">
        <div><a href="${{wikimapUrl}}" target="_blank">${{t('wikimap')}}</a></div>
        <div><a href="${{newNoteUrl}}" target="_blank">${{t('createNote')}}</a></div>
      </div>
      ${{inconsistencyHtml}}
    </div>`;
  }}

  function renderMarkers() {{
    const currentRender = ++renderVersion;
    layerMissingOsm.clearLayers();
    layerMissingWd.clearLayers();
    layerMissingImg.clearLayers();
    layerWheelchair.clearLayers();
    layerMissingWheelchair.clearLayers();
    layerInconsistencyPoi.clearLayers();
    layerInconsistencyOsmMissingWd.clearLayers();
    layerInconsistencyWdMissingOsm.clearLayers();
    const fps = filteredPois();
    fps.forEach(p => {{
      const popup = buildPopup(p);
      if (p.missing.includes('osm')) {{
        L.marker([p.lat, p.lon], {{ icon: makeIcon(['osm']) }}).bindPopup(popup).addTo(layerMissingOsm);
      }}
      if (p.missing.includes('wikidata')) {{
        L.marker([p.lat, p.lon], {{ icon: makeIcon(['wikidata']) }}).bindPopup(popup).addTo(layerMissingWd);
      }}
      if (p.missing.includes('image')) {{
        L.marker([p.lat, p.lon], {{ icon: makeIcon(['image']) }}).bindPopup(popup).addTo(layerMissingImg);
      }}
    }});
    if (map.hasLayer(layerWheelchair) || map.hasLayer(layerMissingWheelchair)) {{
      renderWheelchairLayers(fps, currentRender);
    }}
    if (
      map.hasLayer(layerInconsistencyPoi) ||
      map.hasLayer(layerInconsistencyOsmMissingWd) ||
      map.hasLayer(layerInconsistencyWdMissingOsm)
    ) {{
      renderInconsistencyLayers(fps, currentRender);
    }}
  }}

  async function renderWheelchairLayers(pois, currentRender) {{
    const tasks = pois
      .filter((p) => !!p.osm)
      .map(async (p) => {{
        const tags = await fetchOsmTags(p.osm);
        if (currentRender !== renderVersion) return;
        if (!tags) return;
        const popup = buildPopup(p);
        if (Object.prototype.hasOwnProperty.call(tags, 'wheelchair')) {{
          L.marker([p.lat, p.lon], {{ icon: wheelchairIcon }}).bindPopup(popup).addTo(layerWheelchair);
        }} else {{
          L.marker([p.lat, p.lon], {{ icon: missingWheelchairIcon }}).bindPopup(popup).addTo(layerMissingWheelchair);
        }}
      }});
    await Promise.all(tasks);
  }}

  async function renderInconsistencyLayers(pois, currentRender) {{
    const showPoi = map.hasLayer(layerInconsistencyPoi);
    const showOsmMissingWd = map.hasLayer(layerInconsistencyOsmMissingWd);
    const showWdMissingOsm = map.hasLayer(layerInconsistencyWdMissingOsm);
    const tasks = pois
      .filter((p) => !!p.osm && !!p.wikidata)
      .map(async (p) => {{
        const [tags, wdEntity] = await Promise.all([
          fetchOsmTags(p.osm),
          fetchWikidataEntity(p.wikidata),
        ]);
        if (currentRender !== renderVersion) return;
        if (!tags || !wdEntity) return;
        const satRefs = wikidataSatRefs(wdEntity);
        const expectedQid = parseWikidataRef(p.wikidata);
        const wdHasSat = satIdMatches(satRefs, p.id);
        const osmRefSat = String(tags['ref:stockholmarchipelagotrail'] || '').trim();
        const osmMissingSatRef = !osmRefSat;

        if (showPoi && wdHasSat && osmMissingSatRef) {{
          const detail = [
            `Wikidata P14545 innehåller SAT-ID (<code>${{escapeHtml(p.id)}}</code>): <strong>ja</strong>`,
            `OSM tag <code>ref:stockholmarchipelagotrail</code>: <strong>saknas</strong>`,
          ].join('<br>');
          const popup = buildPopup(p, detail);
          L.marker([p.lat, p.lon], {{ icon: inconsistencyPoiIcon }}).bindPopup(popup).addTo(layerInconsistencyPoi);
        }}

        const osmWikidataTag = String(tags.wikidata || '').trim();
        const osmHasMatchingWd = !!expectedQid && osmWikidataTag === expectedQid;
        if (showOsmMissingWd && !osmHasMatchingWd) {{
          const detail = [
            `Förväntad OSM tag <code>wikidata</code>: <code>${{escapeHtml(expectedQid || 'okänd')}}</code>`,
            `Nuvarande OSM <code>wikidata</code>: <strong>${{escapeHtml(osmWikidataTag || 'saknas')}}</strong>`,
          ].join('<br>');
          const popup = buildPopup(p, detail);
          L.marker([p.lat, p.lon], {{ icon: inconsistencyOsmWdIcon }}).bindPopup(popup).addTo(layerInconsistencyOsmMissingWd);
        }}

        const wdHasOsm = hasWikidataOsmBacklink(wdEntity, p.osm);
        if (showWdMissingOsm && !wdHasOsm) {{
          const osmParsed = parseOsmRef(p.osm);
          const expectedProp = osmParsed?.type === 'node' ? 'P11693' : (osmParsed?.type === 'way' ? 'P10689' : (osmParsed?.type === 'relation' ? 'P402' : 'OSM-ID'));
          const detail = [
            `Wikidata saknar OSM-backlink för objektet <code>${{escapeHtml(p.osm)}}</code>`,
            `Förväntad egenskap i Wikidata: <strong>${{escapeHtml(expectedProp)}}</strong>`,
          ].join('<br>');
          const popup = buildPopup(p, detail);
          L.marker([p.lat, p.lon], {{ icon: inconsistencyWdOsmIcon }}).bindPopup(popup).addTo(layerInconsistencyWdMissingOsm);
        }}
      }});
    await Promise.all(tasks);
  }}

  // ── OSM Notes ─────────────────────────────────────────────────────────────
  // Fixed bbox covering the entire SAT trail (Arholma → Landsort)
  const TRAIL_BBOX = '17.6,58.65,19.4,59.95';

  const noteIcon = L.divIcon({{
    className: '',
    html: '<div style="width:20px;height:20px;border-radius:50%;background:#3b82f6;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font-size:11px">💬</div>',
    iconSize: [20,20], iconAnchor: [10,10], popupAnchor: [0,-12]
  }});

  async function loadOsmNotes() {{
    if (osmNotesLoaded) return;
    osmNotesLoaded = true;
    try {{
      // Fetch all open notes for the whole trail area in one request
      const url = `https://api.openstreetmap.org/api/0.6/notes.json?bbox=${{TRAIL_BBOX}}&limit=500&closed=0`;
      const resp = await fetch(url);
      const data = await resp.json();
      osmNotesLayer.clearLayers();
      const features = data.features || [];
      features.forEach(f => {{
        const [lon, lat] = f.geometry.coordinates;
        const comments = f.properties.comments || [];
        const first = comments[0] || {{}};
        const text = first.text || t('noText');
        const date = (first.date || '').slice(0,10);
        const noteId = f.properties.id;
        const m = L.marker([lat, lon], {{ icon: noteIcon }});
        m.bindPopup(`<div class="note-popup"><strong>💬 OSM Note #${{noteId}}</strong><br>${{escapeHtml(text)}}<br><small>${{date}}</small><br><a href="https://www.openstreetmap.org/note/${{noteId}}" target="_blank">${{t('openOnOsm')}}</a></div>`);
        osmNotesLayer.addLayer(m);
      }});
      console.log(`OSM Notes: ${{features.length}} öppna notes laddade`);
    }} catch(e) {{ console.warn('OSM Notes error', e); }}
  }}

  // Auto-load notes on start
  loadOsmNotes();

  // ── AED layer ─────────────────────────────────────────────────────────────
  const aedIcon = L.divIcon({{
    className: '',
    html: '<div style="width:22px;height:22px;border-radius:50%;background:#dc2626;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font-size:13px">🧡</div>',
    iconSize: [22,22], iconAnchor: [11,11], popupAnchor: [0,-13]
  }});
  let aedLoaded = false;
  function loadAed() {{
    if (aedLoaded) return;
    aedLoaded = true;
    layerAed.clearLayers();
    AED_POINTS.forEach((p) => {{
      const lat = p.lat;
      const lon = p.lon;
      const addr = [p.street, p.city].filter(Boolean).join(', ');
      const m = L.marker([lat, lon], {{ icon: aedIcon }});
      m.bindPopup(`<div style="font-size:13px;min-width:150px">
        <strong>🧡 ${{escapeHtml(p.name || 'AED')}}</strong><br>
        ${{p.owner ? `<small style="color:#64748b">${{escapeHtml(p.owner)}}</small><br>` : ''}}
        ${{addr ? `<div style="margin-top:4px">${{escapeHtml(addr)}}</div>` : ''}}
        ${{p.opening_hours ? `<div>🕐 ${{escapeHtml(p.opening_hours)}}</div>` : ''}}
        <div style="margin-top:5px;border-top:1px solid #e2e8f0;padding-top:4px;font-size:11px;color:#64748b">
          <a href="https://www.openstreetmap.org/note/new#map=18/${{lat}}/${{lon}}" target="_blank">💬 OSM Note</a>
        </div>
      </div>`);
      layerAed.addLayer(m);
    }});
    console.log(`AED: ${{AED_POINTS.length}} laddade`);
  }}

  const pierIcon = L.divIcon({{
    className: '',
    html: '<div style="width:22px;height:22px;border-radius:50%;background:#0ea5e9;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font-size:12px">⛴️</div>',
    iconSize: [22,22], iconAnchor: [11,11], popupAnchor: [0,-13]
  }});
  let piersLoaded = false;
  function loadPiers() {{
    if (piersLoaded) return;
    piersLoaded = true;
    layerPiers.clearLayers();
    PIER_POINTS.forEach((p) => {{
      const lat = p.lat;
      const lon = p.lon;
      const wdUrl = p.wikidataQid ? `https://www.wikidata.org/wiki/${{p.wikidataQid}}` : null;
      const satUrl = p.satId ? `https://map.stockholmarchipelagotrail.com/?${{encodeURIComponent(p.satId)}}` : null;
      const mapkiUrl = `https://mapki.com/map/#16/${{lat}}/${{lon}}`;
      const m = L.marker([lat, lon], {{ icon: pierIcon }});
      m.bindPopup(`<div style="font-size:13px;min-width:180px">
        <strong>⛴️ ${{escapeHtml(p.name || p.slug || p.satId)}}</strong><br>
        <small style="color:#64748b">${{satUrl ? `<a href="${{satUrl}}" target="_blank">${{escapeHtml(p.satId || '')}}</a>` : escapeHtml(p.satId || '')}}</small>
        ${{p.slug ? `<div>slug: <code>${{escapeHtml(p.slug)}}</code></div>` : ''}}
        ${{p.gtfsCount ? `<div>GTFS: ${{p.gtfsCount}}</div>` : ''}}
        ${{wdUrl ? `<div><a href="${{wdUrl}}" target="_blank">📚 Wikidata</a>${{p.wikidataLabel ? ` · ${{escapeHtml(p.wikidataLabel)}}` : ''}}</div>` : ''}}
        <div style="margin-top:5px;border-top:1px solid #e2e8f0;padding-top:4px;font-size:11px;color:#64748b">
          <a href="${{mapkiUrl}}" target="_blank">📍 Mapki history</a>
        </div>
      </div>`);
      layerPiers.addLayer(m);
    }});
    console.log(`Piers: ${{PIER_POINTS.length}} med koordinater från Wikidata`);
    if (MISSING_PIER_SAT_IDS.length > 0) {{
      console.warn(`Piers utan Wikidata-koordinater (${{MISSING_PIER_SAT_IDS.length}}):`, MISSING_PIER_SAT_IDS);
    }}
  }}

  // ── Mapillary layer ────────────────────────────────────────────────────────
  const mapillaryIcon = L.divIcon({{
    className: '',
    html: '<div style="width:22px;height:22px;border-radius:50%;background:#059669;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font-size:12px">📸</div>',
    iconSize: [22,22], iconAnchor: [11,11], popupAnchor: [0,-13]
  }});
  let mapillaryLoaded = false;
  function loadMapillary() {{
    if (mapillaryLoaded) return;
    mapillaryLoaded = true;
    layerMapillary.clearLayers();
    MAPILLARY_IMAGES.forEach((p) => {{
      const lat = p.lat;
      const lon = p.lon;
      const captured = p.capturedAt
        ? new Date(p.capturedAt).toLocaleString(lang === 'en' ? 'en-SE' : 'sv-SE')
        : '';
      const creatorUrl = p.creator ? `https://www.mapillary.com/app/user/${{encodeURIComponent(p.creator)}}` : '';
      const m = L.marker([lat, lon], {{ icon: mapillaryIcon }});
      m.bindPopup(`<div style="font-size:13px;min-width:190px;max-width:240px">
        ${{p.thumb ? `<a href="${{p.url}}" target="_blank"><img src="${{p.thumb}}" style="max-width:220px;border-radius:4px;display:block;margin-bottom:6px"></a>` : ''}}
        <strong>📸 Mapillary</strong>
        ${{captured ? `<div>🗓️ ${{escapeHtml(captured)}}</div>` : ''}}
        ${{p.creator ? `<div>👤 <a href="${{creatorUrl}}" target="_blank">${{escapeHtml(p.creator)}}</a></div>` : ''}}
        <div><a href="${{p.url}}" target="_blank">🔗 Mapillary</a></div>
      </div>`);
      layerMapillary.addLayer(m);
    }});
    console.log(`Mapillary: ${{MAPILLARY_IMAGES.length}} bilder laddade`);
  }}

  // ── Wikimedia Commons photos layer ────────────────────────────────────────
  const commonsIcon = L.divIcon({{
    className: '',
    html: '<div style="width:22px;height:22px;border-radius:50%;background:#3b5ba5;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3);display:flex;align-items:center;justify-content:center;font-size:13px">📷</div>',
    iconSize: [22,22], iconAnchor: [11,11], popupAnchor: [0,-13]
  }});
  let commonsLoaded = false;
  const commonsInfoCache = {{}};
  const commonsHiddenCategoryCache = {{}};

  function formatCommonsDate(raw) {{
    if (!raw) return '';
    try {{
      const d = new Date(raw.replace(' ', 'T'));
      return d.toLocaleString(lang === 'en' ? 'en-SE' : 'sv-SE', {{
        year: 'numeric', month: 'long', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      }});
    }} catch (e) {{
      return raw;
    }}
  }}

  function normalizeCommonsHtml(html) {{
    return String(html || '').replace(/href="\\/\\//g, 'href="https://');
  }}

  function categoryLinksHtml(cats) {{
    return cats.map(c =>
      `<a href="https://commons.wikimedia.org/wiki/Category:${{encodeURIComponent(c)}}" target="_blank">${{escapeHtml(c)}}</a>`
    ).join(' · ');
  }}

  function categoriesToHtml(visibleCats, hiddenCats = []) {{
    const visible = visibleCats || [];
    const hidden = hiddenCats || [];
    const total = visible.length + hidden.length;
    if (total === 0) return '';
    const title = lang === 'en' ? 'Categories' : 'Kategorier';
    const hiddenTitle = lang === 'en' ? 'Hidden categories' : 'Dolda kategorier';
    const visibleSection = `<details style="margin-top:4px">
      <summary style="cursor:pointer; user-select:none">🏷️ ${{title}} (${{visible.length}})</summary>
      <div style="margin-top:4px; max-height:120px; overflow:auto; line-height:1.4">${{categoryLinksHtml(visible)}}</div>
    </details>`;
    if (!hidden.length) return visibleSection;
    const hiddenSection = `<hr style="border:0;border-top:1px solid #e2e8f0;margin:8px 0 6px">
      <details>
        <summary style="cursor:pointer; user-select:none">🫥 ${{hiddenTitle}} (${{hidden.length}})</summary>
        <div style="margin-top:4px; max-height:90px; overflow:auto; line-height:1.4">${{categoryLinksHtml(hidden)}}</div>
      </details>`;
    return visibleSection + hiddenSection;
  }}

  async function splitCommonsCategories(cats) {{
    const all = (cats || []).filter(Boolean);
    if (!all.length) return {{ visible: [], hidden: [] }};
    const unknown = all.filter((c) => !Object.prototype.hasOwnProperty.call(commonsHiddenCategoryCache, c));
    if (unknown.length) {{
      try {{
        const titles = unknown.map((c) => `Category:${{c}}`).join('|');
        const params = new URLSearchParams({{
          action: 'query',
          titles,
          prop: 'categoryinfo',
          format: 'json',
          origin: '*',
        }});
        const res = await fetch(`https://commons.wikimedia.org/w/api.php?${{params.toString()}}`);
        const data = await res.json();
        const pages = data?.query?.pages || {{}};
        Object.values(pages).forEach((p) => {{
          const rawTitle = String(p?.title || '');
          const key = rawTitle.startsWith('Category:') ? rawTitle.slice('Category:'.length) : rawTitle;
          const ci = p?.categoryinfo || {{}};
          commonsHiddenCategoryCache[key] = Object.prototype.hasOwnProperty.call(ci, 'hidden');
        }});
      }} catch (_e) {{
        unknown.forEach((c) => {{
          if (!Object.prototype.hasOwnProperty.call(commonsHiddenCategoryCache, c)) commonsHiddenCategoryCache[c] = false;
        }});
      }}
    }}
    const visible = [];
    const hidden = [];
    all.forEach((c) => {{
      (commonsHiddenCategoryCache[c] ? hidden : visible).push(c);
    }});
    return {{ visible, hidden }};
  }}

  async function fetchCommonsImageInfo(fileTitle) {{
    if (!fileTitle) return null;
    if (commonsInfoCache[fileTitle]) return commonsInfoCache[fileTitle];
    try {{
      const params = new URLSearchParams({{
        action: 'query',
        titles: fileTitle.startsWith('File:') ? fileTitle : `File:${{fileTitle}}`,
        prop: 'imageinfo',
        iiprop: 'url|thumburl|extmetadata',
        iiextmetadatalanguage: 'sv',
        iiurlwidth: '250',
        format: 'json',
        origin: '*',
      }});
      const res = await fetch(`https://commons.wikimedia.org/w/api.php?${{params.toString()}}`);
      const data = await res.json();
      const pages = data?.query?.pages || {{}};
      const page = Object.values(pages)[0] || {{}};
      const ii = (page.imageinfo || [{{}}])[0];
      const em = ii.extmetadata || {{}};
      const catsRaw = (em.Categories || {{}}).value || '';
      const info = {{
        thumb: ii.thumburl || ii.url || '',
        date: (em.DateTimeOriginal || em.DateTime || {{}}).value || '',
        artist: (em.Artist || {{}}).value || '',
        cats: catsRaw ? catsRaw.split('|').map(c => c.trim()).filter(Boolean) : [],
      }};
      commonsInfoCache[fileTitle] = info;
      return info;
    }} catch (e) {{
      return null;
    }}
  }}

  // Fetch depicts (P180) from SDC and resolve Wikidata labels
  async function fetchDepicts(mid) {{
    try {{
      const sdcUrl = `https://commons.wikimedia.org/w/api.php?action=wbgetentities&ids=M${{mid}}&props=statements&format=json&origin=*`;
      const sdcRes = await fetch(sdcUrl);
      const sdcData = await sdcRes.json();
      const stmts = (sdcData.entities[`M${{mid}}`] || {{}}).statements || {{}};
      const p180 = stmts['P180'] || [];
      if (!p180.length) return [];
      const qids = p180.map(s => s.mainsnak?.datavalue?.value?.id).filter(Boolean);
      if (!qids.length) return [];
      const labelsUrl = `https://www.wikidata.org/w/api.php?action=wbgetentities&ids=${{qids.join('|')}}&props=labels&languages=sv|en&format=json&origin=*`;
      const labelsRes = await fetch(labelsUrl);
      const labelsData = await labelsRes.json();
      return qids.map(qid => {{
        const ent = labelsData.entities[qid] || {{}};
        const label = (ent.labels?.sv || ent.labels?.en || {{}}).value || qid;
        return {{ qid, label }};
      }});
    }} catch (e) {{
      return [];
    }}
  }}

  function loadCommons() {{
    if (commonsLoaded) return;
    commonsLoaded = true;
    layerCommons.clearLayers();
    COMMONS_PHOTOS.forEach((p, idx) => {{
      const m = L.marker([p.lat, p.lon], {{ icon: commonsIcon }});
      const popupKey = `${{p.mid || 0}}-${{idx}}`;
      const thumbId = `commons-thumb-${{popupKey}}`;
      const dateId = `commons-date-${{popupKey}}`;
      const artistId = `commons-artist-${{popupKey}}`;
      const catsId = `commons-cats-${{popupKey}}`;
      const depictsId = `depicts-${{popupKey}}`;

      const dateStr = formatCommonsDate(p.date);
      const thumbHtml = `<div id="${{thumbId}}">` + (p.thumb
        ? `<a href="${{p.url}}" target="_blank"><img src="${{p.thumb}}" style="max-width:220px;border-radius:4px;display:block;margin-bottom:6px"></a>`
        : '') + `</div>`;
      const dateHtml = `<div id="${{dateId}}">` + (dateStr ? `🗓️ ${{escapeHtml(dateStr)}}` : '') + `</div>`;
      const artistHtml = `<div id="${{artistId}}">` + (p.artist ? `👤 ${{normalizeCommonsHtml(p.artist)}}` : '') + `</div>`;
      const midHtml = p.mid
        ? `<hr style="border:0;border-top:1px solid #e2e8f0;margin:8px 0 6px">
           <div style="font-weight:600">SDC MediaInfo ID</div>
           <div style="font-size:11px;color:#64748b;margin:2px 0 4px">
             <a href="https://commons.wikimedia.org/wiki/Commons:Structured_data" target="_blank">SDC</a> ·
             <a href="https://www.mediawiki.org/wiki/Extension:WikibaseMediaInfo#MediaInfo_Entity" target="_blank">MediaInfo ID</a>
           </div>
           <div><a href="https://commons.wikimedia.org/entity/M${{p.mid}}" target="_blank">M${{p.mid}}</a> · <a href="https://commons.wikimedia.org/entity/M${{p.mid}}.json" target="_blank">JSON</a></div>`
        : '';
      const catsHtml = `<div id="${{catsId}}" style="margin-top:4px">${{categoriesToHtml(p.cats || [], [])}}</div>`;

      const popupContent = `<div style="font-size:13px;min-width:200px;max-width:240px">
        ${{thumbHtml}}
        <strong>📷 ${{escapeHtml(p.title)}}</strong>
        <div style="margin-top:5px;line-height:1.6">
          ${{dateHtml}}
          ${{artistHtml}}
          <div><a href="${{p.url}}" target="_blank">🔗 Wikimedia Commons</a></div>
          ${{midHtml}}
          <div id="${{depictsId}}" style="margin-top:4px;color:#64748b">⏳ Hämtar depicts…</div>
          ${{catsHtml}}
        </div>
      </div>`;

      m.bindPopup(popupContent, {{ maxWidth: 260 }});
      m.on('popupopen', async () => {{
        const depictsEl = document.getElementById(depictsId);
        if (depictsEl && !depictsEl.dataset.loaded && p.mid) {{
          depictsEl.dataset.loaded = '1';
          const depicts = await fetchDepicts(p.mid);
          if (depicts && depicts.length) {{
            depictsEl.innerHTML = '🎨 ' + depicts.map(d =>
              `<a href="https://www.wikidata.org/wiki/${{d.qid}}" target="_blank">${{escapeHtml(d.label)}}</a>`
            ).join(' · ');
          }} else {{
            depictsEl.textContent = '';
          }}
        }}

        const catsEl = document.getElementById(catsId);
        if (catsEl && !catsEl.dataset.classified && (p.cats || []).length) {{
          catsEl.dataset.classified = '1';
          const split = await splitCommonsCategories(p.cats || []);
          catsEl.innerHTML = categoriesToHtml(split.visible, split.hidden);
        }}

        const needMoreInfo = !p.thumb || !p.date || !p.artist || !(p.cats || []).length;
        if (!needMoreInfo) return;

        const info = await fetchCommonsImageInfo(p.title);
        if (!info) return;

        if (!p.thumb && info.thumb) {{
          p.thumb = info.thumb;
          const thumbEl = document.getElementById(thumbId);
          if (thumbEl) {{
            thumbEl.innerHTML = `<a href="${{p.url}}" target="_blank"><img src="${{p.thumb}}" style="max-width:220px;border-radius:4px;display:block;margin-bottom:6px"></a>`;
          }}
        }}
        if (!p.date && info.date) {{
          p.date = info.date;
          const dateEl = document.getElementById(dateId);
          if (dateEl) dateEl.innerHTML = `🗓️ ${{escapeHtml(formatCommonsDate(p.date))}}`;
        }}
        if (!p.artist && info.artist) {{
          p.artist = info.artist;
          const artistEl = document.getElementById(artistId);
          if (artistEl) artistEl.innerHTML = `👤 ${{normalizeCommonsHtml(p.artist)}}`;
        }}
        if (!(p.cats || []).length && (info.cats || []).length) {{
          p.cats = info.cats;
          const split = await splitCommonsCategories(p.cats || []);
          const catsEl2 = document.getElementById(catsId);
          if (catsEl2) {{
            catsEl2.dataset.classified = '1';
            catsEl2.innerHTML = categoriesToHtml(split.visible, split.hidden);
          }}
        }}
      }});

      layerCommons.addLayer(m);
    }});
    console.log(`Commons: ${{COMMONS_PHOTOS.length}} foton laddade`);
  }}

  map.on('overlayadd', (ev) => {{
    if (ev.layer === layerAed) loadAed();
    if (ev.layer === layerPiers) loadPiers();
    if (ev.layer === layerMapillary) loadMapillary();
    if (ev.layer === layerCommons) loadCommons();
  }});

  window.applyFilters = function() {{
    currentStage = stageFilter.value;
    currentCategory = categoryFilter.value;
    renderMarkers();
    renderList();
    saveStateInUrl();
  }};

  // ── Geolocation ───────────────────────────────────────────────────────────
  window.locateMe = function() {{
    if (!navigator.geolocation) {{ alert(t('geoNotSupported')); return; }}
    navigator.geolocation.getCurrentPosition(pos => {{
      const {{ latitude: lat, longitude: lon }} = pos.coords;
      if (locationMarker) map.removeLayer(locationMarker);
      locationMarker = L.circleMarker([lat, lon], {{
        radius: 8, fillColor:'#0f766e', color:'#fff', weight:2, fillOpacity:1
      }}).addTo(map).bindPopup(t('yourPosition')).openPopup();
      map.setView([lat, lon], 13);
      // Find nearest stage
      let nearest = null, minDist = Infinity;
      ALL_POIS.forEach(p => {{
        const d = Math.hypot(p.lat - lat, p.lon - lon);
        if (d < minDist) {{ minDist = d; nearest = p.section; }}
      }});
      if (nearest) {{
        stageFilter.value = nearest;
        currentStage = nearest;
        renderMarkers();
        renderList();
        saveStateInUrl();
      }}
    }}, err => alert(t('geoError') + err.message));
  }};

  // ── Tab switching ─────────────────────────────────────────────────────────
  window.showTab = function(tab) {{
    document.getElementById('map').style.display = tab==='map' ? 'block' : 'none';
    document.getElementById('list-view').style.display = tab==='list' ? 'block' : 'none';
    document.getElementById('tab-map').classList.toggle('active', tab==='map');
    document.getElementById('tab-list').classList.toggle('active', tab==='list');
    if (tab==='map') map.invalidateSize();
    if (tab==='list') renderList();
    saveStateInUrl();
  }};

  // ── List view ─────────────────────────────────────────────────────────────
  function renderList() {{
    const container = document.getElementById('list-view');
    const rows = filteredPois().slice().sort((a, b) =>
      (a.section || '').localeCompare(b.section || '') ||
      (a.category || '').localeCompare(b.category || '') ||
      (a.name || '').localeCompare(b.name || '')
    );
    if (rows.length === 0) {{
      container.innerHTML = `<p style="padding:20px;text-align:center;color:#64748b">${{t('noObjects')}}</p>`;
      return;
    }}
    container.innerHTML = `<div class="todo-table-wrap"><table class="todo-table">
      <thead>
        <tr>
          <th>${{t('thStage')}}</th>
          <th>${{t('thPoi')}}</th>
          <th>${{t('thOsmName')}}</th>
          <th>${{t('thCategory')}}</th>
          <th>${{t('thMissing')}}</th>
          <th>${{t('thFixme')}}</th>
          <th>${{t('thNote')}}</th>
          <th>${{t('thCheckDate')}}</th>
          <th>${{t('thLinks')}}</th>
        </tr>
      </thead>
      <tbody>
        ${{rows.map(p => {{
          const chips = p.missing.map(m => {{
            const labels = {{osm:'OSM', wikidata:'WD', image:'📷'}};
            return `<span class="mini-chip ${{m==='wikidata'?'wd':m}}">${{labels[m]||m}}</span>`;
          }}).join('');
          const satMapUrl = p.id ? `https://map.stockholmarchipelagotrail.com/?${{p.id}}` : null;
          const satJsonUrl = p.id ? `https://map.stockholmarchipelagotrail.com/api/objects/${{encodeURIComponent(p.id)}}` : null;
          return `<tr data-poi-key="${{encodeURIComponent(p.id || '')}}">
            <td>${{escapeHtml(p.section || '')}}</td>
            <td class="poi-name">${{escapeHtml(p.name || t('noName'))}}</td>
            <td data-field="osm_name"><span class="muted">—</span></td>
            <td>${{escapeHtml(p.category || '')}}</td>
            <td><span class="missing-tags">${{chips}}</span></td>
            <td data-field="fixme">${{p.fixme ? escapeHtml(p.fixme) : '<span class="muted">—</span>'}}</td>
            <td data-field="note">${{p.note ? escapeHtml(p.note) : '<span class="muted">—</span>'}}</td>
            <td data-field="check_date"><span class="muted">—</span></td>
            <td>
              ${{satMapUrl ? `<a href="${{satMapUrl}}" target="_blank">SAT</a> · <a href="${{satJsonUrl}}" target="_blank">JSON</a> · ` : ''}}
              <button class="poi-goto" onclick="gotoOnMap(${{p.lat}},${{p.lon}})" title="${{t('showOnMap')}}">📍</button>
            </td>
          </tr>`;
        }}).join('')}}
      </tbody>
    </table></div>`;
    hydrateListOsmTags(rows);
  }}

  async function hydrateListOsmTags(rows) {{
    const tasks = rows
      .filter((p) => !!p.osm)
      .map(async (p) => {{
        const tags = await fetchOsmTags(p.osm);
        if (!tags) return;
        const key = encodeURIComponent(p.id || '');
        const row = document.querySelector(`tr[data-poi-key="${{key}}"]`);
        if (!row) return;
        const fixmeText = tags.fixme || p.fixme || '';
        const noteText = tags.note || p.note || '';
        const checkDateText = tags.check_date || '';
        const osmNameText = tags.name || '';
        row.querySelector('[data-field="osm_name"]').innerHTML = osmNameText ? escapeHtml(osmNameText) : '<span class="muted">—</span>';
        row.querySelector('[data-field="fixme"]').innerHTML = fixmeText ? escapeHtml(fixmeText) : '<span class="muted">—</span>';
        row.querySelector('[data-field="note"]').innerHTML = noteText ? escapeHtml(noteText) : '<span class="muted">—</span>';
        row.querySelector('[data-field="check_date"]').innerHTML = checkDateText ? escapeHtml(checkDateText) : '<span class="muted">—</span>';
      }});
    await Promise.all(tasks);
  }}

  window.gotoOnMap = function(lat, lon) {{
    showTab('map');
    map.setView([lat, lon], 16);
    saveStateInUrl();
  }};

  function escapeHtml(s) {{
    return String(s||'').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[c]));
  }}

  // ── Init ──────────────────────────────────────────────────────────────────
  applyStateFromUrl();
  applyLanguage();
  renderMarkers();
  loadOsmNotes();
  showTab(initialTab);
  saveStateInUrl();
}})();
</script>
</body>
</html>"""

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"✅ {OUTPUT} sparad")
