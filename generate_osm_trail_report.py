#!/usr/bin/env python3
"""Generate a hierarchical OSM property report for the SAT hiking route."""

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


SUPERROUTE_ID = 19012437
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)
QUERY = f"""[out:json][timeout:300];
relation({SUPERROUTE_ID})->.super;
relation(r.super)->.sections;
(.super;.sections;way(r.sections);node(r.sections););
out body center;"""
USER_AGENT = "sat-sync-trail-report/1.0 (+https://github.com/salgo60/sat-sync)"
JSON_OUTPUT = Path("osm_trail_report.json")
HTML_OUTPUT = Path("sat_osm_trail_report.html")

FEATURE_KEYS = (
    "highway",
    "foot",
    "surface",
    "smoothness",
    "tracktype",
    "sac_scale",
    "trail_visibility",
    "width",
    "incline",
    "lit",
    "access",
    "image",
    "image:license",
    "wikimedia_commons",
    "check_date",
)


def osm_url(osm_type: str, osm_id: int) -> str:
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def wiki_key_url(key: str) -> str:
    return (
        "https://wiki.openstreetmap.org/wiki/Key:"
        + urllib.parse.quote(key, safe=":")
        + "?uselang=sv"
    )


def wiki_tag_url(key: str, value: str) -> str:
    return (
        "https://wiki.openstreetmap.org/wiki/Tag:"
        + urllib.parse.quote(key, safe=":")
        + "%3D"
        + urllib.parse.quote(value, safe="")
        + "?uselang=sv"
    )


def value_url(key: str, value: str) -> str | None:
    value = str(value).strip()
    if value.startswith(("https://", "http://")):
        return value
    if key == "ref:stockholmarchipelagotrail" and value.startswith("sat:"):
        return "https://map.stockholmarchipelagotrail.com/?" + urllib.parse.quote(
            value, safe=":"
        )
    if key == "wikidata" and value.startswith("Q"):
        return "https://www.wikidata.org/wiki/" + urllib.parse.quote(value)
    if key == "wikipedia" and ":" in value:
        language, title = value.split(":", 1)
        return (
            f"https://{urllib.parse.quote(language)}.wikipedia.org/wiki/"
            + urllib.parse.quote(title.replace(" ", "_"))
        )
    if key == "wikimedia_commons" and value.startswith(("Category:", "File:")):
        return "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(value, safe=":")
    if key in {"mapillary", "mapillary:image"} and value.isdigit():
        return "https://www.mapillary.com/app/?pKey=" + value
    return None


def fetch_elements() -> tuple[list[dict], str]:
    payload = urllib.parse.urlencode({"data": QUERY}).encode("utf-8")
    errors: list[str] = []
    for endpoint in OVERPASS_ENDPOINTS:
        request = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=360) as response:
                elements = json.loads(response.read().decode("utf-8")).get(
                    "elements", []
                )
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


def tag_statistics(objects: list[dict]) -> list[dict]:
    key_counts: Counter[str] = Counter()
    value_counts: dict[str, Counter[str]] = {}
    for item in objects:
        for key, value in item.get("tags", {}).items():
            key_counts[key] += 1
            value_counts.setdefault(key, Counter())[str(value)] += 1

    total = len(objects)
    return [
        {
            "key": key,
            "count": count,
            "percent": round(count * 100 / total, 1) if total else 0,
            "wikiUrl": wiki_key_url(key),
            "topValues": [
                {
                    "value": value,
                    "count": value_count,
                    "wikiUrl": wiki_tag_url(key, value),
                    "directUrl": value_url(key, value),
                }
                for value, value_count in value_counts[key].most_common(8)
            ],
        }
        for key, count in sorted(key_counts.items(), key=lambda row: (-row[1], row[0]))
    ]


def serialize_tags(tags: dict) -> list[dict]:
    return [
        {
            "key": key,
            "value": str(value),
            "keyUrl": wiki_key_url(key),
            "valueUrl": value_url(key, value) or wiki_tag_url(key, str(value)),
        }
        for key, value in sorted(tags.items())
    ]


