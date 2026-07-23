#!/usr/bin/env python3
"""
Generera HTML-rapport med ENBART problematiska SAT POI-poster:
- Saknar backreferens (P14545 / ref:stockholmarchipelagotrail)
- Borttagna objekt i OSM eller Wikidata

Batch-hämtning för grunddata; per-objekt-kontroll only för problem-poster (~100 st).
"""

import json
import argparse
import urllib.request
import urllib.error
from urllib.parse import urlencode
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class IssueRecord:
    external_id: str
    sat_id: str
    source_type: str            # "osm" | "wikidata"
    name: Optional[str] = None
    updated_at: Optional[str] = None
    first_seen: Optional[str] = None
    section: Optional[str] = None
    # Wikidata
    wikidata_q: Optional[str] = None
    wikidata_label: Optional[str] = None
    wikidata_p14545_ok: Optional[bool] = None
    wikidata_p14545_value: Optional[str] = None
    wikidata_deleted: bool = False
    # OSM
    osm_type: Optional[str] = None
    osm_numeric_id: Optional[int] = None
    osm_ref_ok: Optional[bool] = None
    osm_ref_value: Optional[str] = None
    osm_deleted: bool = False

    @property
    def is_deleted(self):
        return self.osm_deleted or self.wikidata_deleted

    @property
    def issue_type(self):
        if self.is_deleted:
            return "deleted"
        return "missing_ref"


