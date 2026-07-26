#!/usr/bin/env python3
"""Generate sat_todo_list.html — task-oriented TODO list for SAT POIs."""

import datetime
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from typing import Optional

POIS_URL = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
SECTIONS_INDEX_URL = "https://map.stockholmarchipelagotrail.com/data/sections-index.json"
OUTPUT = "sat_todo_list.html"

HEADERS = {"User-Agent": "sat-sync/todo-list 1.0"}
OPENING_HOURS_CATEGORIES = {"food", "shop", "lodging", "rental", "sauna", "harbour"}
NOTES_PADDING = 0.015


def fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8"))


def normalize_slug(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"^sat\s+", "", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def pick_text(value) -> Optional[str]:
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("sv", "en", "mul", "url", "value"):
            v = value.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in value.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def extract_osm_ref(same_as: list[str]) -> Optional[dict]:
    if not isinstance(same_as, list):
        return None
    for ref in same_as:
        if not isinstance(ref, str) or not ref.startswith("osm:"):
            continue
        parts = ref.split(":")
        if len(parts) != 3:
            continue
        osm_type, osm_id = parts[1], parts[2]
        if osm_type not in {"node", "way", "relation"} or not osm_id:
            continue
        return {"type": osm_type, "id": osm_id, "key": f"{osm_type}/{osm_id}"}
    return None


def fetch_osm_operator(osm_ref: dict) -> Optional[dict]:
    """Fetch operator/brand info from OSM API for given element."""
    if not osm_ref or not osm_ref.get("type") or not osm_ref.get("id"):
        return None
    try:
        url = f"https://api.openstreetmap.org/api/0.6/{osm_ref['type']}/{osm_ref['id']}.json"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        el = (data.get("elements") or [{}])[0]
        tags = el.get("tags", {})
        
        # Try operator first, then brand
        operator = tags.get("operator", "")
        operator_wd = tags.get("operator:wikidata", "")
        brand = tags.get("brand", "")
        brand_wd = tags.get("brand:wikidata", "")
        
        # Prefer operator if present, otherwise use brand
        if operator or operator_wd:
            return {
                "name": operator or operator_wd,
                "wikidata": operator_wd or None,
                "type": "operator",
            }
        elif brand or brand_wd:
            return {
                "name": brand or brand_wd,
                "wikidata": brand_wd or None,
                "type": "brand",
            }
    except Exception:
        pass
    return None


def fetch_open_notes_count(min_lat: float, min_lon: float, max_lat: float, max_lon: float) -> Optional[int]:
    params = urllib.parse.urlencode(
        {
            "bbox": f"{min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}",
            "closed": "0",
            "limit": "200",
        }
    )
    url = f"https://api.openstreetmap.org/api/0.6/notes.json?{params}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read().decode("utf-8"))
        features = payload.get("features") if isinstance(payload, dict) else []
        return len(features or [])
    except Exception:
        return None


def build_page() -> str:
    pois_data = fetch_json(POIS_URL)
    sections_data = fetch_json(SECTIONS_INDEX_URL)
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    features = pois_data.get("features", []) if isinstance(pois_data, dict) else []
    pois: list[dict] = []
    section_bounds: dict[str, dict] = {}
    for feat in features:
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", {}) or {}
        coords = geom.get("coordinates") or []
        if geom.get("type") != "Point" or not isinstance(coords, list) or len(coords) < 2:
            continue
        lon, lat = coords[0], coords[1]
        section = str(props.get("section") or "").strip() or "unknown"
        osm_ref = extract_osm_ref(props.get("sameAs") or [])
        operator_info = fetch_osm_operator(osm_ref) if osm_ref else None
        poi = {
            "id": props.get("id") or "",
            "name": props.get("name") or "",
            "section": section,
            "category": str(props.get("category") or "").strip() or "unknown",
            "same_as": props.get("sameAs") or [],
            "image": pick_text(props.get("image")),
            "lat": lat,
            "lon": lon,
            "osm_ref": osm_ref,
            "operator": operator_info,
        }
        pois.append(poi)

        bounds = section_bounds.setdefault(section, {"min_lat": lat, "max_lat": lat, "min_lon": lon, "max_lon": lon})
        bounds["min_lat"] = min(bounds["min_lat"], lat)
        bounds["max_lat"] = max(bounds["max_lat"], lat)
        bounds["min_lon"] = min(bounds["min_lon"], lon)
        bounds["max_lon"] = max(bounds["max_lon"], lon)

    section_lookup: dict[str, dict] = {}
    if isinstance(sections_data, list):
        for item in sections_data:
            slug = str(item.get("slug") or "").strip()
            if not slug:
                continue
            center = item.get("center") or [None, None]
            section_lookup[slug] = {
                "slug": slug,
                "title": item.get("title") or slug,
                "order": item.get("orderInTrail") if item.get("orderInTrail") is not None else 999,
                "lat": center[1] if isinstance(center, list) and len(center) >= 2 else None,
                "lon": center[0] if isinstance(center, list) and len(center) >= 2 else None,
            }

    def section_label(section_slug: str) -> str:
        sec = section_lookup.get(section_slug)
        if sec and sec.get("title"):
            return f"SAT {sec['title']}"
        return section_slug

    all_sections = sorted(
        {p["section"] for p in pois},
        key=lambda s: (
            0 if s in section_lookup else 1,
            section_lookup.get(s, {}).get("order", 999),
            section_label(s).lower(),
        ),
    )
    all_categories = sorted({p["category"] for p in pois})
    
    # Predefined known organisations
    known_organisations = {
        'Skärgårdsstiftelsen',
        'Stockholm Archipelago Trail',
        'Waxholmsbolaget',
        'Haninge kommun',
        'Norrtälje kommun',
        'Värmdö kommun',
        'Österåkers kommun',
        'Nynäshamns kommun',
        'Arholma Nord',
        'Grinda Wärdshus',
        'STF Finnhamn vandrarhem',
        'STF Möja vandrarhem',
        'Svedtiljas',
        'Vandrarhem Bull-August gård',
        'Naturvårdsverket',
        'Länsstyrelsen Stockholms län',
    }
    
    # Collect operators from data
    data_operators = {p["operator"]["name"] for p in pois if p["operator"]} or {"(unknown)"}
    
    # Combine known organisations with data operators
    all_operators = sorted(known_organisations | data_operators)

    tasks: list[dict] = []
    for p in pois:
        section = p["section"]
        sec_label = section_label(section)
        sat_url = f"https://map.stockholmarchipelagotrail.com/?{urllib.parse.quote(p['id'])}" if p["id"] else ""
        osm_ref = p["osm_ref"]
        osm_url = f"https://www.openstreetmap.org/{osm_ref['type']}/{osm_ref['id']}" if osm_ref else ""
        id_url = (
            f"https://www.openstreetmap.org/edit?editor=id&{osm_ref['type']}={osm_ref['id']}#map=18/{p['lat']}/{p['lon']}"
            if osm_ref
            else ""
        )
        operator_name = p["operator"]["name"] if p["operator"] else "(unknown)"
        operator_wd = p["operator"].get("wikidata") if p["operator"] else None

        if not p["image"]:
            tasks.append(
                {
                    "id": f"photo:{p['id']}",
                    "type": "photo",
                    "section": section,
                    "sectionLabel": sec_label,
                    "category": p["category"],
                    "poiId": p["id"],
                    "poiName": p["name"] or p["id"],
                    "operator": operator_name,
                    "operatorWikidata": operator_wd,
                    "taskTextSv": "Ta/uppdatera bild och ladda upp till Commons",
                    "taskTextEn": "Take/update photo and upload to Commons",
                    "links": {"sat": sat_url, "osm": osm_url, "id": id_url, "notes": ""},
                }
            )

        if p["category"] in OPENING_HOURS_CATEGORIES:
            tasks.append(
                {
                    "id": f"opening_hours:{p['id']}",
                    "type": "opening_hours",
                    "section": section,
                    "sectionLabel": sec_label,
                    "category": p["category"],
                    "poiId": p["id"],
                    "poiName": p["name"] or p["id"],
                    "operator": operator_name,
                    "operatorWikidata": operator_wd,
                    "taskTextSv": "Kontrollera öppettider och uppdatera OSM/SAT vid behov",
                    "taskTextEn": "Check opening hours and update OSM/SAT if needed",
                    "links": {"sat": sat_url, "osm": osm_url, "id": id_url, "notes": ""},
                }
            )

        if osm_ref:
            tasks.append(
                {
                    "id": f"wheelchair:{p['id']}",
                    "type": "wheelchair",
                    "section": section,
                    "sectionLabel": sec_label,
                    "category": p["category"],
                    "poiId": p["id"],
                    "poiName": p["name"] or p["id"],
                    "operator": operator_name,
                    "operatorWikidata": operator_wd,
                    "taskTextSv": "Lägg till eller verifiera wheelchair-tag i OSM",
                    "taskTextEn": "Add or verify wheelchair tag in OSM",
                    "links": {"sat": sat_url, "osm": osm_url, "id": id_url, "notes": ""},
                }
            )

    for section in all_sections:
        bounds = section_bounds.get(section)
        sec_meta = section_lookup.get(section) or {}
        lat = sec_meta.get("lat")
        lon = sec_meta.get("lon")
        if bounds:
            min_lat = bounds["min_lat"] - NOTES_PADDING
            max_lat = bounds["max_lat"] + NOTES_PADDING
            min_lon = bounds["min_lon"] - NOTES_PADDING
            max_lon = bounds["max_lon"] + NOTES_PADDING
            if lat is None or lon is None:
                lat = (bounds["min_lat"] + bounds["max_lat"]) / 2
                lon = (bounds["min_lon"] + bounds["max_lon"]) / 2
        elif lat is not None and lon is not None:
            min_lat = lat - 0.04
            max_lat = lat + 0.04
            min_lon = lon - 0.04
            max_lon = lon + 0.04
        else:
            continue

        notes_count = fetch_open_notes_count(min_lat, min_lon, max_lat, max_lon)
        notes_link = f"https://www.openstreetmap.org/#map=13/{lat:.5f}/{lon:.5f}&layers=N"
        count_sv = "okänt antal" if notes_count is None else str(notes_count)
        count_en = "unknown count" if notes_count is None else str(notes_count)
        tasks.append(
            {
                "id": f"osm_notes:{section}",
                "type": "osm_notes",
                "section": section,
                "sectionLabel": section_label(section),
                "category": "island",
                "poiId": "",
                "poiName": "",
                "taskTextSv": f"Gå igenom öppna OSM Notes på ön ({count_sv})",
                "taskTextEn": f"Review open OSM Notes on island ({count_en})",
                "links": {"sat": "", "osm": "", "id": "", "notes": notes_link},
            }
        )

    tasks.sort(key=lambda t: (all_sections.index(t["section"]) if t["section"] in all_sections else 999, t["type"], t["poiName"]))
    tasks_json = json.dumps(tasks, ensure_ascii=False)
    sections_json = json.dumps([{"value": s, "label": section_label(s)} for s in all_sections], ensure_ascii=False)
    categories_json = json.dumps(all_categories, ensure_ascii=False)
    operators_json = json.dumps(all_operators, ensure_ascii=False)
    generated_at_json = json.dumps(generated_at, ensure_ascii=False)

    template = """<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAT TODO-lista</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f3f6fb; color: #1f2937; }
    .container { max-width: 1300px; margin: 0 auto; padding: 0 14px 28px; }
    .header { background: linear-gradient(135deg,#2546a8,#1d2f6f); color: #fff; margin: 0 -14px; padding: 20px 16px 16px; }
    .header h1 { margin: 0 0 8px; font-size: 1.45rem; }
    .sub { opacity: .92; margin: 0 0 8px; font-size: .94rem; }
    .meta { font-size: .8rem; opacity: .85; line-height: 1.6; }
    .meta a { color: #a8c4ff; text-decoration: none; }
    .meta a:hover { text-decoration: underline; }
    .lang-btn { margin-left: 8px; padding: 4px 10px; border: 1px solid rgba(255,255,255,.5); border-radius: 6px; background: rgba(255,255,255,.2); color:#fff; cursor:pointer; font-size:.75rem; font-weight:600; }
    .panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; margin-top: 12px; }
    .filters { display: flex; flex-wrap: wrap; gap: 10px; align-items: end; }
    .filters label { display: block; font-size: .77rem; color: #475569; margin-bottom: 4px; font-weight: 600; }
    .filters select, .filters input[type="text"] { min-width: 170px; padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; }
    .filters .actions { margin-left: auto; display: flex; flex-wrap: wrap; gap: 8px; }
    button { border: 0; border-radius: 8px; padding: 8px 12px; background: #3159d1; color: #fff; font-weight: 600; cursor: pointer; }
    button.secondary { background: #64748b; }
    button.ghost { background: #e2e8f0; color: #0f172a; }
    button.danger { background: #b91c1c; }
    .stats { margin-top: 8px; font-size: .86rem; color: #334155; }
    .table-wrap { margin-top: 10px; overflow: auto; max-height: 65vh; border: 1px solid #e2e8f0; border-radius: 8px; }
    table { width: 100%; border-collapse: collapse; font-size: .86rem; }
    th, td { border-bottom: 1px solid #eef2f7; padding: 8px 9px; text-align: left; vertical-align: top; }
    th { background: #f8fafc; position: sticky; top: 0; z-index: 2; }
    tr.done td { background: #f8fafc; color: #64748b; }
    tr.done td.task-text { text-decoration: line-through; }
    .chip { display: inline-block; background: #e2e8f0; color: #0f172a; border-radius: 999px; padding: 2px 8px; font-size: .72rem; white-space: nowrap; }
    .links a { margin-right: 8px; white-space: nowrap; }
    .small { font-size: .78rem; color: #64748b; }
    a { color: #1d4ed8; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .custom-row { display:flex; flex-wrap:wrap; gap:8px; align-items:end; }
    .custom-row > div { min-width: 160px; }
    .checkbox-cell { width: 44px; }
    .footer { margin-top: 14px; font-size: .78rem; color: #64748b; text-align:center; }
    @media (max-width: 760px) {
      .filters .actions { margin-left: 0; width: 100%; }
      .filters .actions button { flex: 1; }
      .header h1 { font-size: 1.2rem; }
    }
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1 id="title">✅ SAT TODO-lista</h1>
    <p class="sub" id="subtitle">Arbetslista för fältarbete och datakvalitet, filtrerbar per ö och objekttyp.</p>
    <div class="meta">
      <span id="generatedLabel">Genererad</span>: <strong id="generatedAt"></strong> &nbsp;|&nbsp;
      <a id="navDashboard" href="sat_poi_dashboard.html">🧭 Dashboard</a> &nbsp;|&nbsp;
      <a id="navTodoMap" href="sat_todo_map.html">🗺️ TODO-karta</a> &nbsp;|&nbsp;
      <a id="navQuality" href="sat_poi_quality_history.html">📈 Datakvalitet</a> &nbsp;|&nbsp;
      <a id="navAbout" href="sat_about.html">ℹ️ Om verktygen</a> &nbsp;|&nbsp;
      <a href="whats_new.html">What's new</a>
      <button class="lang-btn" id="langBtn" type="button">English</button>
    </div>
  </div>

  <div class="panel">
    <div class="filters">
      <div>
        <label id="sectionFilterLabel" for="sectionFilter">Ö / section</label>
        <select id="sectionFilter"></select>
      </div>
      <div>
        <label id="categoryFilterLabel" for="categoryFilter">Objekttyp</label>
        <select id="categoryFilter"></select>
      </div>
      <div>
        <label id="organisationFilterLabel" for="organisationFilter">Organisation</label>
        <select id="organisationFilter"></select>
      </div>
      <div>
        <label id="typeFilterLabel" for="typeFilter">Uppgiftstyp</label>
        <select id="typeFilter"></select>
      </div>
      <div>
        <label id="showModeLabel" for="showMode">Visa</label>
        <select id="showMode">
          <option value="open" id="showModeOpen">Ej klara</option>
          <option value="all" id="showModeAll">Alla</option>
          <option value="done" id="showModeDone">Klara</option>
        </select>
      </div>
      <div class="actions">
        <button id="exportJsonBtn" type="button">Export JSON</button>
        <button id="exportCsvBtn" type="button">Export CSV</button>
        <button id="copyMdBtn" type="button" class="secondary">Kopiera Markdown</button>
        <button id="clearDoneBtn" type="button" class="ghost">Rensa klara</button>
      </div>
    </div>
    <div class="stats" id="stats"></div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="checkbox-cell">✓</th>
            <th id="thSection">Ö</th>
            <th id="thType">Typ</th>
            <th id="thPoi">POI</th>
            <th id="thOrganisation">Organisation</th>
            <th id="thCategory">Kategori</th>
            <th id="thTask">Uppgift</th>
            <th id="thLinks">Länkar</th>
          </tr>
        </thead>
        <tbody id="taskBody"></tbody>
      </table>
    </div>
  </div>

  <div class="panel">
    <h3 id="customTitle" style="margin-top:0">Lägg till egen uppgift</h3>
    <div class="custom-row">
      <div>
        <label id="customSectionLabel" for="customSection">Ö / section</label>
        <select id="customSection"></select>
      </div>
      <div>
        <label id="customTypeLabel" for="customType">Typ</label>
        <select id="customType"></select>
      </div>
      <div style="flex:1;min-width:240px">
        <label id="customTextLabel" for="customText">Uppgift</label>
        <input id="customText" type="text" placeholder="t.ex. ring färjan om tidtabell">
      </div>
      <div style="flex:1;min-width:200px">
        <label id="customPoiLabel" for="customPoi">POI (valfritt)</label>
        <input id="customPoi" type="text" placeholder="Namn eller SAT-ID">
      </div>
      <div>
        <button id="addCustomBtn" type="button">Lägg till</button>
      </div>
    </div>
    <p class="small" id="customHint">Egna uppgifter sparas lokalt i webbläsaren (localStorage).</p>
  </div>

  <div class="footer">
    <a href="https://github.com/salgo60/sat-sync" target="_blank">salgo60/sat-sync</a>
  </div>
</div>

<script>
(function () {
  const BASE_TASKS = __TASKS_JSON__;
  const SECTIONS = __SECTIONS_JSON__;
  const CATEGORIES = __CATEGORIES_JSON__;
  const OPERATORS = __OPERATORS_JSON__;
  const GENERATED_AT = __GENERATED_AT_JSON__;
  const CHECKED_KEY = 'satTodoListCheckedV1';
  const CUSTOM_KEY = 'satTodoListCustomV1';
  const TYPE_ORDER = ['photo', 'opening_hours', 'osm_notes', 'wheelchair', 'custom'];
  const TYPE_LABELS = {
    sv: {
      photo: 'Ta bilder',
      opening_hours: 'Öppettider',
      osm_notes: 'OSM Notes',
      wheelchair: 'Wheelchair-tag',
      custom: 'Egen'
    },
    en: {
      photo: 'Take photos',
      opening_hours: 'Opening hours',
      osm_notes: 'OSM Notes',
      wheelchair: 'Wheelchair tag',
      custom: 'Custom'
    }
  };
  const I18N = {
    sv: {
      title: '✅ SAT TODO-lista',
      subtitle: 'Arbetslista för fältarbete och datakvalitet, filtrerbar per ö och objekttyp.',
      generatedLabel: 'Genererad',
      navQuality: '📈 Datakvalitet',
      navAbout: 'ℹ️ Om verktygen',
      langBtn: 'English',
      sectionFilterLabel: 'Ö / section',
      categoryFilterLabel: 'Objekttyp',
      typeFilterLabel: 'Uppgiftstyp',
      showModeLabel: 'Visa',
      showModeOpen: 'Ej klara',
      showModeAll: 'Alla',
      showModeDone: 'Klara',
      thSection: 'Ö',
      thType: 'Typ',
      thPoi: 'POI',
      thOrganisation: 'Organisation',
      thCategory: 'Kategori',
      thTask: 'Uppgift',
      thLinks: 'Länkar',
      organisationFilterLabel: 'Organisation',
      allOrganisations: 'Alla organisationer',
      customTitle: 'Lägg till egen uppgift',
      customSectionLabel: 'Ö / section',
      customTypeLabel: 'Typ',
      customTextLabel: 'Uppgift',
      customPoiLabel: 'POI (valfritt)',
      customHint: 'Egna uppgifter sparas lokalt i webbläsaren (localStorage).',
      allSections: 'Alla öar',
      allCategories: 'Alla kategorier',
      allTypes: 'Alla typer',
      stats: 'Visar {{visible}} av {{total}} uppgifter',
      empty: 'Inga uppgifter matchar valt filter.',
      islandLevel: 'Ö-nivå',
      satMap: 'SAT',
      osm: 'OSM',
      id: 'iD',
      notes: 'Notes',
      exportJsonBtn: 'Export JSON',
      exportCsvBtn: 'Export CSV',
      copyMdBtn: 'Kopiera Markdown',
      clearDoneBtn: 'Rensa klara',
      addCustomBtn: 'Lägg till',
      copiedMarkdown: 'Markdown-checklista kopierad.',
      copiedFallback: 'Kunde inte kopiera automatiskt. Kopiera manuellt:',
      missingCustomText: 'Skriv en uppgiftstext först.',
      defaultOsmNotesTask: 'Gå igenom öppna OSM Notes på ön',
      noPoi: '—'
    },
    en: {
      title: '✅ SAT TODO list',
      subtitle: 'Task list for field work and data quality, filterable by island and object type.',
      generatedLabel: 'Generated',
      navQuality: '📈 Data quality',
      navAbout: 'ℹ️ About',
      langBtn: 'Svenska',
      sectionFilterLabel: 'Island / section',
      categoryFilterLabel: 'Object type',
      typeFilterLabel: 'Task type',
      showModeLabel: 'Show',
      showModeOpen: 'Open',
      showModeAll: 'All',
      showModeDone: 'Done',
      thSection: 'Island',
      thType: 'Type',
      thPoi: 'POI',
      thOrganisation: 'Organisation',
      thCategory: 'Category',
      thTask: 'Task',
      thLinks: 'Links',
      organisationFilterLabel: 'Organisation',
      allOrganisations: 'All organisations',
      customTitle: 'Add custom task',
      customSectionLabel: 'Island / section',
      customTypeLabel: 'Type',
      customTextLabel: 'Task',
      customPoiLabel: 'POI (optional)',
      customHint: 'Custom tasks are saved locally in your browser (localStorage).',
      allSections: 'All islands',
      allCategories: 'All categories',
      allTypes: 'All types',
      stats: 'Showing {{visible}} of {{total}} tasks',
      empty: 'No tasks match current filters.',
      islandLevel: 'Island level',
      satMap: 'SAT',
      osm: 'OSM',
      id: 'iD',
      notes: 'Notes',
      exportJsonBtn: 'Export JSON',
      exportCsvBtn: 'Export CSV',
      copyMdBtn: 'Copy Markdown',
      clearDoneBtn: 'Clear done',
      addCustomBtn: 'Add',
      copiedMarkdown: 'Markdown checklist copied.',
      copiedFallback: 'Could not auto-copy. Copy manually:',
      missingCustomText: 'Enter a task first.',
      defaultOsmNotesTask: 'Review open OSM Notes on island',
      noPoi: '—'
    }
  };

  let lang = 'sv';
  const params = new URLSearchParams(window.location.search);
  if (params.get('lang') === 'en') lang = 'en';

  const sectionFilter = document.getElementById('sectionFilter');
  const categoryFilter = document.getElementById('categoryFilter');
  const operatorFilter = document.getElementById('operatorFilter');
  const typeFilter = document.getElementById('typeFilter');
  const showMode = document.getElementById('showMode');
  const taskBody = document.getElementById('taskBody');
  const stats = document.getElementById('stats');
  const generatedAt = document.getElementById('generatedAt');
  const langBtn = document.getElementById('langBtn');

  const customSection = document.getElementById('customSection');
  const customType = document.getElementById('customType');
  const customText = document.getElementById('customText');
  const customPoi = document.getElementById('customPoi');
  const addCustomBtn = document.getElementById('addCustomBtn');

  const exportJsonBtn = document.getElementById('exportJsonBtn');
  const exportCsvBtn = document.getElementById('exportCsvBtn');
  const copyMdBtn = document.getElementById('copyMdBtn');
  const clearDoneBtn = document.getElementById('clearDoneBtn');
  const sectionNotesLinkBySection = new Map(
    BASE_TASKS
      .filter((task) => task.type === 'osm_notes' && task.section && task.links && task.links.notes)
      .map((task) => [task.section, task.links.notes])
  );

  let checked = loadJson(CHECKED_KEY, {});
  let customTasks = loadJson(CUSTOM_KEY, []);

  function loadJson(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch (_e) {
      return fallback;
    }
  }

  function saveJson(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function t(key, vars) {
    const dict = I18N[lang] || I18N.en;
    const base = dict[key] || I18N.en[key] || key;
    if (!vars) return base;
    return base.replace(/\\{\\{(\\w+)\\}\\}/g, (_m, v) => String(vars[v] ?? ''));
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, (ch) => {
      if (ch === '&') return '&amp;';
      if (ch === '<') return '&lt;';
      if (ch === '>') return '&gt;';
      if (ch === '"') return '&quot;';
      return '&#039;';
    });
  }

  function taskTypeLabel(type) {
    return (TYPE_LABELS[lang] && TYPE_LABELS[lang][type]) || TYPE_LABELS.en[type] || type;
  }

  function localizedTaskText(task) {
    if (lang === 'en' && task.taskTextEn) return task.taskTextEn;
    if (task.taskTextSv) return task.taskTextSv;
    return task.taskTextEn || '';
  }

  function getAllTasks() {
    return BASE_TASKS.concat(customTasks);
  }

  function applyLangToUi() {
    const ids = [
      'title','subtitle','generatedLabel','navQuality','navAbout','sectionFilterLabel',
      'categoryFilterLabel','operatorFilterLabel','typeFilterLabel','showModeLabel','showModeOpen','showModeAll',
      'showModeDone','thSection','thType','thPoi','thOperator','thCategory','thTask','thLinks',
      'customTitle','customSectionLabel','customTypeLabel','customTextLabel','customPoiLabel',
      'customHint','exportJsonBtn','exportCsvBtn','copyMdBtn','clearDoneBtn','addCustomBtn'
    ];
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = t(id);
    });
    langBtn.textContent = t('langBtn');
    document.documentElement.lang = lang;
    document.title = t('title');
    generatedAt.textContent = GENERATED_AT;
    const about = document.getElementById('navAbout');
    const quality = document.getElementById('navQuality');
    if (about) about.setAttribute('href', `sat_about.html${lang === 'en' ? '?lang=en' : ''}`);
    if (quality) quality.setAttribute('href', `sat_poi_quality_history.html${lang === 'en' ? '?lang=en' : ''}`);
    const dashboard = document.getElementById('navDashboard');
    const todoMap = document.getElementById('navTodoMap');
    if (dashboard) dashboard.setAttribute('href', `sat_poi_dashboard.html${lang === 'en' ? '?lang=en' : ''}`);
    if (todoMap) todoMap.setAttribute('href', `sat_todo_map.html${lang === 'en' ? '?lang=en' : ''}`);
  }

  function fillSelectOptions() {
    sectionFilter.innerHTML = `<option value="all">${escapeHtml(t('allSections'))}</option>` +
      SECTIONS.map((s) => `<option value="${escapeHtml(s.value)}">${escapeHtml(s.label)}</option>`).join('');
    customSection.innerHTML = SECTIONS.map((s) => `<option value="${escapeHtml(s.value)}">${escapeHtml(s.label)}</option>`).join('');

    categoryFilter.innerHTML = `<option value="all">${escapeHtml(t('allCategories'))}</option>` +
      CATEGORIES.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');

    operatorFilter.innerHTML = `<option value="all">${escapeHtml(t('allOperators'))}</option>` +
      OPERATORS.map((op) => `<option value="${escapeHtml(op)}">${escapeHtml(op)}</option>`).join('');

    const typeOptions = TYPE_ORDER.map((type) => `<option value="${type}">${escapeHtml(taskTypeLabel(type))}</option>`).join('');
    typeFilter.innerHTML = `<option value="all">${escapeHtml(t('allTypes'))}</option>${typeOptions}`;
    customType.innerHTML = typeOptions;
  }

  function currentFilters() {
    return {
      section: sectionFilter.value || 'all',
      category: categoryFilter.value || 'all',
      operator: operatorFilter.value || 'all',
      type: typeFilter.value || 'all',
      mode: showMode.value || 'open'
    };
  }

  function filteredTasks() {
    const filters = currentFilters();
    return getAllTasks().filter((task) => {
      if (filters.section !== 'all' && task.section !== filters.section) return false;
      if (filters.category !== 'all' && task.category !== filters.category) return false;
      if (filters.operator !== 'all' && task.operator !== filters.operator) return false;
      if (filters.type !== 'all' && task.type !== filters.type) return false;
      const isDone = !!checked[task.id];
      if (filters.mode === 'open' && isDone) return false;
      if (filters.mode === 'done' && !isDone) return false;
      return true;
    });
  }

  function renderTable() {
    const rows = filteredTasks();
    if (!rows.length) {
      taskBody.innerHTML = `<tr><td colspan="8" class="small">${escapeHtml(t('empty'))}</td></tr>`;
      stats.textContent = t('stats', { visible: 0, total: getAllTasks().length });
      return;
    }
    taskBody.innerHTML = rows.map((task) => {
      const isDone = !!checked[task.id];
      const links = [];
      if (task.links && task.links.sat) links.push(`<a href="${escapeHtml(task.links.sat)}" target="_blank">${escapeHtml(t('satMap'))}</a>`);
      if (task.links && task.links.osm) links.push(`<a href="${escapeHtml(task.links.osm)}" target="_blank">${escapeHtml(t('osm'))}</a>`);
      if (task.links && task.links.id) links.push(`<a href="${escapeHtml(task.links.id)}" target="_blank">${escapeHtml(t('id'))}</a>`);
      if (task.links && task.links.notes) links.push(`<a href="${escapeHtml(task.links.notes)}" target="_blank">${escapeHtml(t('notes'))}</a>`);
      const poiText = task.poiId
        ? `<code>${escapeHtml(task.poiId)}</code><br><span class="small">${escapeHtml(task.poiName || '')}</span>`
        : `<span class="small">${escapeHtml(t('islandLevel'))}</span>`;
      const operatorCell = task.operatorWikidata 
        ? `<a href="https://www.wikidata.org/wiki/${task.operatorWikidata}" target="_blank" title="${escapeHtml(task.operator)}">${escapeHtml(task.operator)}</a>`
        : (task.operator && task.operator !== '(unknown)' ? escapeHtml(task.operator) : '<span class="small" style="color:#ccc;">—</span>');
      return `
        <tr class="${isDone ? 'done' : ''}">
          <td class="checkbox-cell"><input type="checkbox" data-task-id="${escapeHtml(task.id)}" ${isDone ? 'checked' : ''}></td>
          <td>${escapeHtml(task.sectionLabel || task.section)}</td>
          <td><span class="chip">${escapeHtml(taskTypeLabel(task.type))}</span></td>
          <td>${poiText}</td>
          <td>${operatorCell}</td>
          <td>${task.category === 'island' ? escapeHtml(t('islandLevel')) : escapeHtml(task.category || t('noPoi'))}</td>
          <td class="task-text">${escapeHtml(localizedTaskText(task))}</td>
          <td class="links">${links.join(' ') || '<span class="small">—</span>'}</td>
        </tr>`;
    }).join('');
    stats.textContent = t('stats', { visible: rows.length, total: getAllTasks().length });
    taskBody.querySelectorAll('input[type="checkbox"][data-task-id]').forEach((el) => {
      el.addEventListener('change', () => {
        const id = el.getAttribute('data-task-id');
        checked[id] = el.checked;
        saveJson(CHECKED_KEY, checked);
        renderTable();
      });
    });
  }

  function downloadText(content, filename, mimeType) {
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function exportJson() {
    const rows = filteredTasks().map((task) => ({ ...task, done: !!checked[task.id], taskText: localizedTaskText(task) }));
    downloadText(JSON.stringify(rows, null, 2), 'sat-todo-list.json', 'application/json;charset=utf-8');
  }

  function toCsvCell(value) {
    const text = String(value ?? '');
    if (text.includes(',') || text.includes('"') || text.includes('\\n')) {
      return '"' + text.replace(/"/g, '""') + '"';
    }
    return text;
  }

  function exportCsv() {
    const rows = filteredTasks();
    const header = ['done','section','type','category','poi_id','poi_name','task','sat_url','osm_url','id_url','notes_url'];
    const lines = [header.join(',')];
    rows.forEach((task) => {
      lines.push([
        checked[task.id] ? '1' : '0',
        task.sectionLabel || task.section,
        taskTypeLabel(task.type),
        task.category,
        task.poiId || '',
        task.poiName || '',
        localizedTaskText(task),
        task.links?.sat || '',
        task.links?.osm || '',
        task.links?.id || '',
        task.links?.notes || ''
      ].map(toCsvCell).join(','));
    });
    downloadText(lines.join('\\n'), 'sat-todo-list.csv', 'text/csv;charset=utf-8');
  }

  async function copyMarkdown() {
    const lines = filteredTasks().map((task) => {
      const marker = checked[task.id] ? 'x' : ' ';
      const poi = task.poiId ? `${task.poiId} ${task.poiName || ''}`.trim() : t('islandLevel');
      const notes = task.links?.notes ? ` (${task.links.notes})` : '';
      return `- [${marker}] ${localizedTaskText(task)} — ${task.sectionLabel || task.section} — ${poi}${notes}`;
    });
    const text = lines.join('\\n');
    try {
      await navigator.clipboard.writeText(text);
      alert(t('copiedMarkdown'));
    } catch (_e) {
      window.prompt(t('copiedFallback'), text);
    }
  }

  function addCustomTask() {
    const selectedType = customType.value || 'custom';
    const text = (customText.value || '').trim();
    const resolvedText = text || (selectedType === 'osm_notes' ? t('defaultOsmNotesTask') : '');
    if (!resolvedText) {
      alert(t('missingCustomText'));
      return;
    }
    const section = customSection.value || 'unknown';
    const sectionItem = SECTIONS.find((s) => s.value === section);
    const notesLink = selectedType === 'osm_notes' ? (sectionNotesLinkBySection.get(section) || '') : '';
    const categoryValue = selectedType === 'osm_notes' ? 'island' : 'custom';
    const task = {
      id: `custom:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`,
      type: selectedType,
      section,
      sectionLabel: sectionItem ? sectionItem.label : section,
      category: categoryValue,
      poiId: '',
      poiName: (customPoi.value || '').trim(),
      taskTextSv: resolvedText,
      taskTextEn: resolvedText,
      links: { sat: '', osm: '', id: '', notes: notesLink }
    };
    customTasks.push(task);
    saveJson(CUSTOM_KEY, customTasks);
    customText.value = '';
    customPoi.value = '';
    renderTable();
  }

  function clearDone() {
    Object.keys(checked).forEach((id) => {
      if (checked[id]) delete checked[id];
    });
    saveJson(CHECKED_KEY, checked);
    renderTable();
  }

  function syncUrlState() {
    const url = new URL(window.location.href);
    const f = currentFilters();
    if (f.section === 'all') url.searchParams.delete('section'); else url.searchParams.set('section', f.section);
    if (f.category === 'all') url.searchParams.delete('category'); else url.searchParams.set('category', f.category);
    if (f.operator === 'all') url.searchParams.delete('operator'); else url.searchParams.set('operator', f.operator);
    if (f.type === 'all') url.searchParams.delete('type'); else url.searchParams.set('type', f.type);
    if (f.mode === 'open') url.searchParams.delete('mode'); else url.searchParams.set('mode', f.mode);
    if (lang === 'en') url.searchParams.set('lang', 'en'); else url.searchParams.delete('lang');
    history.replaceState({}, '', url.toString());
  }

  function readUrlState() {
    const p = new URLSearchParams(window.location.search);
    const sec = p.get('section');
    const cat = p.get('category');
    const op = p.get('operator');
    const type = p.get('type');
    const mode = p.get('mode');
    if (sec) sectionFilter.value = sec;
    if (cat) categoryFilter.value = cat;
    if (op) operatorFilter.value = op;
    if (type) typeFilter.value = type;
    if (mode && ['open','all','done'].includes(mode)) showMode.value = mode;
  }

  function rerender() {
    syncUrlState();
    renderTable();
  }

  fillSelectOptions();
  readUrlState();
  applyLangToUi();
  renderTable();

  [sectionFilter, categoryFilter, operatorFilter, typeFilter, showMode].forEach((el) => el.addEventListener('change', rerender));
  addCustomBtn.addEventListener('click', addCustomTask);
  exportJsonBtn.addEventListener('click', exportJson);
  exportCsvBtn.addEventListener('click', exportCsv);
  copyMdBtn.addEventListener('click', copyMarkdown);
  clearDoneBtn.addEventListener('click', clearDone);

  langBtn.addEventListener('click', () => {
    lang = lang === 'sv' ? 'en' : 'sv';
    fillSelectOptions();
    readUrlState();
    applyLangToUi();
    renderTable();
    syncUrlState();
  });
})();
</script>
</body>
</html>
"""

    return (
        template.replace("__TASKS_JSON__", tasks_json)
        .replace("__SECTIONS_JSON__", sections_json)
        .replace("__CATEGORIES_JSON__", categories_json)
        .replace("__OPERATORS_JSON__", operators_json)
        .replace("__GENERATED_AT_JSON__", generated_at_json)
    )


def main():
    html = build_page()
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ {OUTPUT} sparad")


if __name__ == "__main__":
    main()