def build_report(elements: list[dict], source: str) -> dict:
    element_index = {
        (element["type"], element["id"]): element for element in elements
    }
    root = element_index.get(("relation", SUPERROUTE_ID))
    if not root:
        raise ValueError(f"OSM-relation {SUPERROUTE_ID} saknas i svaret")

    section_refs = [
        member["ref"]
        for member in root.get("members", [])
        if member.get("type") == "relation"
    ]
    sections: list[dict] = []
    segment_sections: dict[tuple[str, int], list[int]] = {}

    for order, section_id in enumerate(section_refs, start=1):
        relation = element_index.get(("relation", section_id))
        if not relation:
            continue
        tags = relation.get("tags") or {}
        members = [
            member
            for member in relation.get("members", [])
            if member.get("type") in {"way", "node"}
        ]
        segment_objects = []
        for member in members:
            key = (member["type"], member["ref"])
            segment_sections.setdefault(key, []).append(section_id)
            element = element_index.get(key)
            if element:
                segment_objects.append(
                    {
                        "osmType": element["type"],
                        "osmId": element["id"],
                        "osmUrl": osm_url(element["type"], element["id"]),
                        "role": member.get("role", ""),
                        "tags": dict(sorted((element.get("tags") or {}).items())),
                    }
                )

        feature_coverage = {}
        for key in FEATURE_KEYS:
            count = sum(1 for item in segment_objects if item["tags"].get(key))
            feature_coverage[key] = {
                "count": count,
                "percent": round(count * 100 / len(segment_objects), 1)
                if segment_objects
                else 0,
            }

        sections.append(
            {
                "order": order,
                "osmId": section_id,
                "osmUrl": osm_url("relation", section_id),
                "name": tags.get("name") or f"Relation {section_id}",
                "satRef": tags.get("ref:stockholmarchipelagotrail", ""),
                "distance": tags.get("distance", ""),
                "memberCount": len(members),
                "wayCount": sum(1 for member in members if member["type"] == "way"),
                "nodeCount": sum(1 for member in members if member["type"] == "node"),
                "tags": serialize_tags(tags),
                "featureCoverage": feature_coverage,
                "tagStats": tag_statistics(segment_objects),
                "members": segment_objects,
            }
        )

    unique_segments = []
    for key, section_ids in segment_sections.items():
        element = element_index.get(key)
        if not element:
            continue
        unique_segments.append(
            {
                "osmType": element["type"],
                "osmId": element["id"],
                "osmUrl": osm_url(element["type"], element["id"]),
                "sections": section_ids,
                "tags": dict(sorted((element.get("tags") or {}).items())),
            }
        )

    total_memberships = sum(section["memberCount"] for section in sections)
    return {
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "source": source,
        "query": QUERY,
        "overpassTurboUrl": "https://overpass-turbo.eu/?Q="
        + urllib.parse.quote(QUERY, safe=""),
        "superroute": {
            "osmId": SUPERROUTE_ID,
            "osmUrl": osm_url("relation", SUPERROUTE_ID),
            "name": (root.get("tags") or {}).get("name", ""),
            "memberCount": len(section_refs),
            "tags": serialize_tags(root.get("tags") or {}),
        },
        "sectionCount": len(sections),
        "totalMemberships": total_memberships,
        "uniqueSegmentCount": len(unique_segments),
        "duplicateMemberships": total_memberships - len(unique_segments),
        "segmentTypes": dict(Counter(item["osmType"] for item in unique_segments)),
        "featureKeys": list(FEATURE_KEYS),
        "tagStats": tag_statistics(unique_segments),
        "sections": sections,
        "segments": unique_segments,
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
  <title>OSM-egenskaper på Stockholm Archipelago Trail</title>
  <style>
    :root {{ --blue:#245b8e; --deep:#173f67; --light:#eef5fb; --line:#d9e2ea; --text:#18222c; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:#f6f8fa; color:var(--text); font-family:system-ui,-apple-system,sans-serif; }}
    header {{ background:linear-gradient(120deg,var(--deep),#3278b6); color:white; padding:2rem max(1rem,calc((100vw - 1200px)/2)); }}
    header h1 {{ margin:0 0 .4rem; font-size:clamp(1.55rem,3vw,2.35rem); }}
    header p {{ margin:.25rem 0; max-width:900px; }}
    header a {{ color:white; }}
    main {{ max-width:1200px; margin:1.5rem auto; padding:0 1rem 3rem; }}
    a {{ color:#1264a3; }}
    code {{ background:#eef1f4; border-radius:4px; padding:.08rem .25rem; }}
    .meta {{ font-size:.85rem; opacity:.88; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.75rem; margin-bottom:1.25rem; }}
    .card,.panel {{ background:white; border:1px solid var(--line); border-radius:10px; box-shadow:0 1px 3px #0001; }}
    .card {{ padding:1rem; }}
    .card strong {{ display:block; color:var(--blue); font-size:1.65rem; }}
    .panel {{ margin-bottom:1rem; padding:1rem; }}
    .infographic {{ display:flex; align-items:center; gap:1rem; padding:.8rem; }}
    .infographic img {{ display:block; width:360px; max-width:38vw; height:auto; border-radius:7px; }}
    .infographic figcaption {{ line-height:1.45; }}
    .infographic strong {{ display:block; color:var(--blue); margin-bottom:.2rem; }}
    .infographic small {{ color:#65717c; }}
    h2 {{ color:var(--blue); font-size:1.25rem; margin:.2rem 0 .8rem; }}
    h3 {{ color:var(--deep); }}
    .hierarchy {{ display:grid; grid-template-columns:minmax(230px,.8fr) 2fr; gap:1rem; }}
    .relation {{ background:var(--light); border-left:5px solid var(--blue); padding:.8rem; border-radius:7px; }}
    .section-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(225px,1fr)); gap:.55rem; }}
    .section-card {{ border:1px solid var(--line); border-radius:7px; padding:.65rem; cursor:pointer; background:white; }}
    .section-card:hover {{ border-color:var(--blue); background:#f8fbfe; }}
    .section-card strong {{ display:block; }}
    .section-card small {{ color:#66727d; }}
    .toolbar {{ display:flex; gap:.7rem; flex-wrap:wrap; align-items:center; }}
    select,input {{ min-height:40px; padding:.5rem .7rem; border:1px solid #b9c5d0; border-radius:6px; background:white; font:inherit; }}
    input {{ flex:1; min-width:230px; }}
    .table-wrap {{ overflow:auto; }}
    table {{ width:100%; border-collapse:collapse; font-size:.86rem; }}
    th,td {{ padding:.45rem .55rem; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ background:#f2f5f7; position:sticky; top:0; }}
    .num {{ text-align:right; white-space:nowrap; }}
    .tag-value {{ display:inline-block; margin:.08rem .15rem .08rem 0; }}
    details {{ margin-top:.75rem; }}
    summary {{ cursor:pointer; font-weight:650; }}
    .coverage {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(155px,1fr)); gap:.45rem; margin:.75rem 0; }}
    .coverage div {{ padding:.45rem .55rem; background:#f5f8fa; border-radius:6px; }}
    .coverage strong {{ float:right; color:var(--blue); }}
    @media(max-width:720px) {{
      .infographic {{ display:block; }}
      .infographic img {{ width:100%; max-width:none; margin-bottom:.7rem; }}
      .hierarchy {{ grid-template-columns:1fr; }}
      th:nth-child(4),td:nth-child(4) {{ display:none; }}
    }}
  </style>
</head>
<body>
<header>
  <h1>🥾 OSM-egenskaper på Stockholm Archipelago Trail</h1>
  <p>Från superrelationen via 20 etapprelationer till de vägar och noder som leden faktiskt följer.</p>
  <p class="meta"><a href="sat_poi_dashboard.html">← SAT POI Dashboard</a> · <a href="sat_osm_ref_report.html">POI-egenskaper</a> · <a href="sat_about.html?lang=sv">Om verktygen</a> · Genererad {generated} · <a href="{query_url}" target="_blank" rel="noopener">Overpass-fråga</a></p>
</header>
<main>
  <figure class="panel infographic">
    <a href="assets/sat-osm-trail-infographic.jpg" target="_blank">
      <img src="assets/sat-osm-trail-infographic.jpg" alt="Infografik över hur Stockholm Archipelago Trail beskrivs i OpenStreetMap" width="1536" height="1024">
    </a>
    <figcaption>
      <strong>Från relation till ledens vägar och platser</strong>
      Infografiken visar hur SAT byggs upp i OSM med en superrelation, 20 etapprelationer och deras vägar, stigar och platser.
      <small>Klicka på bilden för att öppna den i full storlek.</small>
    </figcaption>
  </figure>
  <figure class="panel infographic">
    <a href="assets/sat-osm-experience-infographic.jpg" target="_blank">
      <img src="assets/sat-osm-experience-infographic.jpg" alt="Infografik över hur SAT förädlar OSM-data till information och tjänster för vandrare" width="1536" height="1024">
    </a>
    <figcaption>
      <strong>Från OSM-data till planering och upplevelser</strong>
      Infografiken visar vägen från detaljerad OSM-data via SAT:s sammanställning och API till tjänster som hjälper vandraren att planera.
      <small>Klicka på bilden för att öppna den i full storlek.</small>
    </figcaption>
  </figure>
  <div id="summary" class="cards"></div>
  <section class="panel">
    <h2>Leden som OSM-hierarki</h2>
    <div class="hierarchy">
      <div id="superroute" class="relation"></div>
      <div id="sectionGrid" class="section-grid"></div>
    </div>
  </section>
  <section class="panel">
    <h2>Etapp och egenskaper</h2>
    <div class="toolbar">
      <select id="sectionSelect"><option value="all">Hela leden — unika segment</option></select>
      <input id="tagSearch" type="search" placeholder="Sök OSM-nyckel eller värde…">
    </div>
    <div id="selectionMeta"></div>
    <div id="coverage"></div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>OSM-nyckel</th><th class="num">Antal</th><th class="num">Andel</th><th>Vanligaste värden</th></tr></thead>
        <tbody id="statsBody"></tbody>
      </table>
    </div>
    <details id="membersDetails">
      <summary id="membersSummary">Visa ledobjekt</summary>
      <div class="table-wrap">
        <table>
          <thead><tr><th>OSM-objekt</th><th>Huvudtyp</th><th>Etapper</th><th>Utvalda egenskaper</th></tr></thead>
          <tbody id="membersBody"></tbody>
        </table>
      </div>
    </details>
  </section>
</main>
<script>
const REPORT={embedded};
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const sectionById=Object.fromEntries(REPORT.sections.map(s=>[String(s.osmId),s]));
const keyUrl=key=>`https://wiki.openstreetmap.org/wiki/Key:${{encodeURIComponent(key).replaceAll('%3A',':')}}?uselang=sv`;
const tagUrl=(key,value)=>`https://wiki.openstreetmap.org/wiki/Tag:${{encodeURIComponent(key).replaceAll('%3A',':')}}%3D${{encodeURIComponent(value)}}?uselang=sv`;
function nativeUrl(key,value) {{
  value=String(value||'');
  if(value.startsWith('http://')||value.startsWith('https://'))return value;
  if(key==='wikidata'&&/^Q\\d+$/.test(value))return `https://www.wikidata.org/wiki/${{value}}`;
  if(key==='wikimedia_commons'&&/^(Category|File):/.test(value))return `https://commons.wikimedia.org/wiki/${{encodeURIComponent(value).replaceAll('%3A',':')}}`;
  if(key==='wikipedia'&&value.includes(':')){{const [lang,...title]=value.split(':');return `https://${{lang}}.wikipedia.org/wiki/${{encodeURIComponent(title.join(':').replaceAll(' ','_'))}}`;}}
  if(key==='ref:stockholmarchipelagotrail'&&value.startsWith('sat:'))return `https://map.stockholmarchipelagotrail.com/?${{encodeURIComponent(value).replaceAll('%3A',':')}}`;
  return '';
}}
function linkValue(key,value,count='') {{
  const href=nativeUrl(key,value)||tagUrl(key,value);
  return `<span class="tag-value"><a href="${{href}}" target="_blank" rel="noopener"><code>${{esc(value)}}</code></a>${{count!==''?' '+count:''}}</span>`;
}}
function tagList(tags) {{
  return tags.map(tag=>`<div><a href="${{tag.keyUrl}}" target="_blank"><code>${{esc(tag.key)}}</code></a> = <a href="${{tag.valueUrl}}" target="_blank"><code>${{esc(tag.value)}}</code></a></div>`).join('');
}}
document.getElementById('summary').innerHTML=[
  ['Superrelation',REPORT.superroute.osmId],
  ['Etapprelationer',REPORT.sectionCount],
  ['Unika ledobjekt',REPORT.uniqueSegmentCount],
  ['Medlemskap',REPORT.totalMemberships],
  ['Återanvända segment',REPORT.duplicateMemberships],
].map(([label,value])=>`<div class="card"><strong>${{value}}</strong>${{label}}</div>`).join('');
document.getElementById('superroute').innerHTML=`<strong><a href="${{REPORT.superroute.osmUrl}}" target="_blank">${{esc(REPORT.superroute.name)}}</a></strong><p>relation/${{REPORT.superroute.osmId}} · ${{REPORT.superroute.memberCount}} etapper</p><details><summary>Visa relationens taggar</summary>${{tagList(REPORT.superroute.tags)}}</details>`;
document.getElementById('sectionGrid').innerHTML=REPORT.sections.map(s=>`<div class="section-card" data-id="${{s.osmId}}"><strong>${{s.order}}. ${{esc(s.name.replace(/^SAT Etapp /,''))}}</strong><small>${{esc(s.distance||'okänd längd')}} · ${{s.memberCount}} medlemmar · relation/${{s.osmId}}</small></div>`).join('');
const select=document.getElementById('sectionSelect');
select.innerHTML+=REPORT.sections.map(s=>`<option value="${{s.osmId}}">${{s.order}}. ${{esc(s.name.replace(/^SAT Etapp /,''))}} (${{s.memberCount}})</option>`).join('');
function compactTags(tags) {{
  const preferred=['highway','surface','smoothness','sac_scale','trail_visibility','foot','width','image'];
  return preferred.filter(k=>tags[k]).map(k=>`<span class="tag-value"><a href="${{keyUrl(k)}}" target="_blank"><code>${{esc(k)}}</code></a>=${{linkValue(k,tags[k])}}</span>`).join(' ');
}}
function render() {{
  const section=select.value==='all'?null:sectionById[select.value];
  const stats=section?section.tagStats:REPORT.tagStats;
  const members=section?section.members:REPORT.segments;
  const query=document.getElementById('tagSearch').value.trim().toLowerCase();
  const filteredStats=stats.filter(stat=>!query||stat.key.toLowerCase().includes(query)||stat.topValues.some(v=>v.value.toLowerCase().includes(query)));
  document.getElementById('selectionMeta').innerHTML=section
    ? `<h3><a href="${{section.osmUrl}}" target="_blank">${{esc(section.name)}}</a></h3><p>${{esc(section.distance||'Längd saknas')}} · ${{section.wayCount}} vägar · ${{section.nodeCount}} noder · <code>${{esc(section.satRef)}}</code></p><details><summary>Visa etapprelationens taggar</summary>${{tagList(section.tags)}}</details>`
    : `<h3>Hela SAT-leden</h3><p>${{REPORT.uniqueSegmentCount}} unika ledobjekt. ${{REPORT.duplicateMemberships}} medlemskap är segment som används i mer än en etapp.</p>`;
  const coverage=section?section.featureCoverage:Object.fromEntries(REPORT.featureKeys.map(key=>{{const stat=REPORT.tagStats.find(s=>s.key===key);return [key,{{count:stat?.count||0,percent:stat?.percent||0}}];}}));
  document.getElementById('coverage').innerHTML='<div class="coverage">'+REPORT.featureKeys.map(key=>`<div><a href="${{keyUrl(key)}}" target="_blank"><code>${{esc(key)}}</code></a><strong>${{coverage[key].percent}}%</strong></div>`).join('')+'</div>';
  document.getElementById('statsBody').innerHTML=filteredStats.map(stat=>`<tr><td><a href="${{stat.wikiUrl}}" target="_blank"><code>${{esc(stat.key)}}</code></a></td><td class="num">${{stat.count}}</td><td class="num">${{stat.percent}}%</td><td>${{stat.topValues.map(v=>linkValue(stat.key,v.value,v.count)).join(' · ')}}</td></tr>`).join('');
  document.getElementById('membersSummary').textContent=`Visa ledobjekt (${{members.length}})`;
  document.getElementById('membersBody').innerHTML=members.map(member=>{{
    const sectionNames=(member.sections||[section?.osmId]).filter(Boolean).map(id=>sectionById[String(id)]?.name.replace(/^SAT Etapp /,'')||id).join(', ');
    const mainType=member.tags.highway?`highway=${{member.tags.highway}}`:(member.tags.amenity?`amenity=${{member.tags.amenity}}`:'—');
    return `<tr><td><a href="${{member.osmUrl}}" target="_blank">${{member.osmType}}/${{member.osmId}}</a></td><td>${{esc(mainType)}}</td><td>${{esc(sectionNames)}}</td><td>${{compactTags(member.tags)}}</td></tr>`;
  }}).join('');
}}
select.addEventListener('change',render);
document.getElementById('tagSearch').addEventListener('input',render);
document.querySelectorAll('.section-card').forEach(card=>card.addEventListener('click',()=>{{select.value=card.dataset.id;render();document.getElementById('sectionSelect').scrollIntoView({{behavior:'smooth',block:'center'}});}}));
render();
</script>
</body>
</html>
"""


def main() -> None:
    print(f"Hämtar SAT-ledens OSM-hierarki från relation {SUPERROUTE_ID}...")
    elements, source = fetch_elements()
    report = build_report(elements, source)
    JSON_OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    HTML_OUTPUT.write_text(render_report(report), encoding="utf-8")
    print(
        f"Klart: {report['sectionCount']} etapper, "
        f"{report['uniqueSegmentCount']} unika ledobjekt -> {HTML_OUTPUT}"
    )


if __name__ == "__main__":
    main()