class IssuesReportGenerator:
    CONCORDANCE_URL = "https://map.stockholmarchipelagotrail.com/data/geojson/poi-concordance.json"
    POIS_URL        = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
    WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
    WIKIDATA_API    = "https://www.wikidata.org/w/api.php"
    POSTPASS_URL    = "https://postpass.geofabrik.de/api/interpreter"
    OSM_API         = "https://www.openstreetmap.org/api/0.6"

    def __init__(self, email="salgo60@msn.com"):
        self.email = email
        self.headers = {
            "User-Agent": f"SAT-Sync/1.0 (+https://stockholmarchipelagotrail.com; {email})",
            "Accept": "application/json",
        }

    def _get_json(self, url):
        req = urllib.request.Request(url, headers=self.headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))

    def _http_status(self, url):
        """Returnerar HTTP-statuskod utan att kasta exception."""
        try:
            req = urllib.request.Request(url, headers=self.headers, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Batch-hämtning
    # ------------------------------------------------------------------
    def fetch_concordance(self):
        print("📥 Hämtar poi-concordance.json...")
        data = self._get_json(self.CONCORDANCE_URL)
        items = data.get("satIdOf", {})
        print(f"  ✅ {len(items)} poster")
        return items

    def fetch_pois_metadata(self):
        print("📥 Hämtar pois.geojson metadata...")
        data = self._get_json(self.POIS_URL)
        meta = {}
        for feat in data.get("features", []):
            p = feat.get("properties", {})
            sid = p.get("id")
            if sid:
                meta[sid] = {
                    "updated_at": p.get("updatedAt"),
                    "first_seen": p.get("firstSeen"),
                    "name":       p.get("name"),
                    "section":    p.get("section"),
                }
        print(f"  ✅ Metadata för {len(meta)} POI:er")
        return meta

    def fetch_wikidata_p14545_all(self):
        print("📥 Hämtar Wikidata P14545 (SPARQL batch)...")
        query = """
SELECT ?item ?itemLabel ?value WHERE {
 ?item wdt:P14545 ?value .
 SERVICE wikibase:label { bd:serviceParam wikibase:language "sv,mul,en". }
}"""
        url = f"{self.WIKIDATA_SPARQL}?{urlencode({'query': query, 'format': 'json'})}"
        data = self._get_json(url)
        forward, reverse = {}, {}
        for b in data.get("results", {}).get("bindings", []):
            sat_id = b["value"]["value"]
            q_id   = b["item"]["value"].split("/")[-1]
            label  = b.get("itemLabel", {}).get("value", "")
            if sat_id not in forward:
                forward[sat_id] = {"q_id": q_id, "label": label}
            reverse[q_id] = sat_id
        print(f"  ✅ {len(reverse)} Q-ID:n med P14545")
        return forward, reverse

    def fetch_osm_sat_refs_all(self):
        print("📥 Hämtar OSM ref:stockholmarchipelagotrail (postpass batch)...")
        sql = (
            "SELECT osm_type, osm_id, "
            "tags->>'ref:stockholmarchipelagotrail' AS sat_ref, geom "
            "FROM postpass_pointlinepolygon "
            "WHERE tags ? 'ref:stockholmarchipelagotrail'"
        )
        url = f"{self.POSTPASS_URL}?{urlencode({'data': sql})}"
        data = self._get_json(url)
        osm_map = {"N": "node", "W": "way", "R": "relation"}
        lookup = {}
        for f in data.get("features", []):
            p = f["properties"]
            t   = osm_map.get(p.get("osm_type", "N"), "node")
            key = f"osm:{t}:{p['osm_id']}"
            lookup[key] = p.get("sat_ref") or ""
        print(f"  ✅ {len(lookup)} OSM-poster")
        return lookup

    # ------------------------------------------------------------------
    # Kontrollera om enskilda objekt är borttagna (bara för problem-poster)
    # ------------------------------------------------------------------
    def check_osm_deleted(self, osm_type, osm_id):
        """Returnerar True om objektet är borttaget (HTTP 410), False om det finns (200)."""
        url = f"{self.OSM_API}/{osm_type}/{osm_id}"
        status = self._http_status(url)
        return status == 410

    def check_wikidata_deleted_batch(self, q_ids: list) -> dict:
        """
        Kontrollerar upp till 50 Q-ID:n i taget.
        Returnerar {q_id: True} för borttagna/saknade.
        """
        result = {}
        batch_size = 50
        for i in range(0, len(q_ids), batch_size):
            batch = q_ids[i:i+batch_size]
            ids_str = "|".join(batch)
            url = f"{self.WIKIDATA_API}?{urlencode({'action':'wbgetentities','ids':ids_str,'format':'json','props':'info'})}"
            data = self._get_json(url)
            for qid, ent in data.get("entities", {}).items():
                result[qid] = "missing" in ent
        return result

    # ------------------------------------------------------------------
    # Bygger problem-poster
    # ------------------------------------------------------------------
    def build_issues(self, concordance, pois_meta, wd_fwd, wd_rev, osm_lookup,
                     exclude_prefixes):
        issues = []
        for external_id, sat_id in concordance.items():
            if any(external_id.startswith(p) for p in exclude_prefixes):
                continue

            if external_id.startswith("wikidata:"):
                q_id = external_id.split("wikidata:")[1]
                wd_sat = wd_rev.get(q_id)
                ok = (wd_sat == sat_id) if wd_sat is not None else False
                if ok:
                    continue  # inga problem
                meta = pois_meta.get(sat_id, {})
                wd_info = wd_fwd.get(sat_id, {})
                rec = IssueRecord(
                    external_id=external_id,
                    sat_id=sat_id,
                    source_type="wikidata",
                    name=meta.get("name") or wd_info.get("label"),
                    updated_at=meta.get("updated_at"),
                    first_seen=meta.get("first_seen"),
                    section=meta.get("section"),
                    wikidata_q=q_id,
                    wikidata_label=wd_info.get("label"),
                    wikidata_p14545_ok=False,
                    wikidata_p14545_value=wd_sat,
                )
                issues.append(rec)

            elif external_id.startswith("osm:"):
                osm_ref = osm_lookup.get(external_id)
                ok = (osm_ref == sat_id) if osm_ref is not None else False
                if ok:
                    continue
                parts = external_id.split(":")
                osm_type = parts[1] if len(parts) > 1 else "node"
                osm_num  = int(parts[2]) if len(parts) > 2 else None
                meta = pois_meta.get(sat_id, {})
                rec = IssueRecord(
                    external_id=external_id,
                    sat_id=sat_id,
                    source_type="osm",
                    name=meta.get("name"),
                    updated_at=meta.get("updated_at"),
                    first_seen=meta.get("first_seen"),
                    section=meta.get("section"),
                    osm_type=osm_type,
                    osm_numeric_id=osm_num,
                    osm_ref_ok=False,
                    osm_ref_value=osm_ref,
                )
                issues.append(rec)

        return issues

    # ------------------------------------------------------------------
    # Kontrollera borttagna (per-objekt, bara problem-poster)
    # ------------------------------------------------------------------
    def check_deletions(self, issues: list):
        # Wikidata: batch
        wd_issues = [r for r in issues if r.source_type == "wikidata" and r.wikidata_q]
        if wd_issues:
            print(f"🔍 Kontrollerar {len(wd_issues)} Wikidata-poster mot API (batch)...")
            q_ids = [r.wikidata_q for r in wd_issues]
            deleted_map = self.check_wikidata_deleted_batch(q_ids)
            for r in wd_issues:
                r.wikidata_deleted = deleted_map.get(r.wikidata_q, False)
            n_del = sum(1 for r in wd_issues if r.wikidata_deleted)
            print(f"  ✅ {n_del} borttagna Wikidata-objekt funna")

        # OSM: per-objekt (bara ~86 st)
        osm_issues = [r for r in issues if r.source_type == "osm" and r.osm_numeric_id]
        if osm_issues:
            print(f"🔍 Kontrollerar {len(osm_issues)} OSM-objekt mot API...")
            for i, r in enumerate(osm_issues):
                r.osm_deleted = self.check_osm_deleted(r.osm_type, r.osm_numeric_id)
                if (i+1) % 10 == 0:
                    print(f"  {i+1}/{len(osm_issues)} kontrollerade...")
            n_del = sum(1 for r in osm_issues if r.osm_deleted)
            print(f"  ✅ {n_del} borttagna OSM-objekt funna")

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------
    def _osm_link(self, r: IssueRecord) -> str:
        url = f"https://www.openstreetmap.org/{r.osm_type}/{r.osm_numeric_id}"
        label = r.external_id
        deleted_tag = ' <span class="tag-deleted">🗑️ BORTTAGET</span>' if r.osm_deleted else ""
        return f'<a href="{url}" target="_blank">{label}</a>{deleted_tag}'

    def _wd_link(self, r: IssueRecord) -> str:
        url = f"https://www.wikidata.org/wiki/{r.wikidata_q}"
        deleted_tag = ' <span class="tag-deleted">🗑️ BORTTAGET</span>' if r.wikidata_deleted else ""
        return f'<a href="{url}" target="_blank">{r.external_id}</a>{deleted_tag}'

    def _sat_links(self, sat_id: str) -> str:
        return (
            f'<a href="https://map.stockholmarchipelagotrail.com/?{sat_id}" target="_blank">'
            f'<code>{sat_id}</code></a> '
            f'<a href="https://map.stockholmarchipelagotrail.com/api/objects/{sat_id}" '
            f'target="_blank" style="font-size:.78em;color:#888">[json]</a>'
        )

    def _issue_row(self, idx, r: IssueRecord, section: str) -> str:
        if r.source_type == "wikidata":
            ext_cell = self._wd_link(r)
            if r.wikidata_p14545_value:
                back_cell = f'<span class="badge-warn">⚠️ Fel värde: {r.wikidata_p14545_value}</span>'
            else:
                back_cell = '<span class="badge-warn">⚠️ Saknar P14545</span>'
        else:
            ext_cell = self._osm_link(r)
            if r.osm_ref_value:
                back_cell = f'<span class="badge-warn">⚠️ Fel värde: {r.osm_ref_value}</span>'
            elif r.osm_ref_value == "":
                back_cell = '<span class="badge-warn">⚠️ Saknar ref:sat</span>'
            else:
                back_cell = '<span class="tag-deleted">🗑️ Ej i postpass</span>' if r.osm_deleted else '<span class="badge-warn">⚠️ Saknar ref:sat</span>'

        row_class = "row-deleted" if r.is_deleted else "row-issue"
        section_value = r.section or "okänd"
        return f"""
      <tr class="{row_class}" data-section="{section_value}" data-source="{r.source_type}" data-issue="{r.issue_type}">
        <td>{idx}</td>
        <td>{ext_cell}</td>
        <td>{self._sat_links(r.sat_id)}</td>
        <td>{r.source_type}</td>
        <td>{section_value}</td>
        <td>{back_cell}</td>
        <td data-val="{r.first_seen or ''}">{r.first_seen or '—'}</td>
        <td data-val="{r.updated_at or ''}">{r.updated_at or '—'}</td>
        <td>{r.name or '—'}</td>
      </tr>"""

    def generate_html(self, deleted: list, missing_ref: list, generated_at: str) -> str:
        all_issues = deleted + missing_ref
        sections = sorted({(r.section or "okänd") for r in all_issues})
        section_options = "\n".join(
            f'<option value="{s}">{s}</option>' for s in sections
        )

        # Borttagna objekt-sektion
        del_rows = "\n".join(self._issue_row(i+1, r, "deleted") for i, r in enumerate(deleted))
        del_rows_html = del_rows or "<tr><td colspan='9' class='empty'>Inga borttagna objekt ✅</td></tr>"

        # Saknade backreferenser-sektion
        miss_rows = "\n".join(self._issue_row(i+1, r, "missing") for i, r in enumerate(missing_ref))
        miss_rows_html = miss_rows or "<tr><td colspan='9' class='empty'>Inga saknade backreferenser ✅</td></tr>"

        table_headers = """
          <tr>
            <th>#</th>
            <th>Extern ID</th>
            <th>SAT ID</th>
            <th>Källa</th>
            <th>Etapp/Ö</th>
            <th>Problem</th>
            <th>Första sedd</th>
            <th>Uppdaterad</th>
            <th>Namn</th>
          </tr>"""

        return f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAT POI — Problem-rapport</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#333}}
    .container{{max-width:1400px;margin:0 auto}}
    .header{{background:linear-gradient(135deg,#c0392b,#8e1a1a);color:#fff;padding:30px}}
    .header h1{{font-size:2em;margin-bottom:8px}}
    .header p{{opacity:.85;font-size:1.05em}}
    .header small{{opacity:.7;font-size:.85em}}
    .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;padding:24px;background:#fff;border-bottom:2px solid #e9ecef}}
    .card{{padding:16px 20px;border-radius:8px;border-left:4px solid #c0392b;background:#f8f9fa}}
    .card.red{{border-color:#dc3545;background:#fff5f5}}
    .card.orange{{border-color:#fd7e14;background:#fff8f0}}
    .card h3{{font-size:.8em;text-transform:uppercase;color:#666;margin-bottom:6px}}
    .card .num{{font-size:2em;font-weight:700}}
    .card .sub{{font-size:.8em;color:#888;margin-top:4px}}
    .section{{padding:24px}}
    .section h2{{margin-bottom:12px;display:flex;align-items:center;gap:10px}}
    .section p.desc{{color:#666;font-size:.92em;margin-bottom:16px}}
    .filters{{padding:20px 24px;background:#fff;border-top:1px solid #e9ecef;border-bottom:1px solid #e9ecef;display:flex;flex-wrap:wrap;gap:12px;align-items:end}}
    .filter-group{{display:flex;flex-direction:column;gap:6px}}
    .filter-group label{{font-size:.85em;color:#666;font-weight:600}}
    .filter-group select{{padding:8px 10px;border:1px solid #d0d7de;border-radius:6px;background:#fff;min-width:180px}}
    .filter-note{{font-size:.85em;color:#666}}
    .table-wrap{{overflow-x:auto;background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08)}}
    table{{width:100%;border-collapse:collapse;font-size:.84em}}
    thead{{background:#f8f9fa;border-bottom:2px solid #c0392b;position:sticky;top:0;z-index:10}}
    th{{padding:11px 12px;text-align:left;font-weight:600;white-space:nowrap;cursor:pointer;user-select:none}}
    th:hover{{background:#e9ecef}}
    th.sort-asc::after{{content:" ▲";opacity:.7}}
    th.sort-desc::after{{content:" ▼";opacity:.7}}
    th:not(.sort-asc):not(.sort-desc)::after{{content:" ⇅";opacity:.25}}
    td{{padding:9px 12px;border-bottom:1px solid #f0f2f5;vertical-align:top}}
    tr:hover td{{background:#fafbff}}
    .row-deleted td{{background:#fff0f0}}
    .row-issue td{{background:#fffdf0}}
    .empty{{text-align:center;padding:24px;color:#888;font-style:italic}}
    code{{background:#f0f2f5;padding:2px 6px;border-radius:3px;font-size:.88em}}
    a{{color:#c0392b;text-decoration:none;font-weight:500}}
    a:hover{{text-decoration:underline}}
    .badge-warn{{display:inline-block;background:#fff3cd;color:#856404;padding:3px 9px;border-radius:12px;font-size:.82em;font-weight:600}}
    .tag-deleted{{display:inline-block;background:#f8d7da;color:#721c24;padding:3px 9px;border-radius:12px;font-size:.82em;font-weight:700}}
    .section-deleted h2{{color:#c0392b}}
    .section-missing h2{{color:#856404}}
    .footer{{text-align:center;padding:20px;color:#777;font-size:.88em;border-top:1px solid #e9ecef;background:#fff;margin-top:24px}}
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>⚠️ SAT POI — Problem-rapport</h1>
    <p>Enbart poster med saknade backreferenser eller borttagna externa objekt</p>
    <small>Genererad: {generated_at} &nbsp;|&nbsp; {self.email}</small>
  </div>

  <div class="stats">
    <div class="card red">
      <h3>🗑️ Borttagna objekt</h3>
      <div class="num" style="color:#c0392b">{len(deleted)}</div>
      <div class="sub">Kräver omedelbar åtgärd</div>
    </div>
    <div class="card red">
      <h3>OSM borttagna</h3>
      <div class="num" style="color:#c0392b">{sum(1 for r in deleted if r.source_type=='osm')}</div>
    </div>
    <div class="card red">
      <h3>Wikidata borttagna</h3>
      <div class="num" style="color:#c0392b">{sum(1 for r in deleted if r.source_type=='wikidata')}</div>
    </div>
    <div class="card orange">
      <h3>⚠️ Saknar backreferens</h3>
      <div class="num" style="color:#856404">{len(missing_ref)}</div>
      <div class="sub">Objektet finns, ref saknas</div>
    </div>
    <div class="card orange">
      <h3>OSM saknar ref:sat</h3>
      <div class="num" style="color:#856404">{sum(1 for r in missing_ref if r.source_type=='osm')}</div>
    </div>
    <div class="card orange">
      <h3>WD saknar P14545</h3>
      <div class="num" style="color:#856404">{sum(1 for r in missing_ref if r.source_type=='wikidata')}</div>
    </div>
  </div>

  <div class="filters">
    <div class="filter-group">
      <label for="section-filter">Filtrera etapp/ö</label>
      <select id="section-filter">
        <option value="all">Alla</option>
        {section_options}
      </select>
    </div>
    <div class="filter-group">
      <label for="source-filter">Filtrera källa</label>
      <select id="source-filter">
        <option value="all">Alla</option>
        <option value="osm">OSM</option>
        <option value="wikidata">Wikidata</option>
      </select>
    </div>
    <div class="filter-group">
      <label for="issue-filter">Filtrera problemtyp</label>
      <select id="issue-filter">
        <option value="all">Alla</option>
        <option value="deleted">Borttagna objekt</option>
        <option value="missing_ref">Saknar backreferens</option>
      </select>
    </div>
    <div class="filter-note" id="filter-count"></div>
  </div>

  <!-- SEKTION 1: Borttagna objekt -->
  <div class="section section-deleted">
    <h2>🗑️ Borttagna objekt ({len(deleted)} st)</h2>
    <p class="desc">
      Dessa poster i concordance.json pekar på OSM-objekt eller Wikidata-objekt som har <strong>tagits bort</strong>.
      Concordance behöver uppdateras.
    </p>
    <div class="table-wrap">
      <table id="tbl-deleted">
        <thead>{table_headers}</thead>
        <tbody>{del_rows_html}</tbody>
      </table>
    </div>
  </div>

  <!-- SEKTION 2: Saknar backreferens -->
  <div class="section section-missing">
    <h2>⚠️ Saknar backreferens ({len(missing_ref)} st)</h2>
    <p class="desc">
      Dessa poster finns kvar i OSM / Wikidata men <strong>saknar ref:stockholmarchipelagotrail</strong> (OSM) 
      eller <strong>Property P14545</strong> (Wikidata) som pekar tillbaka till SAT.
    </p>
    <div class="table-wrap">
      <table id="tbl-missing">
        <thead>{table_headers}</thead>
        <tbody>{miss_rows_html}</tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    <a href="https://www.wikidata.org/wiki/Property:P14545" target="_blank">Wikidata P14545</a> &nbsp;|&nbsp;
    <a href="https://taginfo.openstreetmap.org/keys/ref%3Astockholmarchipelagotrail" target="_blank">OSM tag info</a> &nbsp;|&nbsp;
    <a href="sat_poi_report.html">Fullständig rapport</a> &nbsp;|&nbsp;
    <a href="sat_poi_issues_report.json">json</a>
  </div>
</div>

<script>
(function() {{
  const filterEls = {{
    section: document.getElementById('section-filter'),
    source: document.getElementById('source-filter'),
    issue: document.getElementById('issue-filter'),
    count: document.getElementById('filter-count'),
  }};

  function applyFilters() {{
    const sectionVal = filterEls.section.value;
    const sourceVal = filterEls.source.value;
    const issueVal = filterEls.issue.value;
    const rows = document.querySelectorAll('#tbl-deleted tbody tr, #tbl-missing tbody tr');
    let visible = 0;

    rows.forEach((row) => {{
      if (row.classList.contains('empty')) return;
      const rowSection = row.dataset.section || 'okänd';
      const rowSource = row.dataset.source || '';
      const rowIssue = row.dataset.issue || '';
      const show =
        (sectionVal === 'all' || rowSection === sectionVal) &&
        (sourceVal === 'all' || rowSource === sourceVal) &&
        (issueVal === 'all' || rowIssue === issueVal);
      row.style.display = show ? '' : 'none';
      if (show) visible += 1;
    }});
    filterEls.count.textContent = `Visar ${{visible}} poster`;
  }}

  function makeTableSortable(tblId) {{
    const tbl = document.getElementById(tblId);
    if (!tbl) return;
    let sortCol = -1, sortAsc = true;
    function cellVal(row, col) {{
      const td = row.cells[col];
      return (td ? (td.dataset.val || td.innerText || '') : '').trim().toLowerCase();
    }}
    tbl.querySelectorAll('th').forEach((th, i) => {{
      th.addEventListener('click', () => {{
        if (sortCol === i) sortAsc = !sortAsc; else {{ sortCol = i; sortAsc = true; }}
        tbl.querySelectorAll('th').forEach((t, j) => {{
          t.classList.remove('sort-asc','sort-desc');
          if (j === i) t.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
        }});
        const tbody = tbl.tBodies[0];
        Array.from(tbody.rows)
          .sort((a, b) => {{
            const av = cellVal(a, i), bv = cellVal(b, i);
            return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
          }})
          .forEach(r => tbody.appendChild(r));
      }});
    }});
  }}
  makeTableSortable('tbl-deleted');
  makeTableSortable('tbl-missing');
  filterEls.section.addEventListener('change', applyFilters);
  filterEls.source.addEventListener('change', applyFilters);
  filterEls.issue.addEventListener('change', applyFilters);
  applyFilters();
}})();
</script>
</body>
</html>"""

    # ------------------------------------------------------------------
    # JSON-export
    # ------------------------------------------------------------------
    def _record_to_dict(self, r: IssueRecord) -> dict:
        d = {
            "external_id": r.external_id,
            "sat_id": r.sat_id,
            "sat_map_url": f"https://map.stockholmarchipelagotrail.com/?{r.sat_id}",
            "sat_api_url": f"https://map.stockholmarchipelagotrail.com/api/objects/{r.sat_id}",
            "source_type": r.source_type,
            "issue_type": r.issue_type,
            "section": r.section,
            "name": r.name,
            "first_seen": r.first_seen,
            "updated_at": r.updated_at,
        }
        if r.source_type == "wikidata":
            d["wikidata"] = {
                "q_id": r.wikidata_q,
                "label": r.wikidata_label,
                "url": f"https://www.wikidata.org/wiki/{r.wikidata_q}",
                "deleted": r.wikidata_deleted,
                "p14545_ok": r.wikidata_p14545_ok,
                "p14545_value_in_wikidata": r.wikidata_p14545_value,
            }
        elif r.source_type == "osm":
            d["osm"] = {
                "type": r.osm_type,
                "id": r.osm_numeric_id,
                "url": f"https://www.openstreetmap.org/{r.osm_type}/{r.osm_numeric_id}",
                "deleted": r.osm_deleted,
                "ref_ok": r.osm_ref_ok,
                "ref_value_in_osm": r.osm_ref_value,
            }
        return d

    def save_json(self, deleted: list, missing_ref: list, generated_at: str, json_file: str):
        output = {
            "generated_at": generated_at,
            "generated_by": self.email,
            "summary": {
                "total_issues": len(deleted) + len(missing_ref),
                "deleted_total": len(deleted),
                "deleted_osm": sum(1 for r in deleted if r.source_type == "osm"),
                "deleted_wikidata": sum(1 for r in deleted if r.source_type == "wikidata"),
                "missing_ref_total": len(missing_ref),
                "missing_ref_osm": sum(1 for r in missing_ref if r.source_type == "osm"),
                "missing_ref_wikidata": sum(1 for r in missing_ref if r.source_type == "wikidata"),
            },
            "deleted_objects": [self._record_to_dict(r) for r in deleted],
            "missing_backreference": [self._record_to_dict(r) for r in missing_ref],
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON sparad: {json_file}")

    # ------------------------------------------------------------------
    # Huvudmetod
    # ------------------------------------------------------------------
    def run(self, output_file="sat_poi_issues_report.html", exclude_prefixes=None):
        if exclude_prefixes is None:
            exclude_prefixes = []

        concordance = self.fetch_concordance()
        pois_meta   = self.fetch_pois_metadata()
        wd_fwd, wd_rev = self.fetch_wikidata_p14545_all()
        osm_lookup  = self.fetch_osm_sat_refs_all()

        print("🔧 Identifierar problem-poster...")
        issues = self.build_issues(concordance, pois_meta, wd_fwd, wd_rev,
                                   osm_lookup, exclude_prefixes)
        print(f"  ✅ {len(issues)} problem-poster")

        print("🔍 Kontrollerar om objekt är borttagna...")
        self.check_deletions(issues)

        deleted     = [r for r in issues if r.is_deleted]
        missing_ref = [r for r in issues if not r.is_deleted]

        print(f"\n📊 RESULTAT:")
        print(f"   🗑️  Borttagna objekt : {len(deleted)}")
        print(f"     - OSM            : {sum(1 for r in deleted if r.source_type=='osm')}")
        print(f"     - Wikidata       : {sum(1 for r in deleted if r.source_type=='wikidata')}")
        print(f"   ⚠️  Saknar backreferens: {len(missing_ref)}")
        print(f"     - OSM            : {sum(1 for r in missing_ref if r.source_type=='osm')}")
        print(f"     - Wikidata       : {sum(1 for r in missing_ref if r.source_type=='wikidata')}")

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:00Z")

        html = self.generate_html(deleted, missing_ref, generated_at)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"\n✅ HTML sparad: {output_file}")

        json_file = output_file.replace(".html", ".json")
        self.save_json(deleted, missing_ref, generated_at, json_file)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email",          default="salgo60@msn.com")
    parser.add_argument("--output",         default="sat_poi_issues_report.html")
    parser.add_argument("--exclude-prefix", action="append", dest="exclude_prefixes",
                        default=["grillplatser"])
    args = parser.parse_args()

    gen = IssuesReportGenerator(email=args.email)
    gen.run(output_file=args.output, exclude_prefixes=args.exclude_prefixes)


if __name__ == "__main__":
    main()
