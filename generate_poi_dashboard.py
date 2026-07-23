#!/usr/bin/env python3
"""
Dashboard för alla SAT-objekt i pois.geojson.

Visar koppling mellan:
- POI (sat:poi:...)
- Etapp/ö (section)
- Objektkategori (category)
- Wikidata-etapper (SPARQL)
"""

import json
import re
import unicodedata
import urllib.request
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urlencode


POIS_URL = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
TRAIL_URL = "https://map.stockholmarchipelagotrail.com/data/trail.jsonld"
SECTIONS_INDEX_URL = "https://map.stockholmarchipelagotrail.com/data/sections-index.json"


def category_group(category: str) -> str:
    """Mappa detaljkategori till bred grupp för visualisering."""
    c = (category or "unknown").lower()
    mapping = {
        "toilet": "Facilities",
        "water": "Facilities",
        "shower": "Facilities",
        "firepit": "Facilities",
        "beach": "Facilities",
        "harbour": "Facilities",
        "sauna": "Facilities",
        "shelter": "Facilities",
        "lodging": "Accommodation",
        "food": "Food",
        "shop": "Shop",
        "rental": "Rental",
        "attraction": "Attraction",
        "viewpoint": "Attraction",
        "lighthouse": "Attraction",
        "rowboat": "Rental",
    }
    return mapping.get(c, "Other")


def normalize_slug(value: str) -> str:
    """Normalisera text till enkel slug för matchning, t.ex. 'Nåttarö' -> 'nattaro'."""
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"^sat\s+", "", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def parse_point_wkt(point_wkt: str) -> tuple[Optional[float], Optional[float]]:
    """Point(lon lat) -> (lat, lon)."""
    m = re.match(r"Point\(([-0-9.]+)\s+([-0-9.]+)\)", point_wkt or "")
    if not m:
        return None, None
    lon = float(m.group(1))
    lat = float(m.group(2))
    return lat, lon


def pick_text(value) -> Optional[str]:
    """Hämta text/url från lokaliserade fält (dict) eller rå sträng."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("sv", "en", "mul", "url", "value"):
            v = value.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in value.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def to_thumbnail_url(image_url: Optional[str]) -> Optional[str]:
    """Normalisera bild-url till thumbnail-liknande storlek för popup."""
    if not image_url:
        return None
    url = image_url.strip()
    if "commons.wikimedia.org/wiki/Special:FilePath/" in url:
        if "?width=" in url:
            url = re.sub(r"([?&]width=)\d+", r"\g<1>360", url)
        else:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}width=360"
    return url


def p18_to_thumbnail_url(p18_value: Optional[str]) -> Optional[str]:
    """Konvertera Wikidata P18 (filnamn/url) till Wikimedia thumbnail-url."""
    if not p18_value:
        return None
    value = p18_value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return to_thumbnail_url(value)
    # P18 är vanligtvis filnamn, t.ex. "Example.jpg"
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(value)}?width=360"


@dataclass
class Stage:
    q_id: str
    label: str
    coord_wkt: str
    lat: Optional[float]
    lon: Optional[float]
    slug: str
    image: Optional[str] = None


class POIDashboardGenerator:
    def __init__(self, email: str = "salgo60@msn.com"):
        self.email = email
        self.headers = {
            "User-Agent": f"SAT-Sync/1.0 (+https://stockholmarchipelagotrail.com; {email})",
            "Accept": "application/json",
        }

    def _get_json(self, url: str) -> dict:
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))

    def fetch_pois(self) -> list[dict]:
        print("📥 Hämtar pois.geojson...")
        data = self._get_json(POIS_URL)
        features = data.get("features", [])
        pois = []
        for feat in features:
            props = feat.get("properties", {})
            geom = feat.get("geometry", {}) or {}
            coords = geom.get("coordinates") or []
            lat = None
            lon = None
            if geom.get("type") == "Point" and isinstance(coords, list) and len(coords) >= 2:
                lon = coords[0]
                lat = coords[1]
            pois.append(
                {
                    "id": props.get("id"),
                    "name": props.get("name"),
                    "section": props.get("section"),
                    "category": props.get("category"),
                    "updated_at": props.get("updatedAt"),
                    "first_seen": props.get("firstSeen"),
                    "same_as": props.get("sameAs") or [],
                    "wikidata": props.get("wikidata"),
                    "image": to_thumbnail_url(pick_text(props.get("image"))),
                    "lat": lat,
                    "lon": lon,
                }
            )
        print(f"  ✅ {len(pois)} POI-objekt")
        return pois

    def fetch_stages(self) -> list[Stage]:
        print("📥 Hämtar etapper/öar från Wikidata (SPARQL)...")
        query = """
