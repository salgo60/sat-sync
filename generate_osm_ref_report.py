#!/usr/bin/env python3
"""Generate a categorized report for every OSM object carrying the SAT ref tag."""

from __future__ import annotations

import html
import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


REF_KEY = "ref:stockholmarchipelagotrail"
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.nchc.org.tw/api/interpreter",
)
QUERY = f'[out:json][timeout:180];nwr["{REF_KEY}"];out tags center;'
USER_AGENT = "sat-sync-osm-report/1.0 (+https://github.com/salgo60/sat-sync)"
JSON_OUTPUT = Path("osm_ref_report.json")
HTML_OUTPUT = Path("sat_osm_ref_report.html")


CATEGORY_ORDER = (
    "Vindskydd",
    "Toalett",
    "Grillplats",
    "Dricksvatten",
    "Tältplats",
    "Boende",
    "Handla mat",
    "Museum",
    "Restaurang / café",
    "Utsiktspunkt",
    "Färjeläge",
    "Bastu",
    "Dusch",
    "Badplats",
    "Hamn",
    "Uthyrning",
    "Fyr",
    "Hjärtstartare",
    "Turism / sevärdhet",
    "Kyrka / kultur",
    "Aktivitet",
    "Ö / naturplats",
    "Butik övrig",
    "Service",
    "Byggnad / plats",
    "Led / rutt",
    "Övrigt",
)

LODGING_VALUES = {
    "alpine_hut",
    "apartment",
    "camping",
    "chalet",
    "guest_house",
    "holiday_village",
    "hostel",
    "hotel",
    "motel",
    "wilderness_hut",
}
FOOD_SHOP_VALUES = {
    "bakery",
    "convenience",
    "deli",
    "farm",
    "food",
    "general",
    "greengrocer",
    "kiosk",
    "seafood",
    "supermarket",
}
FOOD_AMENITY_VALUES = {"bar", "cafe", "fast_food", "food_court", "pub", "restaurant"}
RENTAL_AMENITY_VALUES = {
    "bicycle_rental",
    "boat_rental",
    "boat_sharing",
    "motorcycle_rental",
}
WATER_AMENITY_VALUES = {"drinking_water", "water_point", "dricksvatten"}


def fetch_osm_elements() -> tuple[list[dict], str]:
    """Fetch all matching OSM elements globally, with endpoint fallback."""
    payload = urllib.parse.urlencode({"data": QUERY}).encode("utf-8")
    errors: list[str] = []

    for endpoint in OVERPASS_ENDPOINTS:
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=240) as response:
                data = json.loads(response.read().decode("utf-8"))
            elements = data.get("elements", [])
            if not elements:
                errors.append(f"{endpoint}: tomt resultat")
                continue
            return elements, endpoint
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            json.JSONDecodeError,
        ) as error:
            errors.append(f"{endpoint}: {error}")

    raise RuntimeError("Ingen Overpass-endpoint svarade: " + "; ".join(errors))


def classify(tags: dict[str, str]) -> str:
    """Assign one primary, human-oriented category based on OSM tags."""
    amenity = tags.get("amenity", "")
    tourism = tags.get("tourism", "")
    leisure = tags.get("leisure", "")
    man_made = tags.get("man_made", "")
    public_transport = tags.get("public_transport", "")

    if amenity == "ferry_terminal" or (
        tags.get("ferry") == "yes"
        and public_transport in {"platform", "station", "stop_position"}
    ):
        return "Färjeläge"
    if amenity == "shelter" or tourism in {"alpine_hut", "wilderness_hut"}:
        return "Vindskydd"
    if amenity == "toilets":
        return "Toalett"
    if amenity == "bbq" or leisure == "firepit":
        return "Grillplats"
    if (
        amenity in WATER_AMENITY_VALUES
        or man_made in {"water_tap", "water_well"}
        and tags.get("drinking_water") != "no"
    ):
        return "Dricksvatten"
    if tourism in {"camp_pitch", "camp_site"}:
        return "Tältplats"
    if tourism in LODGING_VALUES:
        return "Boende"
    if tags.get("shop") in FOOD_SHOP_VALUES:
        return "Handla mat"
    if tourism == "museum" or "museum" in tags:
        return "Museum"
    if amenity in FOOD_AMENITY_VALUES:
        return "Restaurang / café"
    if tourism == "viewpoint":
        return "Utsiktspunkt"
    if leisure == "sauna" or amenity == "sauna":
        return "Bastu"
    if amenity == "shower":
        return "Dusch"
    if tags.get("natural") == "beach" or leisure in {"bathing_place", "swimming_area"}:
        return "Badplats"
    if leisure == "marina" or man_made in {"breakwater", "pier"}:
        return "Hamn"
    if amenity in RENTAL_AMENITY_VALUES or any(
        key.endswith("_rental") and value not in {"", "no"}
        for key, value in tags.items()
    ):
        return "Uthyrning"
    if man_made == "lighthouse" or tags.get("building") == "lighthouse":
        return "Fyr"
    if tags.get("emergency") == "defibrillator":
        return "Hjärtstartare"
    if tourism or tags.get("historic") or tags.get("attraction"):
        return "Turism / sevärdhet"
    if (
        amenity in {"cinema", "place_of_worship"}
        or tags.get("memorial")
        or tags.get("cemetery")
    ):
        return "Kyrka / kultur"
    if leisure:
        return "Aktivitet"
    if tags.get("place") or tags.get("natural"):
        return "Ö / naturplats"
    if tags.get("shop"):
        return "Butik övrig"
    if amenity:
        return "Service"
    if tags.get("route") or tags.get("highway"):
        return "Led / rutt"
    if tags.get("building"):
        return "Byggnad / plats"
    return "Övrigt"


