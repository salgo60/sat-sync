#!/usr/bin/env python3
"""Generate sat_todo_map.html — mobile-friendly TODO map for SAT POI data gaps."""

import json, urllib.request, datetime

POIS_URL   = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
TRAIL_URL  = "https://map.stockholmarchipelagotrail.com/data/trail.jsonld"
SECTIONS_URL = "https://map.stockholmarchipelagotrail.com/data/sections-index.json"
OUTPUT     = "sat_todo_map.html"

HEADERS = {"User-Agent": "sat-sync/todo-map 1.0"}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        return json.load(r)

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

html = f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
  <title>SAT TODO – Vad saknas?</title>
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
    <h1>🗺️ SAT TODO – Vad saknas?</h1>
    <div class="meta">
      {generated_at} &nbsp;
      <a href="sat_poi_dashboard.html">Dashboard</a>
    </div>
  </div>

  <div class="tabs">
    <button class="tab active" id="tab-map" onclick="showTab('map')">🗺️ Karta</button>
    <button class="tab" id="tab-list" onclick="showTab('list')">📋 Lista</button>
  </div>

  <div class="filter-bar">
    <select id="stageFilter" onchange="applyFilters()">
      <option value="all">Alla etapper</option>
    </select>
    <select id="categoryFilter" onchange="applyFilters()">
      <option value="all">Alla kategorier</option>
    </select>
    <button class="loc-btn" onclick="locateMe()">📍 Nära mig</button>
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
  const OSM_TAG_CACHE = {{}};
  const WD_ENTITY_CACHE = {{}};

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
  }};

  // Layer control — shown in map top-right
  L.control.layers(null, {{
    '❌ Saknar OSM-länk':    layerMissingOsm,
    '📋 Saknar Wikidata':   layerMissingWd,
    '📷 Saknar bild':       layerMissingImg,
    '♿ Wheelchair':         layerWheelchair,
    '◻️ Saknar Wheelchair': layerMissingWheelchair,
    'Inkonsekvens POI': layerInconsistencyPoi,
    'Inkonsekvens OSM saknar koppling WD': layerInconsistencyOsmMissingWd,
    'Inkonsekvens WD saknar koppling OSM': layerInconsistencyWdMissingOsm,
    '💬 OSM Notes':         osmNotesLayer,
  }}, {{ collapsed: false, position: 'topright' }}).addTo(map);

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

  function openIdWithCheckDate(idUrl) {{
    const today = new Date().toISOString().slice(0, 10);
    const tagText = `check_date=${{today}}`;
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      navigator.clipboard.writeText(tagText).catch(() => {{}});
    }}
    window.open(idUrl, '_blank', 'noopener');
    return false;
  }}

  function buildPopup(p, inconsistencyInfo = null) {{
    const tags = p.missing.map(tag => {{
      const labels = {{osm:'Saknar OSM', wikidata:'Saknar Wikidata', image:'Saknar bild'}};
      const colors = {{osm:'#ef4444', wikidata:'#f59e0b', image:'#8b5cf6'}};
      return `<span style="background:${{colors[tag]||'#888'}};color:#fff;padding:1px 6px;border-radius:10px;font-size:11px;margin-right:3px">${{labels[tag]||tag}}</span>`;
    }}).join('');
    const osmUrl = p.osm ? `https://www.openstreetmap.org/${{p.osm.replace('osm:node:','node/').replace('osm:way:','way/').replace('osm:relation:','relation/')}}` : null;
    const idUrl  = p.osm ? `https://www.openstreetmap.org/edit?editor=id&${{p.osm.replace('osm:','')}}#map=18/${{p.lat}}/${{p.lon}}` : null;
    const wdUrl  = p.wikidata ? `https://www.wikidata.org/wiki/${{p.wikidata.replace('wikidata:','')}}` : null;
    const satMapUrl = p.id ? `https://map.stockholmarchipelagotrail.com/?${{p.id}}` : null;
    const satJsonUrl = p.id ? `https://map.stockholmarchipelagotrail.com/api/objects/${{encodeURIComponent(p.id)}}` : null;
    const newNoteUrl = `https://www.openstreetmap.org/note/new#map=18/${{p.lat}}/${{p.lon}}`;
    const wikimapUrl = `https://wikimap.toolforge.org/?lat=${{p.lat}}&lon=${{p.lon}}&zoom=15&lang=en&wp=false&cluster=false`;
    const inconsistencyHtml = inconsistencyInfo
      ? `<details style="margin-top:6px"><summary>⚠️ Inkonsekvens-kontroll</summary><div style="font-size:12px;margin-top:4px">${{inconsistencyInfo}}</div></details>`
      : `<details style="margin-top:6px"><summary>⚠️ Inkonsekvens-kontroll</summary><div style="font-size:12px;margin-top:4px">Kontroller: <br>1) Inkonsekvens POI: Wikidata P14545 har SAT-ID men OSM saknar <code>ref:stockholmarchipelagotrail</code>.<br>2) Inkonsekvens OSM saknar koppling WD: OSM saknar/avviker i taggen <code>wikidata</code>.<br>3) Inkonsekvens WD saknar koppling OSM: Wikidata saknar OSM-ID (node/way/relation) tillbaka till objektet.</div></details>`;
    return `<div style="min-width:160px;font-size:13px">
      <strong>${{escapeHtml(p.name)}}</strong><br>
      <small style="color:#64748b">${{escapeHtml(p.section)}} · ${{escapeHtml(p.category)}}</small><br>
      <div style="margin:5px 0">${{tags}}</div>
      ${{satMapUrl ? `<div><a href="${{satMapUrl}}" target="_blank">🗺️ SAT-kartan</a> · <a href="${{satJsonUrl}}" target="_blank">🧾 SAT JSON</a></div>` : ''}}
      ${{osmUrl ? `<div><a href="${{osmUrl}}" target="_blank">🔗 OSM</a> · <a href="${{idUrl}}" target="_blank">✏️ iD editor</a></div><div><a href="${{idUrl}}" target="_blank" onclick="return openIdWithCheckDate(this.href)">🗓️ check_date=today (iD)</a></div>` : '<div style="color:#ef4444;font-size:11px">❌ Ingen OSM-länk</div>'}}
      ${{wdUrl  ? `<div><a href="${{wdUrl}}" target="_blank">📚 Wikidata</a></div>` : '<div style="color:#f59e0b;font-size:11px">❌ Ingen Wikidata-länk</div>'}}
      ${{p.website ? `<div><a href="${{p.website}}" target="_blank">🌐 Webbplats</a></div>` : ''}}
      <div style="margin-top:6px;border-top:1px solid #e2e8f0;padding-top:5px">
        <div><a href="${{wikimapUrl}}" target="_blank">🗺️ Wikimap</a></div>
        <div><a href="${{newNoteUrl}}" target="_blank">💬 Skapa OSM Note här</a></div>
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
        const text = first.text || '(ingen text)';
        const date = (first.date || '').slice(0,10);
        const noteId = f.properties.id;
        const m = L.marker([lat, lon], {{ icon: noteIcon }});
        m.bindPopup(`<div class="note-popup"><strong>💬 OSM Note #${{noteId}}</strong><br>${{escapeHtml(text)}}<br><small>${{date}}</small><br><a href="https://www.openstreetmap.org/note/${{noteId}}" target="_blank">Öppna på OSM</a></div>`);
        osmNotesLayer.addLayer(m);
      }});
      console.log(`OSM Notes: ${{features.length}} öppna notes laddade`);
    }} catch(e) {{ console.warn('OSM Notes error', e); }}
  }}

  // Auto-load notes on start
  loadOsmNotes();

  window.applyFilters = function() {{
    currentStage = stageFilter.value;
    currentCategory = categoryFilter.value;
    renderMarkers();
    renderList();
    saveStateInUrl();
  }};

  // ── Geolocation ───────────────────────────────────────────────────────────
  window.locateMe = function() {{
    if (!navigator.geolocation) {{ alert('Geolocation stöds inte i din webbläsare.'); return; }}
    navigator.geolocation.getCurrentPosition(pos => {{
      const {{ latitude: lat, longitude: lon }} = pos.coords;
      if (locationMarker) map.removeLayer(locationMarker);
      locationMarker = L.circleMarker([lat, lon], {{
        radius: 8, fillColor:'#0f766e', color:'#fff', weight:2, fillOpacity:1
      }}).addTo(map).bindPopup('📍 Din position').openPopup();
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
    }}, err => alert('Kunde inte hämta position: ' + err.message));
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
      container.innerHTML = '<p style="padding:20px;text-align:center;color:#64748b">Inga objekt matchar aktiva filter.</p>';
      return;
    }}
    container.innerHTML = `<div class="todo-table-wrap"><table class="todo-table">
      <thead>
        <tr>
          <th>Etapp</th>
          <th>POI</th>
          <th>OSM name</th>
          <th>Kategori</th>
          <th>Saknas</th>
          <th>fixme (OSM)</th>
          <th>note (OSM)</th>
          <th>check_date (OSM)</th>
          <th>Länkar</th>
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
            <td class="poi-name">${{escapeHtml(p.name || '(utan namn)')}}</td>
            <td data-field="osm_name"><span class="muted">—</span></td>
            <td>${{escapeHtml(p.category || '')}}</td>
            <td><span class="missing-tags">${{chips}}</span></td>
            <td data-field="fixme">${{p.fixme ? escapeHtml(p.fixme) : '<span class="muted">—</span>'}}</td>
            <td data-field="note">${{p.note ? escapeHtml(p.note) : '<span class="muted">—</span>'}}</td>
            <td data-field="check_date"><span class="muted">—</span></td>
            <td>
              ${{satMapUrl ? `<a href="${{satMapUrl}}" target="_blank">SAT</a> · <a href="${{satJsonUrl}}" target="_blank">JSON</a> · ` : ''}}
              <button class="poi-goto" onclick="gotoOnMap(${{p.lat}},${{p.lon}})" title="Visa på karta">📍</button>
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