SELECT ?item ?itemLabel ?coord ?image {
 ?item wdt:P361 wd:Q131318799 ;
       wdt:P31 wd:Q2143825 ;
       wdt:P625 ?coord .
 OPTIONAL { ?item wdt:P18 ?image . }
 SERVICE wikibase:label {
  bd:serviceParam wikibase:language "sv,en" .
 }
}
ORDER BY DESC(geof:latitude(?coord))
"""
        url = f"{WIKIDATA_SPARQL}?{urlencode({'query': query, 'format': 'json'})}"
        data = self._get_json(url)
        stages: list[Stage] = []
        for b in data.get("results", {}).get("bindings", []):
            q_id = b["item"]["value"].split("/")[-1]
            label = b.get("itemLabel", {}).get("value", q_id)
            coord_wkt = b.get("coord", {}).get("value", "")
            lat, lon = parse_point_wkt(coord_wkt)
            p18_value = b.get("image", {}).get("value")
            stages.append(
                Stage(
                    q_id=q_id,
                    label=label,
                    coord_wkt=coord_wkt,
                    lat=lat,
                    lon=lon,
                    slug=normalize_slug(label),
                    image=p18_to_thumbnail_url(p18_value),
                )
            )
        print(f"  ✅ {len(stages)} etapper/öar")
        return stages

    def fetch_trail_geojson(self) -> dict:
        print("📥 Hämtar leden (trail.jsonld)...")
        data = self._get_json(TRAIL_URL)
        geometry = data.get("geometry") or {}
        if geometry.get("type") not in ("LineString", "MultiLineString"):
            raise ValueError("Okänt geometry-format i trail.jsonld")
        feature = {
            "type": "Feature",
            "properties": {
                "name": data.get("name") or "Stockholm Archipelago Trail",
            },
            "geometry": geometry,
        }
        print("  ✅ Ledgeometri hämtad")
        return {"type": "FeatureCollection", "features": [feature]}

    def fetch_sections_index(self, stages: list[Stage]) -> list[dict]:
        print("📥 Hämtar section-index...")
        data = self._get_json(SECTIONS_INDEX_URL)
        sections = []
        stage_by_slug = {s.slug: s for s in stages}
        if not isinstance(data, list):
            return sections
        for item in data:
            center = item.get("center") or []
            lon = center[0] if isinstance(center, list) and len(center) >= 2 else None
            lat = center[1] if isinstance(center, list) and len(center) >= 2 else None
            sec_slug = item.get("slug")
            stage = stage_by_slug.get(normalize_slug(sec_slug or ""))
            sections.append(
                {
                    "sat_id": item.get("satId"),
                    "slug": sec_slug,
                    "title": item.get("title"),
                    "distance_km": item.get("distanceKm"),
                    "difficulty": item.get("difficulty"),
                    "order": item.get("orderInTrail"),
                    "lat": lat,
                    "lon": lon,
                    "wikidata_q": stage.q_id if stage else None,
                    "image": stage.image if stage else None,
                }
            )
        print(f"  ✅ {len(sections)} sektioner")
        return sections

    def match_stage_for_section(self, section: str, stage_by_slug: dict[str, Stage], stages: list[Stage]) -> Optional[Stage]:
        if not section:
            return None
        sec = normalize_slug(section)
        exact = stage_by_slug.get(sec)
        if exact:
            return exact
        # Fallback: sektionen finns i stage-slug (t.ex. specialfall)
        candidates = [s for s in stages if sec in s.slug]
        if not candidates:
            return None
        candidates.sort(key=lambda s: len(s.slug))
        return candidates[0]

    def same_as_links(self, same_as: list[str]) -> str:
        links = []
        for v in same_as:
            if v.startswith("osm:"):
                parts = v.split(":")
                if len(parts) == 3:
                    links.append(f'<a href="https://www.openstreetmap.org/{parts[1]}/{parts[2]}" target="_blank">{v}</a>')
                else:
                    links.append(v)
            elif v.startswith("wikidata:"):
                q_id = v.split("wikidata:")[1]
                links.append(f'<a href="https://www.wikidata.org/wiki/{q_id}" target="_blank">{v}</a>')
            else:
                links.append(v)
        return "<br>".join(links) if links else "—"

    def generate_html(self, pois: list[dict], stages: list[Stage], trail_geojson: dict, sections_index: list[dict]) -> str:
        stage_by_slug = {s.slug: s for s in stages}

        section_stats: dict[str, dict] = {}
        categories: set[str] = set()
        poi_flow_data = []
        poi_map_data = []

        for p in pois:
            sec = p.get("section") or "okänd"
            cat = p.get("category") or "okänd"
            group = category_group(cat)
            categories.add(cat)
            poi_flow_data.append({"section": sec, "category": cat, "group": group})
            poi_map_data.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "section": sec,
                    "category": cat,
                    "lat": p.get("lat"),
                    "lon": p.get("lon"),
                    "image": p.get("image"),
                }
            )
            if sec not in section_stats:
                section_stats[sec] = {"count": 0, "categories": {}, "with_wd": 0, "with_osm": 0}
            section_stats[sec]["count"] += 1
            section_stats[sec]["categories"][cat] = section_stats[sec]["categories"].get(cat, 0) + 1
            same_as = p.get("same_as") or []
            if any(x.startswith("wikidata:") for x in same_as):
                section_stats[sec]["with_wd"] += 1
            if any(x.startswith("osm:") for x in same_as):
                section_stats[sec]["with_osm"] += 1

        section_rows = []
        for sec, st in sorted(section_stats.items(), key=lambda x: x[0]):
            stage = self.match_stage_for_section(sec, stage_by_slug, stages)
            stage_link = "—"
            if stage:
                stage_link = f'<a href="https://www.wikidata.org/wiki/{stage.q_id}" target="_blank">{stage.label}</a>'
            top_cat = sorted(st["categories"].items(), key=lambda x: x[1], reverse=True)[:3]
            top_cat_text = ", ".join(f"{k}:{v}" for k, v in top_cat) if top_cat else "—"
            section_rows.append(
                f"""
        <tr data-section="{sec}">
          <td>{sec}</td>
          <td>{stage_link}</td>
          <td>{st["count"]}</td>
          <td>{st["with_wd"]}</td>
          <td>{st["with_osm"]}</td>
          <td>{top_cat_text}</td>
        </tr>