def element_coordinates(element: dict) -> tuple[float | None, float | None]:
    if element.get("type") == "node":
        return element.get("lat"), element.get("lon")
    center = element.get("center") or {}
    return center.get("lat"), center.get("lon")


def wiki_key_url(key: str) -> str:
    return "https://wiki.openstreetmap.org/wiki/Key:" + urllib.parse.quote(key, safe=":")


def wiki_tag_url(key: str, value: str) -> str:
    return (
        "https://wiki.openstreetmap.org/wiki/Tag:"
        + urllib.parse.quote(key, safe=":")
        + "%3D"
        + urllib.parse.quote(value, safe="")
    )


def osm_url(osm_type: str, osm_id: int) -> str:
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def build_report(elements: list[dict], source: str) -> dict:
    objects: list[dict] = []
    for element in elements:
        tags = element.get("tags") or {}
        lat, lon = element_coordinates(element)
        objects.append(
            {
                "osmType": element["type"],
                "osmId": element["id"],
                "osmUrl": osm_url(element["type"], element["id"]),
                "name": tags.get("name") or tags.get("name:sv") or "(namnlös)",
                "satRef": tags.get(REF_KEY, ""),
                "category": classify(tags),
                "lat": lat,
                "lon": lon,
                "tags": dict(sorted(tags.items())),
            }
        )

    category_counts = Counter(item["category"] for item in objects)
    categories = []
    for category in CATEGORY_ORDER:
        category_objects = [item for item in objects if item["category"] == category]
        if not category_objects:
            continue

        key_counts: Counter[str] = Counter()
        value_counts: dict[str, Counter[str]] = {}
        for item in category_objects:
            for key, value in item["tags"].items():
                key_counts[key] += 1
                value_counts.setdefault(key, Counter())[str(value)] += 1

        tag_stats = []
        for key, count in sorted(key_counts.items(), key=lambda row: (-row[1], row[0])):
            top_values = [
                {"value": value, "count": value_count, "wikiUrl": wiki_tag_url(key, value)}
                for value, value_count in value_counts[key].most_common(5)
            ]
            tag_stats.append(
                {
                    "key": key,
                    "count": count,
                    "percent": round(count * 100 / len(category_objects), 1),
                    "wikiUrl": wiki_key_url(key),
                    "topValues": top_values,
                }
            )

        categories.append(
            {
                "name": category,
                "count": len(category_objects),
                "tagStats": tag_stats,
            }
        )

    return {
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": source,
        "query": QUERY,
        "overpassTurboUrl": "https://overpass-turbo.eu/?Q="
        + urllib.parse.quote(QUERY, safe=""),
        "refKey": REF_KEY,
        "totalObjects": len(objects),
        "osmTypes": dict(Counter(item["osmType"] for item in objects)),
        "categoryCounts": {
            category: category_counts[category]
            for category in CATEGORY_ORDER
            if category_counts[category]
        },
        "categories": categories,
        "objects": sorted(
            objects,
            key=lambda item: (
                CATEGORY_ORDER.index(item["category"]),
                item["name"].casefold(),
                item["osmType"],
                item["osmId"],
            ),
        ),
    }


