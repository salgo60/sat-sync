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
    #list-view {{ flex:1; min-height:0; overflow-y:auto; display:none; }}
    .stage-card {{ background:#fff; margin:8px 10px; border-radius:10px; box-shadow:0 1px 3px rgba(0,0,0,0.08); overflow:hidden; }}
    .stage-head {{ padding:10px 14px; display:flex; align-items:center; gap:8px; cursor:pointer; }}
    .stage-head h3 {{ margin:0; font-size:0.95rem; flex:1; text-transform:capitalize; }}
    .badge {{ display:inline-flex; align-items:center; justify-content:center; border-radius:9999px; width:22px; height:22px; font-size:0.72rem; font-weight:700; }}
    .badge.osm  {{ background:#fee2e2; color:#991b1b; }}
    .badge.wd   {{ background:#fef3c7; color:#92400e; }}
    .badge.img  {{ background:#ede9fe; color:#5b21b6; }}
    .stage-body {{ display:none; border-top:1px solid #f1f5f9; }}
    .poi-row {{ padding:8px 14px; border-bottom:1px solid #f1f5f9; font-size:0.82rem; display:flex; align-items:center; gap:6px; }}
    .poi-row:last-child {{ border-bottom:none; }}
    .poi-row .poi-name {{ flex:1; }}
    .poi-row .missing-tags {{ display:flex; gap:4px; }}
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

  // State
  let currentStage = 'all';
  let currentCategory = 'all';
  let locationMarker = null;
  let osmNotesLoaded = false;

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

  // ── Problem layers (one per issue type) ───────────────────────────────────
  const layerMissingOsm = L.layerGroup().addTo(map);
  const layerMissingWd  = L.layerGroup().addTo(map);
  const layerMissingImg = L.layerGroup().addTo(map);
  const osmNotesLayer   = L.layerGroup().addTo(map);

  // Layer control — shown in map top-right
  L.control.layers(null, {{
    '❌ Saknar OSM-länk':    layerMissingOsm,
    '📋 Saknar Wikidata':   layerMissingWd,
    '📷 Saknar bild':       layerMissingImg,
    '💬 OSM Notes':         osmNotesLayer,
  }}, {{ collapsed: false, position: 'topright' }}).addTo(map);

  function filteredPois() {{
    return ALL_POIS.filter(p => {{
      if (currentStage !== 'all' && p.section !== currentStage) return false;
      if (currentCategory !== 'all' && p.category !== currentCategory) return false;
      return true;
    }});
  }}

  function buildPopup(p) {{
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
    return `<div style="min-width:160px;font-size:13px">
      <strong>${{escapeHtml(p.name)}}</strong><br>
      <small style="color:#64748b">${{escapeHtml(p.section)}} · ${{escapeHtml(p.category)}}</small><br>
      <div style="margin:5px 0">${{tags}}</div>
      ${{satMapUrl ? `<div><a href="${{satMapUrl}}" target="_blank">🗺️ SAT-kartan</a> · <a href="${{satJsonUrl}}" target="_blank">🧾 SAT JSON</a></div>` : ''}}
      ${{osmUrl ? `<div><a href="${{osmUrl}}" target="_blank">🔗 OSM</a> · <a href="${{idUrl}}" target="_blank">✏️ iD editor</a></div>` : '<div style="color:#ef4444;font-size:11px">❌ Ingen OSM-länk</div>'}}
      ${{wdUrl  ? `<div><a href="${{wdUrl}}" target="_blank">📚 Wikidata</a></div>` : '<div style="color:#f59e0b;font-size:11px">❌ Ingen Wikidata-länk</div>'}}
      ${{p.website ? `<div><a href="${{p.website}}" target="_blank">🌐 Webbplats</a></div>` : ''}}
      <div style="margin-top:6px;border-top:1px solid #e2e8f0;padding-top:5px">
        <div><a href="${{wikimapUrl}}" target="_blank">🗺️ Wikimap</a></div>
        <div><a href="${{newNoteUrl}}" target="_blank">💬 Skapa OSM Note här</a></div>
      </div>
    </div>`;
  }}

  function renderMarkers() {{
    layerMissingOsm.clearLayers();
    layerMissingWd.clearLayers();
    layerMissingImg.clearLayers();
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
  }};

  // ── List view ─────────────────────────────────────────────────────────────
  function renderList() {{
    const container = document.getElementById('list-view');
    const stageMap = {{}};
    filteredPois().forEach(p => {{
      if (!stageMap[p.section]) stageMap[p.section] = [];
      stageMap[p.section].push(p);
    }});
    const stagesShown = Object.keys(stageMap).sort();
    if (stagesShown.length === 0) {{
      container.innerHTML = '<p style="padding:20px;text-align:center;color:#64748b">Inga objekt matchar aktiva filter.</p>';
      return;
    }}
    container.innerHTML = stagesShown.map(s => {{
      const pois = stageMap[s];
      const noOsm = pois.filter(p => p.missing.includes('osm')).length;
      const noWd  = pois.filter(p => p.missing.includes('wikidata')).length;
      const noImg = pois.filter(p => p.missing.includes('image')).length;
      const rows = pois.map(p => {{
        const chips = p.missing.map(m => {{
          const labels = {{osm:'OSM', wikidata:'WD', image:'📷'}};
          return `<span class="mini-chip ${{m==='wikidata'?'wd':m}}">${{labels[m]||m}}</span>`;
        }}).join('');
        return `<div class="poi-row">
          <span class="poi-name">${{escapeHtml(p.name)}}</span>
          <span class="missing-tags">${{chips}}</span>
          <button class="poi-goto" onclick="gotoOnMap('${{s}}','map',${{p.lat}},${{p.lon}})" title="Visa på karta">📍</button>
        </div>`;
      }}).join('');
      return `<div class="stage-card">
        <div class="stage-head" onclick="toggleStageBody(this)">
          <h3>${{s.charAt(0).toUpperCase()+s.slice(1)}}</h3>
          ${{noOsm?`<span class="badge osm" title="Saknar OSM">${{noOsm}}</span>`:''}}</span>
          ${{noWd ?`<span class="badge wd"  title="Saknar WD">${{noWd}}</span>`:''}}
          ${{noImg?`<span class="badge img" title="Saknar bild">${{noImg}}</span>`:''}}
          <span style="font-size:1rem">▾</span>
        </div>
        <div class="stage-body">${{rows}}</div>
      </div>`;
    }}).join('');
  }}

  window.toggleStageBody = function(el) {{
    const body = el.nextElementSibling;
    body.style.display = body.style.display === 'block' ? 'none' : 'block';
  }};

  window.gotoOnMap = function(stage, tab, lat, lon) {{
    showTab('map');
    map.setView([lat, lon], 16);
  }};

  function escapeHtml(s) {{
    return String(s||'').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[c]));
  }}

  // ── Init ──────────────────────────────────────────────────────────────────
  renderMarkers();
  loadOsmNotes();
}})();
</script>
</body>
</html>"""

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write(html)
print(f"✅ {OUTPUT} sparad")