"""
            )

        poi_rows = []
        for p in pois:
            sec = p.get("section") or "okänd"
            cat = p.get("category") or "okänd"
            stage = self.match_stage_for_section(sec, stage_by_slug, stages)
            stage_cell = "—"
            if stage:
                stage_cell = f'<a href="https://www.wikidata.org/wiki/{stage.q_id}" target="_blank">{stage.label}</a>'
            sat_id = p.get("id") or "—"
            poi_rows.append(
                f"""
        <tr data-section="{sec}" data-category="{cat}">
          <td><a href="https://map.stockholmarchipelagotrail.com/?{sat_id}" target="_blank"><code>{sat_id}</code></a></td>
          <td>{p.get("name") or "—"}</td>
          <td>{sec}</td>
          <td>{cat}</td>
          <td>{stage_cell}</td>
          <td>{self.same_as_links(p.get("same_as") or [])}</td>
          <td>{p.get("first_seen") or "—"}</td>
          <td>{p.get("updated_at") or "—"}</td>
        </tr>
"""
            )

        sections = sorted(section_stats.keys())
        section_display: dict[str, str] = {}
        for sec in sections:
            stage = self.match_stage_for_section(sec, stage_by_slug, stages)
            if stage:
                section_display[sec] = stage.label
                continue
            sec_meta = next((x for x in sections_index if x.get("slug") == sec), None)
            if sec_meta and sec_meta.get("title"):
                section_display[sec] = f"SAT {sec_meta['title']}"
            else:
                section_display[sec] = sec

        # Sortera etapper Norr -> Söder enligt SPARQL-resultatet (stages är redan i den ordningen).
        stage_order: dict[str, int] = {}
        for idx, stage in enumerate(stages):
            stage_order[stage.slug] = idx

        ordered_sections = []
        for sec in sections:
            stage = self.match_stage_for_section(sec, stage_by_slug, stages)
            if stage:
                ordered_sections.append((0, stage_order.get(stage.slug, 9999), sec))
            else:
                # Fallback om section inte matchar Wikidata-etapp
                ordered_sections.append((1, 9999, sec))
        ordered_sections.sort(key=lambda x: (x[0], x[1], x[2]))

        section_options = "\n".join(
            f'<option value="{sec}">{section_display.get(sec, sec)}</option>'
            for _, _, sec in ordered_sections
        )
        category_options = "\n".join(f'<option value="{c}">{c}</option>' for c in sorted(categories))
        poi_flow_json = json.dumps(poi_flow_data, ensure_ascii=False)
        poi_map_json = json.dumps(poi_map_data, ensure_ascii=False)
        trail_geojson_json = json.dumps(trail_geojson, ensure_ascii=False)
        sections_index_json = json.dumps(sections_index, ensure_ascii=False)

        return f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAT POI Dashboard</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#f5f7fb; color:#222; }}
    .container {{ max-width: 1500px; margin: 0 auto; }}
    .header {{ background: linear-gradient(135deg,#2546a8,#1d2f6f); color:#fff; padding:24px; }}
    .header h1 {{ margin:0 0 8px; }}
    .header p {{ margin:0; opacity:.9; }}
    .stats {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(170px,1fr)); gap:12px; padding:16px 24px; background:#fff; border-bottom:1px solid #e2e8f0; }}
    .card {{ background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:14px; }}
    .card h3 {{ margin:0 0 6px; font-size:.8rem; text-transform: uppercase; color:#555; }}
    .card .num {{ font-size:1.8rem; font-weight:700; }}
    .filters {{ background:#fff; padding:14px 24px; border-bottom:1px solid #e2e8f0; display:flex; flex-wrap:wrap; gap:12px; align-items:flex-end; }}
    .filters label {{ display:block; font-size:.8rem; color:#555; margin-bottom:4px; font-weight:600; }}
    .filters select {{ min-width:180px; padding:8px; border:1px solid #cbd5e1; border-radius:6px; }}
    .filters .actions {{ display:flex; gap:8px; align-items:center; }}
    .filters button {{ padding:8px 12px; border:1px solid #1d4ed8; background:#1d4ed8; color:#fff; border-radius:6px; cursor:pointer; font-weight:600; }}
    .filters button:hover {{ background:#1e40af; }}
    .filters .count {{ margin-left:auto; font-size:.9rem; color:#555; }}
    .section {{ padding:20px 24px; }}
    h2 {{ margin:0 0 12px; }}
    .chart-wrap {{ background:#fff; border:1px solid #e2e8f0; border-radius:8px; padding:10px; }}
    #sankeyChart {{ width:100%; height:560px; }}
    .map-wrap {{ background:#fff; border:1px solid #e2e8f0; border-radius:8px; padding:10px; }}
    #poiMap {{ width:100%; height:520px; border-radius:6px; }}
    .popup-thumb {{ width:140px; max-height:90px; object-fit:cover; border-radius:4px; display:block; margin-top:6px; }}
    .table-wrap {{ overflow:auto; background:#fff; border:1px solid #e2e8f0; border-radius:8px; }}
    table {{ width:100%; border-collapse: collapse; font-size:.86rem; }}
    th, td {{ padding:9px 10px; border-bottom:1px solid #eef2f7; text-align:left; vertical-align:top; }}
    th {{ background:#f8fafc; position: sticky; top:0; z-index:1; }}
    tr:hover td {{ background:#f9fbff; }}
    code {{ background:#eef2f7; padding:2px 5px; border-radius:4px; }}
    a {{ color:#1d4ed8; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .footer {{ padding:20px 24px; font-size:.85rem; color:#666; text-align:center; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🧭 SAT POI Dashboard</h1>
      <p>Alla objekt i pois.geojson med koppling till etapp/ö (Wikidata), section och objekttyp</p>
    </div>

    <div class="stats">
      <div class="card"><h3>Totalt POI</h3><div class="num">{len(pois)}</div></div>
      <div class="card"><h3>Etapp/ö (sections)</h3><div class="num">{len(section_stats)}</div></div>
      <div class="card"><h3>Objekttyper</h3><div class="num">{len(categories)}</div></div>
      <div class="card"><h3>Wikidata-etapper</h3><div class="num">{len(stages)}</div></div>
    </div>

    <div class="filters">
      <div>
        <label for="sectionFilter">Filtrera etapp/ö</label>
        <select id="sectionFilter">
          <option value="all">Alla</option>
          {section_options}
        </select>
      </div>
      <div>
        <label for="categoryFilter">Filtrera objekttyp</label>
        <select id="categoryFilter">
          <option value="all">Alla</option>
          {category_options}
        </select>
      </div>
      <div class="actions">
        <button id="shareBtn" type="button">Dela</button>
        <button id="resetBtn" type="button">Återställ</button>
      </div>
      <div class="count" id="visibleCount"></div>
    </div>

    <div class="section">
      <h2>Karta (aktuell filtrering)</h2>
      <div class="map-wrap">
        <div id="poiMap"></div>
      </div>
    </div>

    <div class="section">
      <h2>Alla POI</h2>
      <div class="table-wrap">
        <table id="poiTable">
          <thead>
            <tr>
              <th>SAT ID</th>
              <th>Namn</th>
              <th>Section</th>
              <th>Kategori</th>
              <th>Etapp/ö</th>
              <th>sameAs</th>
              <th>Första sedd</th>
              <th>Uppdaterad</th>
            </tr>
          </thead>
          <tbody>
            {''.join(poi_rows)}
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h2>Flöde: kategori → grupp → etapp/ö</h2>
      <div class="chart-wrap">
        <div id="sankeyChart"></div>
      </div>
    </div>

    <div class="section">
      <h2>Etapp/ö-översikt</h2>
      <div class="table-wrap">
        <table id="sectionTable">
          <thead>
            <tr>
              <th>Section</th>
              <th>Wikidata etapp/ö</th>
              <th>POI</th>
              <th>Med Wikidata-länk</th>
              <th>Med OSM-länk</th>
              <th>Toppkategorier</th>
            </tr>
          </thead>
          <tbody>
            {''.join(section_rows)}
          </tbody>
        </table>
      </div>
    </div>

    <div class="footer">
      Källor: <a href="{POIS_URL}" target="_blank">pois.geojson</a> |
      <a href="{TRAIL_URL}" target="_blank">trail.jsonld</a> |
      <a href="{SECTIONS_INDEX_URL}" target="_blank">sections-index.json</a> |
      <a href="https://map.stockholmarchipelagotrail.com/data-sources" target="_blank">data-sources</a> |
      <a href="https://www.wikidata.org/wiki/Q131318799" target="_blank">Wikidata route</a>
    </div>
  </div>

  <script>
    (function() {{
      const sectionFilter = document.getElementById('sectionFilter');
      const categoryFilter = document.getElementById('categoryFilter');
      const shareBtn = document.getElementById('shareBtn');
      const resetBtn = document.getElementById('resetBtn');
      const poiRows = Array.from(document.querySelectorAll('#poiTable tbody tr'));
      const sectionRows = Array.from(document.querySelectorAll('#sectionTable tbody tr'));
      const visibleCount = document.getElementById('visibleCount');
      const poiFlow = {poi_flow_json};
      const poiMapData = {poi_map_json};
      const totalPoiCount = poiMapData.length;
      const trailGeoJson = {trail_geojson_json};
      const sectionsIndex = {sections_index_json};
      const map = L.map('poiMap').setView([59.2, 18.5], 8);
      const markerLayer = L.layerGroup().addTo(map);
      const sectionLayer = L.layerGroup().addTo(map);
      const trailLayer = L.geoJSON(trailGeoJson, {{
        style: {{
          color: '#ef4444',
          weight: 4,
          opacity: 0.75
        }}
      }}).addTo(map);

      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 18,
        attribution: '&copy; OpenStreetMap'
      }}).addTo(map);

      function escapeHtml(text) {{
        return String(text || '')
          .replaceAll('&', '&amp;')
          .replaceAll('<', '&lt;')
          .replaceAll('>', '&gt;')
          .replaceAll('\"', '&quot;')
          .replaceAll(\"'\", '&#039;');
      }}

      function canonicalBaseUrl() {{
        if (window.location.protocol === 'file:') {{
          return 'https://salgo60.github.io/sat-sync/sat_poi_dashboard.html';
        }}
        return `${{window.location.origin}}${{window.location.pathname}}`;
      }}

      function stateLabel(sec, cat) {{
        const secText = sec === 'all' ? 'Alla' : (sectionFilter.options[sectionFilter.selectedIndex]?.text || sec);
        const catText = cat === 'all' ? 'Alla' : cat;
        return `${{secText}} ${{catText}}`;
      }}

      function buildShareUrl(sec, cat) {{
        const params = new URLSearchParams();
        if (sec && sec !== 'all') params.set('s', sec);
        if (cat && cat !== 'all') params.set('c', cat);
        const qs = params.toString();
        return qs ? `${{canonicalBaseUrl()}}?${{qs}}` : canonicalBaseUrl();
      }}

      function saveStateInUrl(sec, cat) {{
        const url = buildShareUrl(sec, cat);
        window.history.replaceState({{}}, '', url);
      }}

      function restoreStateFromUrl() {{
        const params = new URLSearchParams(window.location.search);
        const sec = params.get('s') || params.get('section');
        const cat = params.get('c') || params.get('category');
        if (sec && Array.from(sectionFilter.options).some(o => o.value === sec)) {{
          sectionFilter.value = sec;
        }}
        if (cat && Array.from(categoryFilter.options).some(o => o.value === cat)) {{
          categoryFilter.value = cat;
        }}
      }}

      async function shareCurrentState() {{
        const sec = sectionFilter.value;
        const cat = categoryFilter.value;
        const url = buildShareUrl(sec, cat);
        const title = 'SAT POI Dashboard';
        const text = stateLabel(sec, cat);
        try {{
          if (navigator.share) {{
            await navigator.share({{ title, text, url }});
          }} else if (navigator.clipboard && navigator.clipboard.writeText) {{
            await navigator.clipboard.writeText(url);
            alert(`Delningslänk kopierad:\\n${{url}}`);
          }} else {{
            prompt('Kopiera länken:', url);
          }}
        }} catch (_err) {{
          // användaren avbröt delning eller api saknas
        }}
      }}

      function resetFilters() {{
        sectionFilter.value = 'all';
        categoryFilter.value = 'all';
        applyFilters();
      }}

      function renderMap(sec, cat) {{
        markerLayer.clearLayers();
        sectionLayer.clearLayers();
        const filtered = poiMapData.filter((r) =>
          (sec === 'all' || r.section === sec) &&
          (cat === 'all' || r.category === cat) &&
          typeof r.lat === 'number' &&
          typeof r.lon === 'number'
        );

        const bounds = [];
        filtered.forEach((r) => {{
          const marker = L.circleMarker([r.lat, r.lon], {{
            radius: 5,
            color: '#1d4ed8',
            fillColor: '#2563eb',
            fillOpacity: 0.8,
            weight: 1
          }});
          const satUrl = `https://map.stockholmarchipelagotrail.com/sv?id=${{encodeURIComponent(r.id)}}`;
          const imageHtml = r.image
            ? `<img class="popup-thumb" src="${{escapeHtml(r.image)}}" alt="thumbnail">`
            : '';
          marker.bindPopup(`
            <div style="min-width:180px">
              <strong>${{escapeHtml(r.name || r.id)}}</strong><br>
              <small>Section: ${{escapeHtml(r.section)}} | Kategori: ${{escapeHtml(r.category)}}</small><br>
              <a href="${{satUrl}}" target="_blank">Öppna i SAT-kartan</a>
              ${{imageHtml}}
            </div>
          `);
          marker.addTo(markerLayer);
          bounds.push([r.lat, r.lon]);
        }});

        sectionsIndex
          .filter((s) => sec === 'all' || s.slug === sec)
          .forEach((s) => {{
            if (typeof s.lat !== 'number' || typeof s.lon !== 'number') return;
            const label = s.title || s.slug || s.sat_id || 'Sektion';
            const satLink = s.sat_id
              ? `https://map.stockholmarchipelagotrail.com/sv?${{s.sat_id}}`
              : '#';
            const popup = `
              <div style="min-width:190px">
                <strong><a href="${{satLink}}" target="_blank">SAT ${{escapeHtml(label)}}</a></strong><br>
                <small><a href="${{satLink}}" target="_blank"><code>${{escapeHtml(s.sat_id || '')}}</code></a></small><br>
                <small>distanceKm: <strong>${{escapeHtml(String(s.distance_km ?? '—'))}}</strong></small><br>
                <small>difficulty: <strong>${{escapeHtml(String(s.difficulty ?? '—'))}}</strong></small>
                ${{s.image ? `<img class="popup-thumb" src="${{escapeHtml(s.image)}}" alt="section thumbnail">` : ''}}
              </div>
            `;
            const marker = L.circleMarker([s.lat, s.lon], {{
              radius: 7,
              color: '#ef4444',
              fillColor: '#f97316',
              fillOpacity: 0.95,
              weight: 1
            }});
            marker.bindPopup(popup);
            marker.addTo(sectionLayer);
            bounds.push([s.lat, s.lon]);
          }});

        if (bounds.length > 0) {{
          map.fitBounds(bounds, {{ padding: [20, 20], maxZoom: 13 }});
        }} else {{
          const trailBounds = trailLayer.getBounds();
          if (trailBounds.isValid()) {{
            map.fitBounds(trailBounds, {{ padding: [20, 20], maxZoom: 11 }});
          }}
        }}
      }}

      function renderSankey(sec, cat) {{
        if (typeof Plotly === 'undefined') return;
        const filtered = poiFlow.filter((r) =>
          (sec === 'all' || r.section === sec) &&
          (cat === 'all' || r.category === cat)
        );

        const labels = [];
        const labelIndex = new Map();
        function idx(label) {{
          if (!labelIndex.has(label)) {{
            labelIndex.set(label, labels.length);
            labels.push(label);
          }}
          return labelIndex.get(label);
        }}

        const linkMap = new Map();
        function addLink(a, b) {{
          const key = `${{a}}|||${{b}}`;
          linkMap.set(key, (linkMap.get(key) || 0) + 1);
        }}

        filtered.forEach((r) => {{
          addLink(r.category, r.group);
          addLink(r.group, `SAT ${{r.section}}`);
        }});

        const source = [];
        const target = [];
        const value = [];
        const linkColor = [];

        const groupColors = {{
          Facilities: "rgba(31, 119, 180, 0.65)",
          Food: "rgba(255, 127, 14, 0.65)",
          Accommodation: "rgba(148, 103, 189, 0.65)",
          Shop: "rgba(44, 160, 44, 0.65)",
          Rental: "rgba(214, 39, 40, 0.65)",
          Attraction: "rgba(23, 190, 207, 0.65)",
          Other: "rgba(127, 127, 127, 0.65)",
        }};

        for (const [k, v] of linkMap.entries()) {{
          const [a, b] = k.split("|||");
          source.push(idx(a));
          target.push(idx(b));
          value.push(v);
          const fromGroup = groupColors[a] ? a : (groupColors[b] ? b : "Other");
          linkColor.push(groupColors[fromGroup] || groupColors.Other);
        }}

        const nodeColor = labels.map((label) => {{
          if (groupColors[label]) return groupColors[label];
          if (label.startsWith("SAT ")) return "rgba(180, 180, 180, 0.9)";
          return "rgba(210, 210, 210, 0.9)";
        }});

        const data = [{{
          type: "sankey",
          arrangement: "snap",
          node: {{
            pad: 10,
            thickness: 20,
            line: {{ color: "rgba(70,70,70,.35)", width: 1 }},
            label: labels,
            color: nodeColor
          }},
          link: {{
            source,
            target,
            value,
            color: linkColor
          }}
        }}];

        const titlePart = sec === 'all' ? 'alla etapper' : `etapp: ${{sec}}`;
        const layout = {{
          title: `POI-flöde för ${{titlePart}}`,
          margin: {{ l: 20, r: 20, t: 40, b: 10 }},
          font: {{ size: 13 }}
        }};
        Plotly.react('sankeyChart', data, layout, {{displayModeBar: false, responsive: true}});
      }}

      function applyFilters() {{
        const sec = sectionFilter.value;
        const cat = categoryFilter.value;
        let visible = 0;

        poiRows.forEach((row) => {{
          const rowSec = row.dataset.section;
          const rowCat = row.dataset.category;
          const show = (sec === 'all' || rowSec === sec) && (cat === 'all' || rowCat === cat);
          row.style.display = show ? '' : 'none';
          if (show) visible += 1;
        }});

        sectionRows.forEach((row) => {{
          const rowSec = row.dataset.section;
          row.style.display = (sec === 'all' || rowSec === sec) ? '' : 'none';
        }});

        visibleCount.textContent = `Visar ${{visible}} av ${{totalPoiCount}} POI`;
        saveStateInUrl(sec, cat);
        renderMap(sec, cat);
        renderSankey(sec, cat);
      }}

      sectionFilter.addEventListener('change', applyFilters);
      categoryFilter.addEventListener('change', applyFilters);
      shareBtn.addEventListener('click', shareCurrentState);
      resetBtn.addEventListener('click', resetFilters);
      restoreStateFromUrl();
      applyFilters();
    }})();
  </script>
</body>
</html>
"""

    def run(self, output_file: str = "sat_poi_dashboard.html"):
        pois = self.fetch_pois()
        stages = self.fetch_stages()
        trail_geojson = self.fetch_trail_geojson()
        sections_index = self.fetch_sections_index(stages)
        html = self.generate_html(pois, stages, trail_geojson, sections_index)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ Dashboard sparad: {output_file}")


def main():
    generator = POIDashboardGenerator(email="salgo60@msn.com")
    generator.run()


if __name__ == "__main__":
    main()