def render_report(report: dict) -> str:
    embedded = json.dumps(report, ensure_ascii=False).replace("</", "<\\/")
    generated = html.escape(report["generatedAt"].replace("T", " ").replace("Z", " UTC"))
    query_url = html.escape(report["overpassTurboUrl"], quote=True)
    return f"""<!doctype html>
<html lang="sv">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OSM-objekt längs Stockholm Archipelago Trail</title>
  <style>
    :root {{ --blue:#245b8e; --light:#eef5fb; --line:#d9e2ea; --text:#18222c; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#f6f8fa; color:var(--text); font-family:system-ui,-apple-system,sans-serif; }}
    header {{ background:linear-gradient(120deg,#173f67,#3278b6); color:white; padding:2rem max(1rem,calc((100vw - 1200px)/2)); }}
    header h1 {{ margin:0 0 .4rem; font-size:clamp(1.5rem,3vw,2.3rem); }}
    header p {{ margin:.25rem 0; max-width:850px; }}
    main {{ max-width:1200px; margin:1.5rem auto; padding:0 1rem 3rem; }}
    a {{ color:#1264a3; }}
    .meta {{ font-size:.85rem; opacity:.85; }}
    .summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.75rem; margin-bottom:1.25rem; }}
    .card,.panel {{ background:white; border:1px solid var(--line); border-radius:10px; box-shadow:0 1px 3px #0001; }}
    .card {{ padding:1rem; }}
    .card strong {{ display:block; font-size:1.65rem; color:var(--blue); }}
    .toolbar {{ display:flex; gap:.7rem; flex-wrap:wrap; padding:1rem; margin-bottom:1rem; }}
    input,select {{ min-height:40px; padding:.5rem .7rem; border:1px solid #b9c5d0; border-radius:6px; background:white; font:inherit; }}
    input {{ flex:1; min-width:240px; }}
    .category-nav {{ display:flex; flex-wrap:wrap; gap:.45rem; margin:1rem 0; }}
    .category-nav a {{ background:var(--light); border-radius:999px; padding:.35rem .7rem; text-decoration:none; font-size:.86rem; }}
    section {{ margin:1.4rem 0; scroll-margin-top:1rem; }}
    section h2 {{ color:var(--blue); margin:.2rem 0 .7rem; }}
    details {{ margin:.5rem 0; }}
    summary {{ cursor:pointer; font-weight:650; }}
    .table-wrap {{ overflow:auto; }}
    table {{ border-collapse:collapse; width:100%; font-size:.86rem; }}
    th,td {{ border-bottom:1px solid var(--line); padding:.45rem .55rem; text-align:left; vertical-align:top; }}
    th {{ background:#f2f5f7; position:sticky; top:0; }}
    td.num,th.num {{ text-align:right; white-space:nowrap; }}
    code {{ background:#eef1f4; border-radius:4px; padding:.08rem .25rem; }}
    .values {{ color:#52606b; font-size:.8rem; }}
    .object-tags {{ max-width:620px; white-space:normal; }}
    .tag {{ display:inline-block; margin:.08rem; padding:.12rem .3rem; background:#f0f4f7; border-radius:4px; }}
    .hidden {{ display:none !important; }}
    @media(max-width:650px) {{ th:nth-child(4),td:nth-child(4) {{ display:none; }} }}
  </style>
</head>
<body>
<header>
  <h1>OSM-objekt med <code>{html.escape(REF_KEY)}</code></h1>
  <p>Alla noder, vägar och relationer grupperade efter funktion. Taggstatistiken visar hur många objekt i varje grupp som har respektive egenskap.</p>
  <p class="meta">Genererad {generated} · <a style="color:white" href="{query_url}" target="_blank" rel="noopener">Global Overpass-fråga</a> · Nycklar och värden länkar till OSM Wiki</p>
</header>
<main>
  <div id="summary" class="summary"></div>
  <div class="panel toolbar">
    <input id="search" type="search" placeholder="Sök namn, SAT-ref, OSM-tagg eller värde…">
    <select id="category"><option value="">Alla kategorier</option></select>
  </div>
  <nav id="categoryNav" class="category-nav"></nav>
  <div id="categories"></div>
</main>
<script>
const REPORT={embedded};
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const slug=value=>'cat-'+value.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').replace(/[^a-z0-9]+/g,'-');
const objectsByCategory=Object.groupBy
  ? Object.groupBy(REPORT.objects,o=>o.category)
  : REPORT.objects.reduce((a,o)=>((a[o.category]??=[]).push(o),a),{{}});

document.getElementById('summary').innerHTML=[
  ['OSM-objekt',REPORT.totalObjects],
  ['Noder',REPORT.osmTypes.node||0],
  ['Vägar',REPORT.osmTypes.way||0],
  ['Relationer',REPORT.osmTypes.relation||0],
  ['Kategorier',REPORT.categories.length],
].map(([label,value])=>`<div class="card"><strong>${{value}}</strong>${{label}}</div>`).join('');

const categorySelect=document.getElementById('category');
categorySelect.innerHTML+=REPORT.categories.map(c=>`<option value="${{esc(c.name)}}">${{esc(c.name)}} (${{c.count}})</option>`).join('');
document.getElementById('categoryNav').innerHTML=REPORT.categories.map(c=>`<a href="#${{slug(c.name)}}">${{esc(c.name)}} · ${{c.count}}</a>`).join('');

function valuesHtml(stat) {{
  return stat.topValues.map(v=>`<a href="${{v.wikiUrl}}" target="_blank" rel="noopener"><code>${{esc(v.value)}}</code></a> ${{v.count}}`).join(' · ');
}}
function tagsHtml(tags) {{
  return Object.entries(tags).map(([k,v])=>`<span class="tag"><a href="https://wiki.openstreetmap.org/wiki/Key:${{encodeURIComponent(k).replaceAll('%3A',':')}}" target="_blank">${{esc(k)}}</a>=${{esc(v)}}</span>`).join(' ');
}}
function render() {{
  const q=document.getElementById('search').value.trim().toLowerCase();
  const selected=categorySelect.value;
  const sections=REPORT.categories.map(category=>{{
    if(selected&&selected!==category.name)return '';
    const objects=(objectsByCategory[category.name]||[]).filter(o=>!q||JSON.stringify(o).toLowerCase().includes(q));
    if(q&&!objects.length)return '';
    const stats=category.tagStats;
    const statRows=stats.map(stat=>`<tr><td><a href="${{stat.wikiUrl}}" target="_blank" rel="noopener"><code>${{esc(stat.key)}}</code></a></td><td class="num">${{stat.count}}</td><td class="num">${{stat.percent}}%</td><td class="values">${{valuesHtml(stat)}}</td></tr>`).join('');
    const objectRows=objects.map(o=>`<tr><td><a href="${{o.osmUrl}}" target="_blank" rel="noopener">${{esc(o.name)}}</a></td><td><code>${{esc(o.satRef)}}</code></td><td>${{o.osmType}}/${{o.osmId}}</td><td class="object-tags">${{tagsHtml(o.tags)}}</td></tr>`).join('');
    return `<section id="${{slug(category.name)}}"><h2>${{esc(category.name)}} <small>(${{objects.length}}${{q?' filtrerade':''}})</small></h2>
      <div class="panel"><details open><summary style="padding:.8rem">Egenskaper och täckning</summary><div class="table-wrap"><table><thead><tr><th>OSM-nyckel</th><th class="num">Antal</th><th class="num">Andel</th><th>Vanligaste värden</th></tr></thead><tbody>${{statRows}}</tbody></table></div></details></div>
      <div class="panel"><details><summary style="padding:.8rem">Visa alla objekt (${{objects.length}})</summary><div class="table-wrap"><table><thead><tr><th>Namn / OSM</th><th>SAT-ref</th><th>Typ/ID</th><th>Alla taggar</th></tr></thead><tbody>${{objectRows}}</tbody></table></div></details></div>
    </section>`;
  }}).join('');
  document.getElementById('categories').innerHTML=sections||'<p>Inga objekt matchar filtret.</p>';
}}
document.getElementById('search').addEventListener('input',render);
categorySelect.addEventListener('change',render);
render();
</script>
</body>
</html>
"""


def main() -> None:
    print(f"Hämtar alla OSM-objekt med {REF_KEY}...")
    elements, source = fetch_osm_elements()
    report = build_report(elements, source)
    JSON_OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    HTML_OUTPUT.write_text(render_report(report), encoding="utf-8")
    print(
        f"Klart: {report['totalObjects']} objekt i {len(report['categories'])} kategorier "
        f"-> {HTML_OUTPUT}"
    )


if __name__ == "__main__":
    main()
