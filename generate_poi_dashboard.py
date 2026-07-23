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
from datetime import datetime
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
                    "name_localized": props.get("nameLocalized") or {},
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
        generated_at = datetime.now().strftime("%Y%m%d %H:%M")

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
                    "name_localized": p.get("name_localized") or {},
                    "section": sec,
                    "category": cat,
                    "same_as": p.get("same_as") or [],
                    "first_seen": p.get("first_seen"),
                    "updated_at": p.get("updated_at"),
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
        <tr data-section="{sec}" data-category="{cat}" data-poi-id="{sat_id}">
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
        category_options = "\n".join(f'<option value="{c}" data-category="{c}">{c}</option>' for c in sorted(categories))
        swedish_languages = [
            ("sv", "Swedish (Svenska)"),
            ("en", "English"),
            ("ar", "Arabic (العربية)"),
            ("fi", "Finnish (Suomi)"),
            ("so", "Somali (Soomaali)"),
            ("fa", "Persian (فارسی)"),
            ("ckb", "Kurdish (Sorani)"),
            ("ti", "Tigrinya (ትግርኛ)"),
            ("pl", "Polish (Polski)"),
            ("tr", "Turkish (Türkçe)"),
            ("es", "Spanish (Español)"),
        ]
        tourist_languages = [
            ("nb", "Norwegian (Bokmål)"),
            ("nn", "Norwegian (Nynorsk)"),
            ("da", "Danish (Dansk)"),
            ("fi", "Finnish (Suomi)"),
            ("de", "German (Deutsch)"),
            ("nl", "Dutch (Nederlands)"),
            ("en", "English"),
            ("fr", "French (Français)"),
            ("es", "Spanish (Español)"),
            ("it", "Italian (Italiano)"),
            ("zh", "Chinese (中文)"),
            ("ja", "Japanese (日本語)"),
            ("pl", "Polish (Polski)"),
            ("ru", "Russian (Русский)"),
        ]
        swedish_language_options = "\n".join(
            f'<option value="swedish:{code}"{" selected" if code == "sv" else ""}>{label}</option>'
            for code, label in swedish_languages
        )
        tourist_language_options = "\n".join(
            f'<option value="tourist:{code}">{label}</option>'
            for code, label in tourist_languages
        )
        language_options = (
            f'<optgroup label="Svenska språken">\n{swedish_language_options}\n</optgroup>\n'
            f'<optgroup label="Turistspråken">\n{tourist_language_options}\n</optgroup>'
        )
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
    #languageFilter {{ min-width:300px; }}
    .filters .hint {{ margin-top:4px; font-size:.75rem; color:#64748b; }}
    .filters .actions {{ display:flex; gap:8px; align-items:center; }}
    .filters button {{ padding:8px 12px; border:1px solid #1d4ed8; background:#1d4ed8; color:#fff; border-radius:6px; cursor:pointer; font-weight:600; }}
    .filters button:hover {{ background:#1e40af; }}
    .filters .toggle {{ display:flex; align-items:center; gap:6px; font-size:.9rem; color:#334155; }}
    .filters .toggle input {{ width:16px; height:16px; }}
    .filters .distance-controls {{ display:flex; gap:8px; align-items:center; }}
    .filters .distance-controls select {{ min-width:90px; }}
    .filters .distance-count {{ font-size:.85rem; color:#334155; background:#f8fafc; border:1px solid #cbd5e1; border-radius:9999px; padding:5px 10px; }}
    .filters .count {{ margin-left:auto; font-size:1rem; color:#0f172a; font-weight:700; background:#e0ecff; border:1px solid #93c5fd; padding:8px 12px; border-radius:8px; }}
    .section {{ padding:20px 24px; }}
    h2 {{ margin:0 0 12px; }}
    .chart-wrap {{ background:#fff; border:1px solid #e2e8f0; border-radius:8px; padding:10px; }}
    #sankeyChart {{ width:100%; height:560px; }}
    .map-wrap {{ background:#fff; border:1px solid #e2e8f0; border-radius:8px; padding:10px; }}
    #poiMap {{ width:100%; height:520px; border-radius:6px; }}
    .popup-thumb {{ width:140px; max-height:90px; object-fit:cover; border-radius:4px; display:block; margin-top:6px; }}
    .osm-tags {{ margin-top:6px; font-size:.82rem; }}
    .osm-tags-body {{ margin-top:6px; max-height:140px; overflow:auto; border:1px solid #e2e8f0; border-radius:6px; padding:6px; background:#f8fafc; }}
    .osm-tags-list {{ margin:0; padding-left:18px; }}
    .poi-icon {{
      width: 24px;
      height: 24px;
      border-radius: 9999px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px;
      line-height: 1;
      border: 1px solid rgba(15,23,42,.28);
      box-shadow: 0 1px 2px rgba(15,23,42,.25);
    }}
    .poi-icon-badge {{
      display:inline-flex;
      width: 18px;
      height: 18px;
      border-radius: 9999px;
      align-items:center;
      justify-content:center;
      font-size:11px;
      margin-right:4px;
      border:1px solid rgba(15,23,42,.2);
    }}
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
      <h1 id="headerTitle">🧭 SAT POI Dashboard</h1>
      <p id="headerSubtitle">Alla objekt i pois.geojson med koppling till etapp/ö (Wikidata), section och objekttyp</p>
    </div>

    <div class="stats">
      <div class="card"><h3 id="statTotalLabel">Totalt POI</h3><div class="num">{len(pois)}</div></div>
      <div class="card"><h3 id="statSectionsLabel">Etapp/ö (sections)</h3><div class="num">{len(section_stats)}</div></div>
      <div class="card"><h3 id="statCategoriesLabel">Objekttyper</h3><div class="num">{len(categories)}</div></div>
      <div class="card"><h3 id="statWikidataLabel">Wikidata-etapper</h3><div class="num">{len(stages)}</div></div>
    </div>

    <div class="filters">
      <div>
        <label id="languageFilterLabel" for="languageFilter">Språk</label>
        <select id="languageFilter">
          {language_options}
        </select>
        <div id="languageHint" class="hint">Svenska språken och turistspråken är separerade i listan.</div>
      </div>
      <div>
        <label id="sectionFilterLabel" for="sectionFilter">Filtrera etapp/ö</label>
        <select id="sectionFilter">
          <option value="all" id="sectionAllOption">Alla</option>
          {section_options}
        </select>
      </div>
      <div>
        <label id="categoryFilterLabel" for="categoryFilter">Filtrera objekttyp</label>
        <select id="categoryFilter">
          <option value="all" id="categoryAllOption">Alla</option>
          {category_options}
        </select>
      </div>
      <div class="actions">
        <button id="shareBtn" type="button">Dela</button>
        <button id="downloadBtn" type="button">Ladda ned urval JSON</button>
        <button id="resetBtn" type="button">Återställ</button>
        <button id="zoomTrailBtn" type="button">Zooma ut hela leden</button>
      </div>
      <label class="toggle" for="trailInfoToggle">
        <input type="checkbox" id="trailInfoToggle" checked>
        <span id="trailInfoToggleLabel">Visa ledinfo</span>
      </label>
      <div class="distance-controls">
        <label class="toggle" for="distanceBandToggle">
          <input type="checkbox" id="distanceBandToggle">
          <span id="distanceBandToggleLabel">Visa avståndsremsa</span>
        </label>
        <select id="distanceBandMeters" aria-label="Avstånd i meter">
          <option value="100">100 m</option>
          <option value="500" selected>500 m</option>
          <option value="1000">1000 m</option>
        </select>
        <span id="distanceBandCount" class="distance-count" style="display:none"></span>
      </div>
      <div class="count" id="visibleCount"></div>
    </div>

    <div class="section">
      <h2 id="mapSectionTitle">Karta (aktuell filtrering)</h2>
      <div class="map-wrap">
        <div id="poiMap"></div>
      </div>
    </div>

    <div class="section">
      <h2 id="allPoiTitle">Alla POI</h2>
      <div class="table-wrap">
        <table id="poiTable">
          <thead>
            <tr>
              <th id="thSatId">SAT ID</th>
              <th id="thName">Namn</th>
              <th id="thSection">Section</th>
              <th id="thCategory">Kategori</th>
              <th id="thStage">Etapp/ö</th>
              <th>sameAs</th>
              <th id="thFirstSeen">Första sedd</th>
              <th id="thUpdated">Uppdaterad</th>
            </tr>
          </thead>
          <tbody>
            {''.join(poi_rows)}
          </tbody>
        </table>
      </div>
    </div>

    <div class="section">
      <h2 id="flowTitle">Flöde: kategori → grupp → etapp/ö</h2>
      <div class="chart-wrap">
        <div id="sankeyChart"></div>
      </div>
    </div>

    <div class="section">
      <h2 id="sectionOverviewTitle">Etapp/ö-översikt</h2>
      <div class="table-wrap">
        <table id="sectionTable">
          <thead>
            <tr>
              <th id="thSectionOverviewSection">Section</th>
              <th id="thSectionOverviewWikidata">Wikidata etapp/ö</th>
              <th>POI</th>
              <th id="thSectionOverviewWithWikidata">Med Wikidata-länk</th>
              <th id="thSectionOverviewWithOsm">Med OSM-länk</th>
              <th id="thSectionOverviewTopCategories">Toppkategorier</th>
            </tr>
          </thead>
          <tbody>
            {''.join(section_rows)}
          </tbody>
        </table>
      </div>
    </div>

    <div class="footer">
      <span id="versionCreatedLabel">Version skapad</span>: <strong>{generated_at}</strong> |
      <a href="https://github.com/salgo60/sat-sync" target="_blank">GitHub: salgo60/sat-sync</a> |
      <span id="sourcesLabel">Källor</span>: <a href="{POIS_URL}" target="_blank">pois.geojson</a> |
      <a href="{TRAIL_URL}" target="_blank">trail.jsonld</a> |
      <a href="{SECTIONS_INDEX_URL}" target="_blank">sections-index.json</a> |
      <a href="https://map.stockholmarchipelagotrail.com/data-sources" target="_blank">data-sources</a> |
      <a href="https://www.wikidata.org/wiki/Q131318799" target="_blank">Wikidata route</a>
    </div>
  </div>

  <script>
    (function() {{
      const languageFilter = document.getElementById('languageFilter');
      const sectionFilter = document.getElementById('sectionFilter');
      const categoryFilter = document.getElementById('categoryFilter');
      const trailInfoToggle = document.getElementById('trailInfoToggle');
      const distanceBandToggle = document.getElementById('distanceBandToggle');
      const distanceBandMeters = document.getElementById('distanceBandMeters');
      const distanceBandCount = document.getElementById('distanceBandCount');
      const shareBtn = document.getElementById('shareBtn');
      const downloadBtn = document.getElementById('downloadBtn');
      const resetBtn = document.getElementById('resetBtn');
      const zoomTrailBtn = document.getElementById('zoomTrailBtn');
      const poiRows = Array.from(document.querySelectorAll('#poiTable tbody tr'));
      const sectionRows = Array.from(document.querySelectorAll('#sectionTable tbody tr'));
      const visibleCount = document.getElementById('visibleCount');
      const poiFlow = {poi_flow_json};
      const poiMapData = {poi_map_json};
      const poiById = new Map(poiMapData.filter((p) => !!p.id).map((p) => [p.id, p]));
      const totalPoiCount = poiMapData.length;
      const sectionValues = new Set(Array.from(sectionFilter.options).map(o => o.value));
      const categoryValues = new Set(Array.from(categoryFilter.options).map(o => o.value));
      const trailGeoJson = {trail_geojson_json};
      const sectionsIndex = {sections_index_json};
      const map = L.map('poiMap').setView([59.2, 18.5], 8);
      let preserveMapView = false;
      let isProgrammaticMapMove = false;
      let lastSection = null;
      let lastCategory = null;
      const osmTagCache = new Map();
      const markerLayer = L.layerGroup().addTo(map);
      const sectionLayer = L.layerGroup().addTo(map);
      const distanceBandLayer = L.geoJSON(trailGeoJson, {{
        interactive: false,
        style: {{
          color: '#60a5fa',
          opacity: 0.35,
          fillOpacity: 0.22,
          weight: 14,
          lineCap: 'round',
          lineJoin: 'round'
        }}
      }});
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

      const i18n = {{
        sv: {{
          all: 'Alla',
          headerTitle: '🧭 SAT POI Dashboard',
          headerSubtitle: 'Alla objekt i pois.geojson med koppling till etapp/ö (Wikidata), section och objekttyp',
          statTotalLabel: 'Totalt POI',
          statSectionsLabel: 'Etapp/ö (sections)',
          statCategoriesLabel: 'Objekttyper',
          statWikidataLabel: 'Wikidata-etapper',
          languageFilterLabel: 'Språk',
          languageHint: 'Svenska språken och turistspråken är separerade i listan.',
          sectionFilterLabel: 'Filtrera etapp/ö',
          categoryFilterLabel: 'Filtrera objekttyp',
          shareBtn: 'Dela',
          downloadBtn: 'Ladda ned urval JSON',
          resetBtn: 'Återställ',
          zoomTrailBtn: 'Zooma ut hela leden',
          trailInfoToggleLabel: 'Visa ledinfo',
          distanceBandToggleLabel: 'Visa avståndsremsa',
          mapSectionTitle: 'Karta (aktuell filtrering)',
          allPoiTitle: 'Alla POI',
          flowTitle: 'Flöde: kategori → grupp → etapp/ö',
          sectionOverviewTitle: 'Etapp/ö-översikt',
          thName: 'Namn',
          thSection: 'Section',
          thCategory: 'Kategori',
          thStage: 'Etapp/ö',
          thFirstSeen: 'Första sedd',
          thUpdated: 'Uppdaterad',
          thSectionOverviewWithWikidata: 'Med Wikidata-länk',
          thSectionOverviewWithOsm: 'Med OSM-länk',
          thSectionOverviewTopCategories: 'Toppkategorier',
          versionCreatedLabel: 'Version skapad',
          sourcesLabel: 'Källor',
          visibleCount: 'Visar {{visible}} av {{total}} POI',
          distanceCount: '{{within}} inom {{meters}} m',
          section: 'Section',
          category: 'Kategori',
          openSatMap: 'Öppna i SAT-kartan',
          osmTags: 'OSM-taggar',
          noOsmTags: 'Inga OSM-taggar hittades.',
          noOsmRef: 'Ingen OSM-referens för objektet.',
          loadingOsmTags: 'Laddar OSM-taggar...',
          cannotLoadOsmTags: 'Kunde inte hämta OSM-taggar (HTTP {{status}}).',
          failedOsmTags: 'Fel vid hämtning av OSM-taggar: {{message}}',
          copiedShareLink: 'Delningslänk kopierad:\\n{{url}}',
          copyLinkPrompt: 'Kopiera länken:',
          sankeyTitlePrefix: 'POI-flöde för',
          sankeyAllStages: 'alla etapper',
          sankeyStagePrefix: 'etapp'
        }},
        en: {{
          all: 'All',
          headerTitle: '🧭 SAT POI Dashboard',
          headerSubtitle: 'All objects in pois.geojson linked to stage/island (Wikidata), section and object type',
          statTotalLabel: 'Total POI',
          statSectionsLabel: 'Stage/island (sections)',
          statCategoriesLabel: 'Object types',
          statWikidataLabel: 'Wikidata stages',
          languageFilterLabel: 'Language',
          languageHint: 'Swedish-language set and tourist-language set are separated in the list.',
          sectionFilterLabel: 'Filter by stage/island',
          categoryFilterLabel: 'Filter by object type',
          shareBtn: 'Share',
          downloadBtn: 'Download selection JSON',
          resetBtn: 'Reset',
          zoomTrailBtn: 'Zoom out to whole trail',
          trailInfoToggleLabel: 'Show trail info',
          distanceBandToggleLabel: 'Show distance band',
          mapSectionTitle: 'Map (current filter)',
          allPoiTitle: 'All POI',
          flowTitle: 'Flow: category → group → stage/island',
          sectionOverviewTitle: 'Stage/island overview',
          thName: 'Name',
          thSection: 'Section',
          thCategory: 'Category',
          thStage: 'Stage/island',
          thFirstSeen: 'First seen',
          thUpdated: 'Updated',
          thSectionOverviewWithWikidata: 'With Wikidata link',
          thSectionOverviewWithOsm: 'With OSM link',
          thSectionOverviewTopCategories: 'Top categories',
          versionCreatedLabel: 'Version created',
          sourcesLabel: 'Sources',
          visibleCount: 'Showing {{visible}} of {{total}} POI',
          distanceCount: '{{within}} within {{meters}} m',
          section: 'Section',
          category: 'Category',
          openSatMap: 'Open in SAT map',
          osmTags: 'OSM tags',
          noOsmTags: 'No OSM tags found.',
          noOsmRef: 'No OSM reference for this object.',
          loadingOsmTags: 'Loading OSM tags...',
          cannotLoadOsmTags: 'Could not load OSM tags (HTTP {{status}}).',
          failedOsmTags: 'Error loading OSM tags: {{message}}',
          copiedShareLink: 'Share link copied:\\n{{url}}',
          copyLinkPrompt: 'Copy the link:',
          sankeyTitlePrefix: 'POI flow for',
          sankeyAllStages: 'all stages',
          sankeyStagePrefix: 'stage'
        }}
      }};

      const i18nExtended = {{
        ar: {{ all: 'الكل', languageFilterLabel: 'اللغة', sectionFilterLabel: 'تصفية حسب المرحلة/الجزيرة', categoryFilterLabel: 'تصفية حسب نوع الكائن', shareBtn: 'مشاركة', downloadBtn: 'تنزيل JSON', resetBtn: 'إعادة تعيين', zoomTrailBtn: 'تصغير إلى كامل المسار', trailInfoToggleLabel: 'إظهار معلومات المسار', distanceBandToggleLabel: 'إظهار نطاق المسافة', mapSectionTitle: 'الخريطة (التصفية الحالية)', allPoiTitle: 'كل نقاط الاهتمام', flowTitle: 'التدفق: الفئة → المجموعة → المرحلة/الجزيرة', sectionOverviewTitle: 'نظرة عامة على المراحل/الجزر', versionCreatedLabel: 'تم إنشاء النسخة', sourcesLabel: 'المصادر', section: 'القسم', category: 'الفئة', openSatMap: 'افتح في خريطة SAT', thName: 'الاسم', thStage: 'المرحلة/الجزيرة', thFirstSeen: 'أول ظهور', thUpdated: 'محدّث' }},
        fi: {{ all: 'Kaikki', languageFilterLabel: 'Kieli', sectionFilterLabel: 'Suodata etapin/saaren mukaan', categoryFilterLabel: 'Suodata kohdelajin mukaan', shareBtn: 'Jaa', downloadBtn: 'Lataa JSON-valinta', resetBtn: 'Nollaa', zoomTrailBtn: 'Zoomaa koko reitille', trailInfoToggleLabel: 'Näytä reittitiedot', distanceBandToggleLabel: 'Näytä etäisyysvyöhyke', mapSectionTitle: 'Kartta (nykyinen suodatus)', allPoiTitle: 'Kaikki POI:t', flowTitle: 'Virta: kategoria → ryhmä → etappi/saari', sectionOverviewTitle: 'Etappi-/saariyhteenveto', versionCreatedLabel: 'Versio luotu', sourcesLabel: 'Lähteet', section: 'Osio', category: 'Kategoria', openSatMap: 'Avaa SAT-kartassa', thName: 'Nimi', thStage: 'Etappi/saari', thFirstSeen: 'Ensimmäinen havainto', thUpdated: 'Päivitetty' }},
        so: {{ all: 'Dhammaan', languageFilterLabel: 'Luqad', sectionFilterLabel: 'Ku shaandhee marxalad/jasiirad', categoryFilterLabel: 'Ku shaandhee nooca shayga', shareBtn: 'Wadaag', downloadBtn: 'Soo dejiso JSON', resetBtn: 'Dib u deji', zoomTrailBtn: 'Ka fogee jidka oo dhan', trailInfoToggleLabel: 'Muuji xogta jidka', distanceBandToggleLabel: 'Muuji xadka masaafada', mapSectionTitle: 'Khariidad (shaandhaynta hadda)', allPoiTitle: 'Dhammaan POI', flowTitle: 'Socod: nooc → koox → marxalad/jasiirad', sectionOverviewTitle: 'Dulmar marxalad/jasiirad', versionCreatedLabel: 'Nooca la sameeyay', sourcesLabel: 'Ilaha', section: 'Qayb', category: 'Nooc', openSatMap: 'Ka fur khariidadda SAT' }},
        fa: {{ all: 'همه', languageFilterLabel: 'زبان', sectionFilterLabel: 'فیلتر بر اساس مرحله/جزیره', categoryFilterLabel: 'فیلتر بر اساس نوع شیء', shareBtn: 'اشتراک‌گذاری', downloadBtn: 'دانلود JSON', resetBtn: 'بازنشانی', zoomTrailBtn: 'بزرگ‌نمایی روی کل مسیر', trailInfoToggleLabel: 'نمایش اطلاعات مسیر', distanceBandToggleLabel: 'نمایش نوار فاصله', mapSectionTitle: 'نقشه (فیلتر فعلی)', allPoiTitle: 'همه POIها', flowTitle: 'جریان: دسته‌بندی → گروه → مرحله/جزیره', sectionOverviewTitle: 'نمای کلی مرحله/جزیره', versionCreatedLabel: 'نسخه ایجاد شد', sourcesLabel: 'منابع', section: 'بخش', category: 'دسته‌بندی', openSatMap: 'باز کردن در نقشه SAT' }},
        ckb: {{ all: 'هەموو', languageFilterLabel: 'زمان', sectionFilterLabel: 'پاڵاوتن بە پێی قۆناغ/دوورگە', categoryFilterLabel: 'پاڵاوتن بە پێی جۆری شت', shareBtn: 'هاوبەشکردن', downloadBtn: 'داگرتنی JSON', resetBtn: 'ڕێکخستنەوە', zoomTrailBtn: 'زوم دەرەوە بۆ تەواوی ڕێگا', trailInfoToggleLabel: 'پیشاندانی زانیاری ڕێگا', distanceBandToggleLabel: 'پیشاندانی شریتی دووری', mapSectionTitle: 'نەخشە (پاڵاوتنی ئێستا)', allPoiTitle: 'هەموو POI', flowTitle: 'ڕەوت: پۆل → گروپ → قۆناغ/دوورگە', sectionOverviewTitle: 'پوختەی قۆناغ/دوورگە', versionCreatedLabel: 'وەشان دروستکرا', sourcesLabel: 'سەرچاوەکان', section: 'بەش', category: 'پۆل' }},
        ti: {{ all: 'ኩሉ', languageFilterLabel: 'ቋንቋ', sectionFilterLabel: 'ብደረጃ/ደሴት ምረጽ', categoryFilterLabel: 'ብዓይነት ነገር ምረጽ', shareBtn: 'ኣካፍል', downloadBtn: 'JSON ኣውርድ', resetBtn: 'ዳግም ምድላው', zoomTrailBtn: 'ናብ ኩሉ መንገዲ ኣውጽእ', trailInfoToggleLabel: 'ሓበሬታ መንገዲ ኣርኢ', distanceBandToggleLabel: 'ርሕቀት ክልል ኣርኢ', mapSectionTitle: 'ካርታ (ሕጂ ማጣርያ)', allPoiTitle: 'ኩሉ POI', flowTitle: 'ፍሰት: ምድብ → ጉጅለ → ደረጃ/ደሴት', sectionOverviewTitle: 'ሓፈሻዊ ደረጃ/ደሴት', versionCreatedLabel: 'ስሪት ተፈጢሩ', sourcesLabel: 'ምንጮች', section: 'ክፍሊ', category: 'ምድብ' }},
        pl: {{ all: 'Wszystkie', languageFilterLabel: 'Język', sectionFilterLabel: 'Filtruj wg etapu/wyspy', categoryFilterLabel: 'Filtruj wg typu obiektu', shareBtn: 'Udostępnij', downloadBtn: 'Pobierz JSON', resetBtn: 'Resetuj', zoomTrailBtn: 'Oddal na cały szlak', trailInfoToggleLabel: 'Pokaż informacje o szlaku', distanceBandToggleLabel: 'Pokaż pas odległości', mapSectionTitle: 'Mapa (bieżący filtr)', allPoiTitle: 'Wszystkie POI', flowTitle: 'Przepływ: kategoria → grupa → etap/wyspa', sectionOverviewTitle: 'Przegląd etapów/wysp', versionCreatedLabel: 'Wersja utworzona', sourcesLabel: 'Źródła', section: 'Sekcja', category: 'Kategoria', openSatMap: 'Otwórz w mapie SAT', thName: 'Nazwa', thStage: 'Etap/wyspa', thFirstSeen: 'Pierwsze wykrycie', thUpdated: 'Zaktualizowano' }},
        tr: {{ all: 'Tümü', languageFilterLabel: 'Dil', sectionFilterLabel: 'Etap/adaya göre filtrele', categoryFilterLabel: 'Nesne türüne göre filtrele', shareBtn: 'Paylaş', downloadBtn: 'JSON indir', resetBtn: 'Sıfırla', zoomTrailBtn: 'Tüm rotaya uzaklaş', trailInfoToggleLabel: 'Rota bilgisini göster', distanceBandToggleLabel: 'Mesafe bandını göster', mapSectionTitle: 'Harita (mevcut filtre)', allPoiTitle: 'Tüm POI', flowTitle: 'Akış: kategori → grup → etap/ada', sectionOverviewTitle: 'Etap/ada özeti', versionCreatedLabel: 'Sürüm oluşturuldu', sourcesLabel: 'Kaynaklar', section: 'Bölüm', category: 'Kategori', openSatMap: 'SAT haritasında aç', thName: 'Ad', thStage: 'Etap/ada', thFirstSeen: 'İlk görülen', thUpdated: 'Güncellendi' }},
        es: {{ all: 'Todos', languageFilterLabel: 'Idioma', sectionFilterLabel: 'Filtrar por etapa/isla', categoryFilterLabel: 'Filtrar por tipo de objeto', shareBtn: 'Compartir', downloadBtn: 'Descargar JSON', resetBtn: 'Restablecer', zoomTrailBtn: 'Alejar a todo el sendero', trailInfoToggleLabel: 'Mostrar info del sendero', distanceBandToggleLabel: 'Mostrar banda de distancia', mapSectionTitle: 'Mapa (filtro actual)', allPoiTitle: 'Todos los POI', flowTitle: 'Flujo: categoría → grupo → etapa/isla', sectionOverviewTitle: 'Resumen de etapas/islas', versionCreatedLabel: 'Versión creada', sourcesLabel: 'Fuentes', section: 'Sección', category: 'Categoría', openSatMap: 'Abrir en mapa SAT', thName: 'Nombre', thStage: 'Etapa/isla', thFirstSeen: 'Primera vez visto', thUpdated: 'Actualizado' }},
        nb: {{ all: 'Alle', languageFilterLabel: 'Språk', sectionFilterLabel: 'Filtrer etter etappe/øy', categoryFilterLabel: 'Filtrer etter objekttype', shareBtn: 'Del', downloadBtn: 'Last ned JSON', resetBtn: 'Tilbakestill', zoomTrailBtn: 'Zoom ut til hele leden', trailInfoToggleLabel: 'Vis ledinfo', distanceBandToggleLabel: 'Vis avstandsbånd', mapSectionTitle: 'Kart (nåværende filter)', allPoiTitle: 'Alle POI', flowTitle: 'Flyt: kategori → gruppe → etappe/øy', sectionOverviewTitle: 'Oversikt etappe/øy', versionCreatedLabel: 'Versjon opprettet', sourcesLabel: 'Kilder', section: 'Seksjon', category: 'Kategori', openSatMap: 'Åpne i SAT-kart', thName: 'Navn', thStage: 'Etappe/øy', thFirstSeen: 'Først sett', thUpdated: 'Oppdatert' }},
        nn: {{ all: 'Alle', languageFilterLabel: 'Språk', sectionFilterLabel: 'Filtrer etter etappe/øy', categoryFilterLabel: 'Filtrer etter objekttype', shareBtn: 'Del', downloadBtn: 'Last ned JSON', resetBtn: 'Tilbakestill', zoomTrailBtn: 'Zoom ut til heile leden', trailInfoToggleLabel: 'Vis leddinfo', distanceBandToggleLabel: 'Vis avstandsbånd', mapSectionTitle: 'Kart (gjeldande filter)', allPoiTitle: 'Alle POI', flowTitle: 'Flyt: kategori → gruppe → etappe/øy', sectionOverviewTitle: 'Oversikt etappe/øy', versionCreatedLabel: 'Versjon oppretta', sourcesLabel: 'Kjelder', section: 'Seksjon', category: 'Kategori', openSatMap: 'Opne i SAT-kart' }},
        da: {{ all: 'Alle', languageFilterLabel: 'Sprog', sectionFilterLabel: 'Filtrer efter etape/ø', categoryFilterLabel: 'Filtrer efter objekttype', shareBtn: 'Del', downloadBtn: 'Download JSON', resetBtn: 'Nulstil', zoomTrailBtn: 'Zoom ud til hele stien', trailInfoToggleLabel: 'Vis stiinfo', distanceBandToggleLabel: 'Vis afstandsbånd', mapSectionTitle: 'Kort (aktuelt filter)', allPoiTitle: 'Alle POI', flowTitle: 'Flow: kategori → gruppe → etape/ø', sectionOverviewTitle: 'Oversigt etape/ø', versionCreatedLabel: 'Version oprettet', sourcesLabel: 'Kilder', section: 'Sektion', category: 'Kategori', openSatMap: 'Åbn i SAT-kort' }},
        de: {{ all: 'Alle', languageFilterLabel: 'Sprache', sectionFilterLabel: 'Nach Etappe/Insel filtern', categoryFilterLabel: 'Nach Objekttyp filtern', shareBtn: 'Teilen', downloadBtn: 'Auswahl als JSON herunterladen', resetBtn: 'Zurücksetzen', zoomTrailBtn: 'Auf gesamten Trail zoomen', trailInfoToggleLabel: 'Trail-Info anzeigen', distanceBandToggleLabel: 'Entfernungsband anzeigen', mapSectionTitle: 'Karte (aktueller Filter)', allPoiTitle: 'Alle POI', flowTitle: 'Fluss: Kategorie → Gruppe → Etappe/Insel', sectionOverviewTitle: 'Etappen-/Inselübersicht', versionCreatedLabel: 'Version erstellt', sourcesLabel: 'Quellen', section: 'Abschnitt', category: 'Kategorie', openSatMap: 'In SAT-Karte öffnen', thName: 'Name', thStage: 'Etappe/Insel', thFirstSeen: 'Erstmals gesehen', thUpdated: 'Aktualisiert' }},
        nl: {{ all: 'Alle', languageFilterLabel: 'Taal', sectionFilterLabel: 'Filter op etappe/eiland', categoryFilterLabel: 'Filter op objecttype', shareBtn: 'Delen', downloadBtn: 'Selectie JSON downloaden', resetBtn: 'Resetten', zoomTrailBtn: 'Uitzoomen naar hele route', trailInfoToggleLabel: 'Route-info tonen', distanceBandToggleLabel: 'Afstandsband tonen', mapSectionTitle: 'Kaart (huidige filter)', allPoiTitle: 'Alle POI', flowTitle: 'Stroom: categorie → groep → etappe/eiland', sectionOverviewTitle: 'Overzicht etappe/eiland', versionCreatedLabel: 'Versie gemaakt', sourcesLabel: 'Bronnen', section: 'Sectie', category: 'Categorie', openSatMap: 'Openen in SAT-kaart' }},
        fr: {{ all: 'Tous', languageFilterLabel: 'Langue', sectionFilterLabel: 'Filtrer par étape/île', categoryFilterLabel: 'Filtrer par type d’objet', shareBtn: 'Partager', downloadBtn: 'Télécharger JSON', resetBtn: 'Réinitialiser', zoomTrailBtn: 'Dézoomer sur tout le sentier', trailInfoToggleLabel: 'Afficher infos du sentier', distanceBandToggleLabel: 'Afficher la bande de distance', mapSectionTitle: 'Carte (filtre actuel)', allPoiTitle: 'Tous les POI', flowTitle: 'Flux : catégorie → groupe → étape/île', sectionOverviewTitle: 'Vue d’ensemble étape/île', versionCreatedLabel: 'Version créée', sourcesLabel: 'Sources', section: 'Section', category: 'Catégorie', openSatMap: 'Ouvrir dans la carte SAT', thName: 'Nom', thStage: 'Étape/île', thFirstSeen: 'Vu pour la première fois', thUpdated: 'Mis à jour' }},
        it: {{ all: 'Tutti', languageFilterLabel: 'Lingua', sectionFilterLabel: 'Filtra per tappa/isola', categoryFilterLabel: 'Filtra per tipo oggetto', shareBtn: 'Condividi', downloadBtn: 'Scarica JSON selezione', resetBtn: 'Reimposta', zoomTrailBtn: 'Zoom out su tutto il percorso', trailInfoToggleLabel: 'Mostra info sentiero', distanceBandToggleLabel: 'Mostra fascia distanza', mapSectionTitle: 'Mappa (filtro corrente)', allPoiTitle: 'Tutti i POI', flowTitle: 'Flusso: categoria → gruppo → tappa/isola', sectionOverviewTitle: 'Panoramica tappa/isola', versionCreatedLabel: 'Versione creata', sourcesLabel: 'Fonti', section: 'Sezione', category: 'Categoria', openSatMap: 'Apri nella mappa SAT' }},
        zh: {{ all: '全部', languageFilterLabel: '语言', sectionFilterLabel: '按路段/岛屿筛选', categoryFilterLabel: '按对象类型筛选', shareBtn: '分享', downloadBtn: '下载 JSON', resetBtn: '重置', zoomTrailBtn: '缩放到整条步道', trailInfoToggleLabel: '显示步道信息', distanceBandToggleLabel: '显示距离带', mapSectionTitle: '地图（当前筛选）', allPoiTitle: '全部 POI', flowTitle: '流向：类别 → 分组 → 路段/岛屿', sectionOverviewTitle: '路段/岛屿概览', versionCreatedLabel: '版本创建时间', sourcesLabel: '来源', section: '区段', category: '类别', openSatMap: '在 SAT 地图中打开', thName: '名称', thStage: '路段/岛屿', thFirstSeen: '首次发现', thUpdated: '已更新' }},
        ja: {{ all: 'すべて', languageFilterLabel: '言語', sectionFilterLabel: '区間/島で絞り込み', categoryFilterLabel: 'オブジェクト種別で絞り込み', shareBtn: '共有', downloadBtn: 'JSONをダウンロード', resetBtn: 'リセット', zoomTrailBtn: 'トレイル全体にズームアウト', trailInfoToggleLabel: 'トレイル情報を表示', distanceBandToggleLabel: '距離バンドを表示', mapSectionTitle: '地図（現在のフィルター）', allPoiTitle: 'すべての POI', flowTitle: 'フロー：カテゴリ → グループ → 区間/島', sectionOverviewTitle: '区間/島の概要', versionCreatedLabel: '作成バージョン', sourcesLabel: 'ソース', section: 'セクション', category: 'カテゴリ', openSatMap: 'SATマップで開く', thName: '名称', thStage: '区間/島', thFirstSeen: '初回確認', thUpdated: '更新日' }},
        ru: {{ all: 'Все', languageFilterLabel: 'Язык', sectionFilterLabel: 'Фильтр по этапу/острову', categoryFilterLabel: 'Фильтр по типу объекта', shareBtn: 'Поделиться', downloadBtn: 'Скачать JSON', resetBtn: 'Сбросить', zoomTrailBtn: 'Уменьшить до всего маршрута', trailInfoToggleLabel: 'Показать информацию о тропе', distanceBandToggleLabel: 'Показать полосу расстояния', mapSectionTitle: 'Карта (текущий фильтр)', allPoiTitle: 'Все POI', flowTitle: 'Поток: категория → группа → этап/остров', sectionOverviewTitle: 'Обзор этапов/островов', versionCreatedLabel: 'Версия создана', sourcesLabel: 'Источники', section: 'Секция', category: 'Категория', openSatMap: 'Открыть в карте SAT', thName: 'Название', thStage: 'Этап/остров', thFirstSeen: 'Первое обнаружение', thUpdated: 'Обновлено' }}
      }};

      const i18nCoreRequested = {{
        ar: {{ headerTitle:'🧭 لوحة SAT POI', headerSubtitle:'كل العناصر في pois.geojson المرتبطة بالمرحلة/الجزيرة (Wikidata) والقسم ونوع الكائن', statTotalLabel:'إجمالي POI', statSectionsLabel:'المرحلة/الجزيرة (الأقسام)', statCategoriesLabel:'أنواع الكائنات', statWikidataLabel:'مراحل ويكي بيانات', thName:'الاسم', thSection:'القسم' }},
        fi: {{ headerTitle:'🧭 SAT POI -koontinäkymä', headerSubtitle:'Kaikki pois.geojson-objektit linkitettynä etappiin/saareen (Wikidata), osioon ja kohdelajiin', statTotalLabel:'POI yhteensä', statSectionsLabel:'Etappi/saari (osiot)', statCategoriesLabel:'Objektityypit', statWikidataLabel:'Wikidata-etapit', thName:'Nimi', thSection:'Osio' }},
        so: {{ headerTitle:'🧭 SAT POI Dashboard', headerSubtitle:'Dhammaan walxaha ku jira pois.geojson oo ku xiran marxalad/jasiirad (Wikidata), qayb iyo nooca shayga', statTotalLabel:'Wadarta POI', statSectionsLabel:'Marxalad/jasiirad (qaybo)', statCategoriesLabel:'Noocyada shayga', statWikidataLabel:'Marxaladaha Wikidata', thName:'Magac', thSection:'Qayb' }},
        fa: {{ headerTitle:'🧭 داشبورد SAT POI', headerSubtitle:'همه اشیاء در pois.geojson مرتبط با مرحله/جزیره (Wikidata)، بخش و نوع شیء', statTotalLabel:'مجموع POI', statSectionsLabel:'مرحله/جزیره (بخش‌ها)', statCategoriesLabel:'نوع اشیاء', statWikidataLabel:'مراحل ویکی‌داده', thName:'نام', thSection:'بخش' }},
        ckb: {{ headerTitle:'🧭 داشبۆردی SAT POI', headerSubtitle:'هەموو ئۆبجێکتەکانی pois.geojson بەستراون بە قۆناغ/دوورگە (Wikidata)، بەش و جۆری شت', statTotalLabel:'کۆی POI', statSectionsLabel:'قۆناغ/دوورگە (بەشەکان)', statCategoriesLabel:'جۆرەکانی شت', statWikidataLabel:'قۆناغەکانی Wikidata', thName:'ناو', thSection:'بەش' }},
        ti: {{ headerTitle:'🧭 SAT POI Dashboard', headerSubtitle:'ኩሎም ኣብ pois.geojson ዘለዉ ኣቕሑ ምስ ደረጃ/ደሴት (Wikidata)፣ ክፍሊን ዓይነት ኣቕሓን ዝተኣሳሰሩ', statTotalLabel:'ጠቕላላ POI', statSectionsLabel:'ደረጃ/ደሴት (ክፍልታት)', statCategoriesLabel:'ዓይነታት ኣቕሓ', statWikidataLabel:'Wikidata ደረጃታት', thName:'ስም', thSection:'ክፍሊ' }},
        pl: {{ headerTitle:'🧭 Panel SAT POI', headerSubtitle:'Wszystkie obiekty w pois.geojson powiązane z etapem/wyspą (Wikidata), sekcją i typem obiektu', statTotalLabel:'Łącznie POI', statSectionsLabel:'Etap/wyspa (sekcje)', statCategoriesLabel:'Typy obiektów', statWikidataLabel:'Etapy Wikidata', thName:'Nazwa', thSection:'Sekcja' }},
        tr: {{ headerTitle:'🧭 SAT POI Gösterge Paneli', headerSubtitle:'pois.geojson içindeki tüm nesneler etap/ada (Wikidata), bölüm ve nesne türü ile bağlantılı', statTotalLabel:'Toplam POI', statSectionsLabel:'Etap/ada (bölümler)', statCategoriesLabel:'Nesne türleri', statWikidataLabel:'Wikidata etapları', thName:'Ad', thSection:'Bölüm' }},
        es: {{ headerTitle:'🧭 Panel SAT POI', headerSubtitle:'Todos los objetos en pois.geojson vinculados a etapa/isla (Wikidata), sección y tipo de objeto', statTotalLabel:'POI totales', statSectionsLabel:'Etapa/isla (secciones)', statCategoriesLabel:'Tipos de objeto', statWikidataLabel:'Etapas Wikidata', thName:'Nombre', thSection:'Sección' }},
        nb: {{ headerTitle:'🧭 SAT POI-dashbord', headerSubtitle:'Alle objekter i pois.geojson koblet til etappe/øy (Wikidata), seksjon og objekttype', statTotalLabel:'Totalt POI', statSectionsLabel:'Etappe/øy (seksjoner)', statCategoriesLabel:'Objekttyper', statWikidataLabel:'Wikidata-etapper', thName:'Navn', thSection:'Seksjon' }},
        nn: {{ headerTitle:'🧭 SAT POI-dashbord', headerSubtitle:'Alle objekt i pois.geojson knytte til etappe/øy (Wikidata), seksjon og objekttype', statTotalLabel:'Totalt POI', statSectionsLabel:'Etappe/øy (seksjonar)', statCategoriesLabel:'Objekttypar', statWikidataLabel:'Wikidata-etappar', thName:'Namn', thSection:'Seksjon' }},
        da: {{ headerTitle:'🧭 SAT POI-dashboard', headerSubtitle:'Alle objekter i pois.geojson koblet til etape/ø (Wikidata), sektion og objekttype', statTotalLabel:'Total POI', statSectionsLabel:'Etape/ø (sektioner)', statCategoriesLabel:'Objekttyper', statWikidataLabel:'Wikidata-etaper', thName:'Navn', thSection:'Sektion' }},
        de: {{ headerTitle:'🧭 SAT POI-Dashboard', headerSubtitle:'Alle Objekte in pois.geojson, verknüpft mit Etappe/Insel (Wikidata), Abschnitt und Objekttyp', statTotalLabel:'POI gesamt', statSectionsLabel:'Etappe/Insel (Abschnitte)', statCategoriesLabel:'Objekttypen', statWikidataLabel:'Wikidata-Etappen', thName:'Name', thSection:'Abschnitt' }},
        nl: {{ headerTitle:'🧭 SAT POI-dashboard', headerSubtitle:'Alle objecten in pois.geojson gekoppeld aan etappe/eiland (Wikidata), sectie en objecttype', statTotalLabel:'Totaal POI', statSectionsLabel:'Etappe/eiland (secties)', statCategoriesLabel:'Objecttypen', statWikidataLabel:'Wikidata-etappes', thName:'Naam', thSection:'Sectie' }},
        fr: {{ headerTitle:'🧭 Tableau de bord SAT POI', headerSubtitle:'Tous les objets de pois.geojson liés à une étape/île (Wikidata), une section et un type d’objet', statTotalLabel:'POI total', statSectionsLabel:'Étape/île (sections)', statCategoriesLabel:'Types d’objet', statWikidataLabel:'Étapes Wikidata', thName:'Nom', thSection:'Section' }},
        it: {{ headerTitle:'🧭 Dashboard SAT POI', headerSubtitle:'Tutti gli oggetti in pois.geojson collegati a tappa/isola (Wikidata), sezione e tipo di oggetto', statTotalLabel:'POI totali', statSectionsLabel:'Tappa/isola (sezioni)', statCategoriesLabel:'Tipi di oggetto', statWikidataLabel:'Tappe Wikidata', thName:'Nome', thSection:'Sezione' }},
        zh: {{ headerTitle:'🧭 SAT POI 仪表盘', headerSubtitle:'pois.geojson 中所有对象，关联到路段/岛屿（Wikidata）、区段和对象类型', statTotalLabel:'POI 总数', statSectionsLabel:'路段/岛屿（区段）', statCategoriesLabel:'对象类型', statWikidataLabel:'Wikidata 路段', thName:'名称', thSection:'区段' }},
        ja: {{ headerTitle:'🧭 SAT POI ダッシュボード', headerSubtitle:'pois.geojson 内の全オブジェクト（区間/島・Wikidata・セクション・オブジェクト種別に関連）', statTotalLabel:'POI 合計', statSectionsLabel:'区間/島（セクション）', statCategoriesLabel:'オブジェクト種別', statWikidataLabel:'Wikidata 区間', thName:'名称', thSection:'セクション' }},
        ru: {{ headerTitle:'🧭 Панель SAT POI', headerSubtitle:'Все объекты в pois.geojson, связанные с этапом/островом (Wikidata), секцией и типом объекта', statTotalLabel:'Всего POI', statSectionsLabel:'Этап/остров (секции)', statCategoriesLabel:'Типы объектов', statWikidataLabel:'Этапы Wikidata', thName:'Название', thSection:'Секция' }}
      }};

      const categoryLabels = {{
        sv: {{ toilet:'Toalett', water:'Vatten', shower:'Dusch', firepit:'Eldplats', beach:'Badplats', harbour:'Hamn', food:'Mat', lodging:'Boende', shelter:'Vindskydd', sauna:'Bastu', shop:'Butik', rental:'Uthyrning', attraction:'Sevärdhet', viewpoint:'Utsikt', lighthouse:'Fyr', rowboat:'Roddbåt' }},
        en: {{ toilet:'Toilet', water:'Water', shower:'Shower', firepit:'Firepit', beach:'Beach', harbour:'Harbour', food:'Food', lodging:'Lodging', shelter:'Shelter', sauna:'Sauna', shop:'Shop', rental:'Rental', attraction:'Attraction', viewpoint:'Viewpoint', lighthouse:'Lighthouse', rowboat:'Rowboat' }},
        de: {{ toilet:'Toilette', water:'Wasser', shower:'Dusche', firepit:'Feuerstelle', beach:'Strand', harbour:'Hafen', food:'Essen', lodging:'Unterkunft', shelter:'Schutzhütte', sauna:'Sauna', shop:'Geschäft', rental:'Verleih', attraction:'Sehenswürdigkeit', viewpoint:'Aussichtspunkt', lighthouse:'Leuchtturm', rowboat:'Ruderboot' }},
        fr: {{ toilet:'Toilettes', water:'Eau', shower:'Douche', firepit:'Foyer', beach:'Plage', harbour:'Port', food:'Nourriture', lodging:'Hébergement', shelter:'Abri', sauna:'Sauna', shop:'Boutique', rental:'Location', attraction:'Attraction', viewpoint:'Point de vue', lighthouse:'Phare', rowboat:'Barque' }},
        es: {{ toilet:'Baño', water:'Agua', shower:'Ducha', firepit:'Hoguera', beach:'Playa', harbour:'Puerto', food:'Comida', lodging:'Alojamiento', shelter:'Refugio', sauna:'Sauna', shop:'Tienda', rental:'Alquiler', attraction:'Atracción', viewpoint:'Mirador', lighthouse:'Faro', rowboat:'Bote de remos' }},
        it: {{ toilet:'Toilette', water:'Acqua', shower:'Doccia', firepit:'Focolare', beach:'Spiaggia', harbour:'Porto', food:'Cibo', lodging:'Alloggio', shelter:'Rifugio', sauna:'Sauna', shop:'Negozio', rental:'Noleggio', attraction:'Attrazione', viewpoint:'Punto panoramico', lighthouse:'Faro', rowboat:'Barca a remi' }},
        fi: {{ toilet:'WC', water:'Vesi', shower:'Suihku', firepit:'Nuotiopaikka', beach:'Ranta', harbour:'Satama', food:'Ruoka', lodging:'Majoitus', shelter:'Laavu', sauna:'Sauna', shop:'Kauppa', rental:'Vuokraus', attraction:'Nähtävyys', viewpoint:'Näköalapaikka', lighthouse:'Majakka', rowboat:'Soutuvene' }},
        pl: {{ toilet:'Toaleta', water:'Woda', shower:'Prysznic', firepit:'Miejsce ogniskowe', beach:'Plaża', harbour:'Port', food:'Jedzenie', lodging:'Nocleg', shelter:'Schronienie', sauna:'Sauna', shop:'Sklep', rental:'Wypożyczalnia', attraction:'Atrakcja', viewpoint:'Punkt widokowy', lighthouse:'Latarnia', rowboat:'Łódź wiosłowa' }},
        tr: {{ toilet:'Tuvalet', water:'Su', shower:'Duş', firepit:'Ateş yeri', beach:'Plaj', harbour:'Liman', food:'Yemek', lodging:'Konaklama', shelter:'Sığınak', sauna:'Sauna', shop:'Mağaza', rental:'Kiralama', attraction:'Gezilecek yer', viewpoint:'Seyir noktası', lighthouse:'Deniz feneri', rowboat:'Kürekli tekne' }},
        ru: {{ toilet:'Туалет', water:'Вода', shower:'Душ', firepit:'Костровище', beach:'Пляж', harbour:'Гавань', food:'Еда', lodging:'Проживание', shelter:'Укрытие', sauna:'Сауна', shop:'Магазин', rental:'Прокат', attraction:'Достопримечательность', viewpoint:'Смотровая точка', lighthouse:'Маяк', rowboat:'Гребная лодка' }},
        nl: {{ toilet:'Toilet', water:'Water', shower:'Douche', firepit:'Vuurplaats', beach:'Strand', harbour:'Haven', food:'Eten', lodging:'Verblijf', shelter:'Schuilplaats', sauna:'Sauna', shop:'Winkel', rental:'Verhuur', attraction:'Attractie', viewpoint:'Uitzichtpunt', lighthouse:'Vuurtoren', rowboat:'Roeiboot' }},
        da: {{ toilet:'Toilet', water:'Vand', shower:'Bruser', firepit:'Bålplads', beach:'Strand', harbour:'Havn', food:'Mad', lodging:'Overnatning', shelter:'Shelter', sauna:'Sauna', shop:'Butik', rental:'Udlejning', attraction:'Seværdighed', viewpoint:'Udsigtspunkt', lighthouse:'Fyr', rowboat:'Robåd' }},
        nb: {{ toilet:'Toalett', water:'Vann', shower:'Dusj', firepit:'Bålplass', beach:'Strand', harbour:'Havn', food:'Mat', lodging:'Overnatting', shelter:'Gapahuk', sauna:'Badstue', shop:'Butikk', rental:'Utleie', attraction:'Severdighet', viewpoint:'Utsiktspunkt', lighthouse:'Fyr', rowboat:'Robåt' }},
        nn: {{ toilet:'Toalett', water:'Vatn', shower:'Dusj', firepit:'Bålplass', beach:'Strand', harbour:'Hamn', food:'Mat', lodging:'Overnatting', shelter:'Gapahuk', sauna:'Badstove', shop:'Butikk', rental:'Utleige', attraction:'Severdsemd', viewpoint:'Utsynspunkt', lighthouse:'Fyr', rowboat:'Robåt' }},
        zh: {{ toilet:'厕所', water:'饮用水', shower:'淋浴', firepit:'篝火点', beach:'海滩', harbour:'港口', food:'餐饮', lodging:'住宿', shelter:'庇护所', sauna:'桑拿', shop:'商店', rental:'租赁', attraction:'景点', viewpoint:'观景点', lighthouse:'灯塔', rowboat:'划艇' }},
        ja: {{ toilet:'トイレ', water:'水', shower:'シャワー', firepit:'焚き火場', beach:'ビーチ', harbour:'港', food:'食事', lodging:'宿泊', shelter:'シェルター', sauna:'サウナ', shop:'ショップ', rental:'レンタル', attraction:'見どころ', viewpoint:'展望地点', lighthouse:'灯台', rowboat:'手こぎボート' }},
        ar: {{ toilet:'مرحاض', water:'ماء', shower:'دش', firepit:'موقد نار', beach:'شاطئ', harbour:'ميناء', food:'طعام', lodging:'إقامة', shelter:'مأوى', sauna:'ساونا', shop:'متجر', rental:'تأجير', attraction:'معلم', viewpoint:'نقطة مشاهدة', lighthouse:'منارة', rowboat:'قارب تجديف' }},
        fa: {{ toilet:'سرویس بهداشتی', water:'آب', shower:'دوش', firepit:'محل آتش', beach:'ساحل', harbour:'بندر', food:'غذا', lodging:'اقامت', shelter:'پناهگاه', sauna:'سونا', shop:'فروشگاه', rental:'اجاره', attraction:'جاذبه', viewpoint:'نقطه دید', lighthouse:'فانوس دریایی', rowboat:'قایق پارویی' }},
        so: {{ toilet:'Musqul', water:'Biyo', shower:'Qubays', firepit:'Goob dab', beach:'Xeeb', harbour:'Deked', food:'Cunto', lodging:'Hoy', shelter:'Hoyga', sauna:'Sauna', shop:'Dukaan', rental:'Kireyn', attraction:'Goob dalxiis', viewpoint:'Goob aragti', lighthouse:'Faro', rowboat:'Doon yar' }},
        ckb: {{ toilet:'توالێت', water:'ئاو', shower:'دوش', firepit:'شوێنی ئاگر', beach:'کەناراو', harbour:'بەندر', food:'خواردن', lodging:'مانەوە', shelter:'پەناگە', sauna:'ساونا', shop:'فرۆشگا', rental:'کرێ', attraction:'شوێنی سەرنجڕاکێش', viewpoint:'شوێنی بینین', lighthouse:'فانۆس', rowboat:'بەلەم' }},
        ti: {{ toilet:'መጸዳጃ', water:'ማይ', shower:'ሻወር', firepit:'ቦታ ሓዊ', beach:'ዳርቻ', harbour:'ወደብ', food:'ምግቢ', lodging:'ማረፊያ', shelter:'መጽለሊ', sauna:'ሳውና', shop:'ድኳን', rental:'ክራይ', attraction:'መስሕብ', viewpoint:'ቦታ ርእይቶ', lighthouse:'መብራህቲ ባሕሪ', rowboat:'ጀልባ ሓዊስ' }}
      }};

      const groupLabels = {{
        sv: {{ Facilities:'Faciliteter', Food:'Mat', Accommodation:'Boende', Shop:'Butik', Rental:'Uthyrning', Attraction:'Sevärdhet', Other:'Övrigt' }},
        en: {{ Facilities:'Facilities', Food:'Food', Accommodation:'Accommodation', Shop:'Shop', Rental:'Rental', Attraction:'Attraction', Other:'Other' }},
        de: {{ Facilities:'Service', Food:'Mat', Accommodation:'Boende', Shop:'Butik', Rental:'Uthyrning', Attraction:'Sevärdhet', Other:'Övrigt' }},
        fr: {{ Facilities:'Services', Food:'Restauration', Accommodation:'Hébergement', Shop:'Boutique', Rental:'Location', Attraction:'Attraction', Other:'Autres' }},
        es: {{ Facilities:'Servicios', Food:'Comida', Accommodation:'Alojamiento', Shop:'Tienda', Rental:'Alquiler', Attraction:'Atracción', Other:'Otros' }}
      }};

      function parseLangValue(value) {{
        const raw = String(value || '');
        if (!raw.includes(':')) {{
          return {{ group: 'swedish', code: raw || 'sv' }};
        }}
        const parts = raw.split(':');
        return {{
          group: parts[0] || 'swedish',
          code: parts[1] || 'sv'
        }};
      }}

      function normalizeLangValue(rawValue) {{
        const value = String(rawValue || '');
        if (Array.from(languageFilter.options).some((o) => o.value === value)) return value;
        const parsed = parseLangValue(value);
        const byCode = Array.from(languageFilter.options).find((o) => parseLangValue(o.value).code === parsed.code);
        if (byCode) return byCode.value;
        return 'swedish:sv';
      }}

      function currentLangCode() {{
        const code = parseLangValue(languageFilter.value).code;
        if (code === 'zh-CN') return 'zh';
        if (code === 'zh') return 'zh';
        return code;
      }}

      function t(key, vars) {{
        const lang = currentLangCode();
        const langPack = lang === 'sv'
          ? i18n.sv
          : {{ ...i18n.en, ...(i18nExtended[lang] || {{}}), ...(i18nCoreRequested[lang] || {{}}) }};
        const text = langPack[key] || i18n.en[key] || key;
        if (!vars) return text;
        return text.replace(/\\{{(\\w+)\\}}/g, (_m, name) => String(vars[name] ?? ''));
      }}

      function localizedCategory(rawCategory) {{
        const lang = currentLangCode();
        const table = categoryLabels[lang] || categoryLabels.en;
        return table[rawCategory] || rawCategory;
      }}

      function localizedGroup(rawGroup) {{
        const lang = currentLangCode();
        const table = groupLabels[lang] || groupLabels.en;
        return table[rawGroup] || rawGroup;
      }}

      function localizedPoiName(poi) {{
        if (!poi) return '—';
        const lang = currentLangCode();
        const localized = poi.name_localized || {{}};
        return localized[lang] || localized.en || localized.sv || poi.name || poi.id || '—';
      }}

      function updateLocalizedPoiRows() {{
        poiRows.forEach((row) => {{
          const poiId = row.dataset.poiId;
          if (!poiId || !poiById.has(poiId)) return;
          const poi = poiById.get(poiId);
          const nameCell = row.children[1];
          const categoryCell = row.children[3];
          if (nameCell) nameCell.textContent = localizedPoiName(poi);
          if (categoryCell) categoryCell.textContent = localizedCategory(poi.category || '');
        }});
        Array.from(categoryFilter.options).forEach((opt) => {{
          if (opt.value === 'all') return;
          opt.textContent = localizedCategory(opt.value);
        }});
      }}

      function applyLanguage() {{
        languageFilter.value = normalizeLangValue(languageFilter.value);
        const bindings = {{
          headerTitle: 'headerTitle',
          headerSubtitle: 'headerSubtitle',
          statTotalLabel: 'statTotalLabel',
          statSectionsLabel: 'statSectionsLabel',
          statCategoriesLabel: 'statCategoriesLabel',
          statWikidataLabel: 'statWikidataLabel',
          languageFilterLabel: 'languageFilterLabel',
          languageHint: 'languageHint',
          sectionFilterLabel: 'sectionFilterLabel',
          categoryFilterLabel: 'categoryFilterLabel',
          shareBtn: 'shareBtn',
          downloadBtn: 'downloadBtn',
          resetBtn: 'resetBtn',
          zoomTrailBtn: 'zoomTrailBtn',
          trailInfoToggleLabel: 'trailInfoToggleLabel',
          distanceBandToggleLabel: 'distanceBandToggleLabel',
          mapSectionTitle: 'mapSectionTitle',
          allPoiTitle: 'allPoiTitle',
          flowTitle: 'flowTitle',
          sectionOverviewTitle: 'sectionOverviewTitle',
          versionCreatedLabel: 'versionCreatedLabel',
          sourcesLabel: 'sourcesLabel',
          thName: 'thName',
          thSection: 'section',
          thCategory: 'thCategory',
          thStage: 'thStage',
          thFirstSeen: 'thFirstSeen',
          thUpdated: 'thUpdated',
          thSectionOverviewSection: 'thSection',
          thSectionOverviewWikidata: 'statWikidataLabel',
          thSectionOverviewWithWikidata: 'thSectionOverviewWithWikidata',
          thSectionOverviewWithOsm: 'thSectionOverviewWithOsm',
          thSectionOverviewTopCategories: 'thSectionOverviewTopCategories'
        }};
        Object.entries(bindings).forEach(([id, key]) => {{
          const el = document.getElementById(id);
          if (el) el.textContent = t(key);
        }});
        const sectionAllOption = document.getElementById('sectionAllOption');
        const categoryAllOption = document.getElementById('categoryAllOption');
        if (sectionAllOption) sectionAllOption.textContent = t('all');
        if (categoryAllOption) categoryAllOption.textContent = t('all');
        updateLocalizedPoiRows();
        document.documentElement.lang = currentLangCode();
      }}

      function escapeHtml(text) {{
        return String(text || '').replace(/[&<>"']/g, (ch) => {{
          if (ch === '&') return '&amp;';
          if (ch === '<') return '&lt;';
          if (ch === '>') return '&gt;';
          if (ch === '"') return '&quot;';
          return '&#039;';
        }});
      }}

      function isFiniteCoord(v) {{
        return typeof v === 'number' && Number.isFinite(v);
      }}

      function normalizeBandMeters(raw) {{
        const n = Number(raw);
        if (n === 100 || n === 500 || n === 1000) return n;
        return 500;
      }}

      function normalizeCategoryValue(rawValue) {{
        if (!rawValue) return 'all';
        const parts = String(rawValue)
          .split(',')
          .map((v) => v.trim())
          .filter(Boolean);
        for (const part of parts) {{
          if (categoryValues.has(part)) return part;
        }}
        return 'all';
      }}

      function poiIconMeta(category) {{
        const c = String(category || '').toLowerCase();
        const table = {{
          toilet: {{ emoji: '🚻', color: '#60a5fa', label: 'Toalett' }},
          water: {{ emoji: '💧', color: '#38bdf8', label: 'Vatten' }},
          shower: {{ emoji: '🚿', color: '#22d3ee', label: 'Dusch' }},
          firepit: {{ emoji: '🔥', color: '#fb923c', label: 'Eldplats' }},
          beach: {{ emoji: '🏖️', color: '#fbbf24', label: 'Badplats' }},
          harbour: {{ emoji: '⚓', color: '#34d399', label: 'Hamn' }},
          food: {{ emoji: '🍽️', color: '#f87171', label: 'Mat' }},
          lodging: {{ emoji: '🛏️', color: '#a78bfa', label: 'Boende' }},
          shelter: {{ emoji: '🏕️', color: '#86efac', label: 'Vindskydd' }},
          sauna: {{ emoji: '♨️', color: '#f59e0b', label: 'Bastu' }},
          shop: {{ emoji: '🛒', color: '#4ade80', label: 'Butik' }},
          rental: {{ emoji: '🚲', color: '#f43f5e', label: 'Uthyrning' }},
          attraction: {{ emoji: '⭐', color: '#22c55e', label: 'Sevärdhet' }},
          viewpoint: {{ emoji: '🔭', color: '#67e8f9', label: 'Utsikt' }},
          lighthouse: {{ emoji: '🗼', color: '#fde047', label: 'Fyr' }},
          rowboat: {{ emoji: '🛶', color: '#fb7185', label: 'Roddbåt' }},
        }};
        return table[c] || {{ emoji: '📍', color: '#cbd5e1', label: category || 'POI' }};
      }}

      function findOsmRef(sameAs) {{
        if (!Array.isArray(sameAs)) return null;
        for (const ref of sameAs) {{
          if (typeof ref !== 'string' || !ref.startsWith('osm:')) continue;
          const parts = ref.split(':');
          if (parts.length !== 3) continue;
          const type = parts[1];
          const id = parts[2];
          if (!['node', 'way', 'relation'].includes(type) || !id) continue;
          return {{ type, id, key: `${{type}}/${{id}}` }};
        }}
        return null;
      }}

      function renderOsmTagsHtml(tags) {{
        const entries = Object.entries(tags || {{}}).sort(([a], [b]) => a.localeCompare(b));
        if (entries.length === 0) return `<span>${{t('noOsmTags')}}</span>`;
        const items = entries
          .map(([k, v]) => `<li><code>${{escapeHtml(k)}}</code>: ${{escapeHtml(String(v))}}</li>`)
          .join('');
        return `<ul class="osm-tags-list">${{items}}</ul>`;
      }}

      async function loadOsmTags(ref, targetEl) {{
        if (!targetEl || !ref) return;
        if (osmTagCache.has(ref.key)) {{
          targetEl.innerHTML = renderOsmTagsHtml(osmTagCache.get(ref.key));
          return;
        }}
        targetEl.textContent = t('loadingOsmTags');
        const url = `https://api.openstreetmap.org/api/0.6/${{ref.type}}/${{ref.id}}.json`;
        try {{
          const response = await fetch(url, {{ headers: {{ 'Accept': 'application/json' }} }});
          if (!response.ok) {{
            targetEl.textContent = t('cannotLoadOsmTags', {{ status: response.status }});
            return;
          }}
          const data = await response.json();
          const tags = data?.elements?.[0]?.tags || {{}};
          osmTagCache.set(ref.key, tags);
          targetEl.innerHTML = renderOsmTagsHtml(tags);
        }} catch (err) {{
          targetEl.textContent = t('failedOsmTags', {{ message: err && err.message ? err.message : 'unknown error' }});
        }}
      }}

      function canonicalShareBaseUrl() {{
        if (window.location.protocol === 'file:') {{
          return 'https://salgo60.github.io/sat-sync/sat_poi_dashboard.html';
        }}
        return `${{window.location.origin}}${{window.location.pathname}}`;
      }}

      function canonicalCurrentBaseUrl() {{
        return window.location.href.split('?')[0];
      }}

      function sanitizeValue(value, allowed) {{
        if (!value || !allowed.has(value)) return 'all';
        return value;
      }}

      function stateLabel(sec, cat) {{
        const secText = sec === 'all' ? t('all') : (sectionFilter.options[sectionFilter.selectedIndex]?.text || sec);
        const catText = cat === 'all' ? t('all') : cat;
        return `${{secText}} ${{catText}}`;
      }}

      function currentMapState() {{
        const c = map.getCenter();
        return {{
          lat: Number(c.lat.toFixed(5)),
          lon: Number(c.lng.toFixed(5)),
          z: map.getZoom()
        }};
      }}

      function buildShareUrl(sec, cat, baseUrl) {{
        const safeSec = sanitizeValue(sec, sectionValues);
        const safeCat = sanitizeValue(normalizeCategoryValue(cat), categoryValues);
        const safeLang = normalizeLangValue(languageFilter.value);
        const params = new URLSearchParams();
        if (safeSec !== 'all') params.set('s', safeSec);
        if (safeCat !== 'all') params.set('c', safeCat);
        params.set('lang', safeLang);
        if (!trailInfoToggle.checked) params.set('li', '0');
        if (distanceBandToggle.checked) params.set('db', '1');
        const bandMeters = normalizeBandMeters(distanceBandMeters.value);
        if (bandMeters !== 500) params.set('dm', String(bandMeters));
        const m = currentMapState();
        params.set('lat', String(m.lat));
        params.set('lon', String(m.lon));
        params.set('z', String(m.z));
        const qs = params.toString();
        const root = baseUrl || canonicalShareBaseUrl();
        return qs ? `${{root}}?${{qs}}` : root;
      }}

      function saveStateInUrl(sec, cat) {{
        const url = buildShareUrl(sec, cat, canonicalCurrentBaseUrl());
        window.history.replaceState({{}}, '', url);
      }}

      function restoreStateFromUrl() {{
        const params = new URLSearchParams(window.location.search);
        const sec = sanitizeValue(params.get('s') || params.get('section'), sectionValues);
        const cat = sanitizeValue(
          normalizeCategoryValue(params.get('c') || params.get('category')),
          categoryValues
        );
        languageFilter.value = normalizeLangValue(params.get('lang') || 'swedish:sv');
        applyLanguage();
        sectionFilter.value = sec;
        categoryFilter.value = cat;
        const li = params.get('li');
        trailInfoToggle.checked = li !== '0';
        distanceBandToggle.checked = params.get('db') === '1';
        distanceBandMeters.value = String(normalizeBandMeters(params.get('dm') || '500'));

        const lat = Number(params.get('lat'));
        const lon = Number(params.get('lon'));
        const z = Number(params.get('z'));
        const validLat = Number.isFinite(lat) && lat >= -90 && lat <= 90;
        const validLon = Number.isFinite(lon) && lon >= -180 && lon <= 180;
        const validZoom = Number.isFinite(z) && z >= 3 && z <= 18;
        if (validLat && validLon && validZoom) {{
          preserveMapView = true;
          isProgrammaticMapMove = true;
          map.setView([lat, lon], z);
          setTimeout(() => {{ isProgrammaticMapMove = false; }}, 0);
        }}
      }}

      async function shareCurrentState() {{
        const sec = sectionFilter.value;
        const cat = categoryFilter.value;
        const url = buildShareUrl(sec, cat, canonicalShareBaseUrl());
        try {{
          if (navigator.share) {{
            await navigator.share({{ url }});
          }} else if (navigator.clipboard && navigator.clipboard.writeText) {{
            await navigator.clipboard.writeText(url);
            alert(t('copiedShareLink', {{ url }}));
          }} else {{
            prompt(t('copyLinkPrompt'), url);
          }}
        }} catch (_err) {{
          // användaren avbröt delning eller api saknas
        }}
      }}

      function filteredPois(sec, cat) {{
        const safeSec = sanitizeValue(sec, sectionValues);
        const safeCat = sanitizeValue(normalizeCategoryValue(cat), categoryValues);
        return poiMapData.filter((r) =>
          (safeSec === 'all' || r.section === safeSec) &&
          (safeCat === 'all' || r.category === safeCat)
        );
      }}

      function downloadSelectionJson() {{
        const sec = sectionFilter.value;
        const cat = categoryFilter.value;
        const selected = filteredPois(sec, cat);
        const bandMeters = normalizeBandMeters(distanceBandMeters.value);
        const safeCat = sanitizeValue(normalizeCategoryValue(cat), categoryValues);
        const payload = {{
          generated_at: new Date().toISOString(),
          source: 'sat_poi_dashboard',
          filter: {{
            section: sanitizeValue(sec, sectionValues),
            category: safeCat,
            show_trail_info: trailInfoToggle.checked,
            show_distance_band: distanceBandToggle.checked,
            distance_band_m: bandMeters,
            label: stateLabel(sec, safeCat),
          }},
          count: selected.length,
          items: selected,
        }};
        const blob = new Blob([JSON.stringify(payload, null, 2)], {{ type: 'application/json' }});
        const url = URL.createObjectURL(blob);
        const secPart = payload.filter.section === 'all' ? 'all' : payload.filter.section;
        const catPart = payload.filter.category === 'all' ? 'all' : payload.filter.category;
        const a = document.createElement('a');
        a.href = url;
        a.download = `sat-poi-selection-${{secPart}}-${{catPart}}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      }}

      function resetFilters() {{
        sectionFilter.value = 'all';
        categoryFilter.value = 'all';
        preserveMapView = false;
        applyFilters();
      }}

      function renderMap(sec, cat) {{
        markerLayer.clearLayers();
        sectionLayer.clearLayers();
        const showTrailInfo = trailInfoToggle.checked;
        const showDistanceBand = distanceBandToggle.checked;
        const bandMeters = normalizeBandMeters(distanceBandMeters.value);
        const safeCat = sanitizeValue(normalizeCategoryValue(cat), categoryValues);
        const selectedSection = sec !== 'all'
          ? sectionsIndex.find((s) => s.slug === sec && isFiniteCoord(s.lat) && isFiniteCoord(s.lon))
          : null;
        const filtered = poiMapData.filter((r) =>
          (sec === 'all' || r.section === sec) &&
          (safeCat === 'all' || r.category === safeCat) &&
          isFiniteCoord(r.lat) &&
          isFiniteCoord(r.lon)
        );

        const bounds = [];
        filtered.forEach((r) => {{
          const iconMeta = poiIconMeta(r.category);
          const poiName = localizedPoiName(r);
          const poiCategoryLabel = localizedCategory(r.category || '');
          const icon = L.divIcon({{
            className: '',
            html: `<div class="poi-icon" style="background:${{iconMeta.color}}">${{iconMeta.emoji}}</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
            popupAnchor: [0, -12],
          }});
          const marker = L.marker([r.lat, r.lon], {{ icon }});
          const satUrl = `https://map.stockholmarchipelagotrail.com/sv?id=${{encodeURIComponent(r.id)}}`;
          const imageHtml = r.image
            ? `<img class="popup-thumb" src="${{escapeHtml(r.image)}}" alt="thumbnail">`
            : '';
          const osmRef = findOsmRef(r.same_as);
          const osmHistoryUrl = osmRef ? `https://pewu.github.io/osm-history/#/${{osmRef.type}}/${{osmRef.id}}` : null;
          const osmTagsHtml = osmRef
            ? `<details class="osm-tags"><summary>${{escapeHtml(t('osmTags'))}}</summary><div class="osm-tags-body" data-osm-ref="${{escapeHtml(osmRef.key)}}">${{escapeHtml(t('loadingOsmTags'))}}</div></details>`
            : `<details class="osm-tags"><summary>${{escapeHtml(t('osmTags'))}}</summary><div class="osm-tags-body">${{escapeHtml(t('noOsmRef'))}}</div></details>`;
          const osmHistoryLink = osmHistoryUrl
            ? `<div><a href="${{osmHistoryUrl}}" target="_blank">OSM Deep history</a></div>`
            : '';
          marker.bindPopup(`
            <div style="min-width:180px">
              <strong><span class="poi-icon-badge" style="background:${{iconMeta.color}}">${{iconMeta.emoji}}</span>${{escapeHtml(poiName)}}</strong><br>
              <small>${{escapeHtml(t('section'))}}: ${{escapeHtml(r.section)}} | ${{escapeHtml(t('category'))}}: ${{escapeHtml(poiCategoryLabel)}}</small><br>
              <a href="${{satUrl}}" target="_blank">${{escapeHtml(t('openSatMap'))}}</a>
              ${{osmTagsHtml}}
              ${{osmHistoryLink}}
              ${{imageHtml}}
            </div>
          `);
          marker.on('popupopen', (event) => {{
            if (!osmRef) return;
            const root = event.popup.getElement();
            const candidates = root ? Array.from(root.querySelectorAll('[data-osm-ref]')) : [];
            const node = candidates.find((el) => el.getAttribute('data-osm-ref') === osmRef.key);
            if (node) loadOsmTags(osmRef, node);
          }});
          marker.addTo(markerLayer);
          bounds.push([r.lat, r.lon]);
        }});

        if (showDistanceBand) {{
          const centerLat = map.getCenter().lat || 59.2;
          const metersPerPixel = 156543.03392 * Math.cos(centerLat * Math.PI / 180) / Math.pow(2, map.getZoom());
          const weight = Math.max(8, (2 * bandMeters) / Math.max(metersPerPixel, 0.01));
          distanceBandLayer.setStyle({{
            weight,
            opacity: 0.35,
            fillOpacity: 0.22
          }});
          if (!map.hasLayer(distanceBandLayer)) {{
            distanceBandLayer.addTo(map);
          }}
        }} else if (map.hasLayer(distanceBandLayer)) {{
          map.removeLayer(distanceBandLayer);
        }}

        if (showTrailInfo) {{
          sectionsIndex
            .filter((s) => sec === 'all' || s.slug === sec)
            .forEach((s) => {{
              if (!isFiniteCoord(s.lat) || !isFiniteCoord(s.lon)) return;
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
        }}

        if (!preserveMapView) {{
          if (bounds.length > 0) {{
            isProgrammaticMapMove = true;
            map.fitBounds(bounds, {{ padding: [20, 20], maxZoom: 13 }});
            if (selectedSection && map.getZoom() < 10) {{
              map.setView([selectedSection.lat, selectedSection.lon], 11);
            }}
            setTimeout(() => {{ isProgrammaticMapMove = false; }}, 0);
          }} else if (selectedSection) {{
            isProgrammaticMapMove = true;
            map.setView([selectedSection.lat, selectedSection.lon], 11);
            setTimeout(() => {{ isProgrammaticMapMove = false; }}, 0);
          }} else {{
            const trailBounds = trailLayer.getBounds();
            if (trailBounds.isValid()) {{
              isProgrammaticMapMove = true;
              map.fitBounds(trailBounds, {{ padding: [20, 20], maxZoom: 11 }});
              setTimeout(() => {{ isProgrammaticMapMove = false; }}, 0);
            }}
          }}
        }}
      }}

      function renderSankey(sec, cat) {{
        if (typeof Plotly === 'undefined') return;
        const safeCat = sanitizeValue(normalizeCategoryValue(cat), categoryValues);
        const filtered = poiFlow.filter((r) =>
          (sec === 'all' || r.section === sec) &&
          (safeCat === 'all' || r.category === safeCat)
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
        const displayLabels = labels.map((label) => {{
          if (groupColors[label]) return localizedGroup(label);
          if (label.startsWith("SAT ")) return label;
          return localizedCategory(label);
        }});

        const data = [{{
          type: "sankey",
          arrangement: "snap",
          node: {{
            pad: 10,
            thickness: 20,
            line: {{ color: "rgba(70,70,70,.35)", width: 1 }},
            label: displayLabels,
            color: nodeColor
          }},
          link: {{
            source,
            target,
            value,
            color: linkColor
          }}
        }}];

        const titlePart = sec === 'all' ? t('sankeyAllStages') : `${{t('sankeyStagePrefix')}}: ${{sec}}`;
        const layout = {{
          title: `${{t('sankeyTitlePrefix')}} ${{titlePart}}`,
          margin: {{ l: 20, r: 20, t: 40, b: 10 }},
          font: {{ size: 13 }}
        }};
        Plotly.react('sankeyChart', data, layout, {{displayModeBar: false, responsive: true}});
      }}

      function extractTrailLines() {{
        const lines = [];
        (trailGeoJson.features || []).forEach((f) => {{
          const geom = f && f.geometry ? f.geometry : null;
          if (!geom || !Array.isArray(geom.coordinates)) return;
          if (geom.type === 'LineString') {{
            const line = geom.coordinates
              .filter((c) => Array.isArray(c) && c.length >= 2)
              .map((c) => [Number(c[1]), Number(c[0])])
              .filter((c) => isFiniteCoord(c[0]) && isFiniteCoord(c[1]));
            if (line.length >= 2) lines.push(line);
          }} else if (geom.type === 'MultiLineString') {{
            geom.coordinates.forEach((segment) => {{
              const line = (segment || [])
                .filter((c) => Array.isArray(c) && c.length >= 2)
                .map((c) => [Number(c[1]), Number(c[0])])
                .filter((c) => isFiniteCoord(c[0]) && isFiniteCoord(c[1]));
              if (line.length >= 2) lines.push(line);
            }});
          }}
        }});
        return lines;
      }}

      const trailLines = extractTrailLines();

      function pointSegmentDistanceMeters(lat, lon, lat1, lon1, lat2, lon2) {{
        const meanLat = ((lat + lat1 + lat2) / 3) * Math.PI / 180;
        const metersPerDegLat = 111132.92 - 559.82 * Math.cos(2 * meanLat) + 1.175 * Math.cos(4 * meanLat);
        const metersPerDegLon = 111412.84 * Math.cos(meanLat) - 93.5 * Math.cos(3 * meanLat);
        const x = (lon - lon1) * metersPerDegLon;
        const y = (lat - lat1) * metersPerDegLat;
        const dx = (lon2 - lon1) * metersPerDegLon;
        const dy = (lat2 - lat1) * metersPerDegLat;
        const len2 = dx * dx + dy * dy;
        if (len2 <= 0.0001) return Math.hypot(x, y);
        const t = Math.max(0, Math.min(1, (x * dx + y * dy) / len2));
        const px = x - t * dx;
        const py = y - t * dy;
        return Math.hypot(px, py);
      }}

      function pointTrailDistanceMeters(lat, lon) {{
        let best = Infinity;
        trailLines.forEach((line) => {{
          for (let i = 1; i < line.length; i += 1) {{
            const a = line[i - 1];
            const b = line[i];
            const d = pointSegmentDistanceMeters(lat, lon, a[0], a[1], b[0], b[1]);
            if (d < best) best = d;
          }}
        }});
        return best;
      }}

      function updateDistanceBandCount(sec, cat) {{
        if (!distanceBandToggle.checked) {{
          distanceBandCount.style.display = 'none';
          distanceBandCount.textContent = '';
          return;
        }}
        const bandMeters = normalizeBandMeters(distanceBandMeters.value);
        const selected = filteredPois(sec, cat).filter((r) => isFiniteCoord(r.lat) && isFiniteCoord(r.lon));
        let within = 0;
        selected.forEach((r) => {{
          const d = pointTrailDistanceMeters(r.lat, r.lon);
          if (Number.isFinite(d) && d <= bandMeters) within += 1;
        }});
        distanceBandCount.textContent = t('distanceCount', {{ within, meters: bandMeters }});
        distanceBandCount.style.display = '';
      }}

      function zoomToTrail() {{
        const trailBounds = trailLayer.getBounds();
        if (!trailBounds.isValid()) return;
        preserveMapView = true;
        isProgrammaticMapMove = true;
        map.fitBounds(trailBounds, {{ padding: [20, 20], maxZoom: 11 }});
        map.once('moveend', () => {{
          isProgrammaticMapMove = false;
          saveStateInUrl(sectionFilter.value, categoryFilter.value);
          applyFilters();
        }});
      }}

      function applyFilters() {{
        const sec = sanitizeValue(sectionFilter.value, sectionValues);
        const cat = sanitizeValue(normalizeCategoryValue(categoryFilter.value), categoryValues);
        sectionFilter.value = sec;
        categoryFilter.value = cat;
        const filterChanged = (lastSection !== null && (sec !== lastSection || cat !== lastCategory));
        if (filterChanged) {{
          preserveMapView = false;
        }}
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

        applyLanguage();
        visibleCount.textContent = t('visibleCount', {{ visible, total: totalPoiCount }});
        saveStateInUrl(sec, cat);
        renderMap(sec, cat);
        renderSankey(sec, cat);
        updateDistanceBandCount(sec, cat);
        lastSection = sec;
        lastCategory = cat;
      }}

      sectionFilter.addEventListener('change', applyFilters);
      categoryFilter.addEventListener('change', applyFilters);
      languageFilter.addEventListener('change', applyFilters);
      trailInfoToggle.addEventListener('change', applyFilters);
      distanceBandToggle.addEventListener('change', applyFilters);
      distanceBandMeters.addEventListener('change', applyFilters);
      shareBtn.addEventListener('click', shareCurrentState);
      downloadBtn.addEventListener('click', downloadSelectionJson);
      resetBtn.addEventListener('click', resetFilters);
      zoomTrailBtn.addEventListener('click', zoomToTrail);
      map.on('zoomend', () => {{
        if (!distanceBandToggle.checked) return;
        const prevPreserve = preserveMapView;
        preserveMapView = true;
        renderMap(sectionFilter.value, categoryFilter.value);
        preserveMapView = prevPreserve;
      }});
      map.on('moveend', () => {{
        if (isProgrammaticMapMove) return;
        preserveMapView = true;
        saveStateInUrl(sectionFilter.value, categoryFilter.value);
      }});
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
