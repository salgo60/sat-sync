#!/usr/bin/env python3
"""
Generera HTML-rapport över SAT POI-identifierare från concordance.json
och validera mot Wikidata (P14545) och OpenStreetMap (ref:stockholmarchipelagotrail).

Alla externa API-anrop sker som batch — ingen per-post HTTP-förfrågan.
"""

import json
import argparse
import urllib.request
from urllib.parse import urlencode, quote
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class POIRecord:
    """En POI-post från concordance.json"""
    external_id: str           # t.ex. osm:node:123 eller wikidata:Q456
    sat_id: str                # t.ex. sat:poi:abc
    source_type: str           # "osm" | "wikidata" | "other"
    name: Optional[str] = None
    updated_at: Optional[str] = None
    first_seen: Optional[str] = None
    # Wikidata-fält (relevant när source_type == "wikidata")
    wikidata_q: Optional[str] = None       # Q-nummer, t.ex. Q140621337
    wikidata_label: Optional[str] = None
    wikidata_ids_count: Optional[int] = None  # antal identifierare i Wikidata
    wikidata_p14545_ok: Optional[bool] = None  # True=backreferens OK, False=saknas/fel
    wikidata_p14545_value: Optional[str] = None  # faktiskt värde i Wikidata
    # OSM-fält (relevant när source_type == "osm")
    osm_type: Optional[str] = None        # "node" | "way" | "relation"
    osm_numeric_id: Optional[int] = None
    osm_ref_ok: Optional[bool] = None     # True=ref:stockholmarchipelagotrail OK
    osm_ref_value: Optional[str] = None   # faktiskt värde i OSM


class POIReportGenerator:
    """Genererar HTML-rapport med batch-datahämtning."""

    CONCORDANCE_URL = "https://map.stockholmarchipelagotrail.com/data/geojson/poi-concordance.json"
    POIS_URL        = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
    WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
    POSTPASS_URL    = "https://postpass.geofabrik.de/api/interpreter"

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

    # ------------------------------------------------------------------
    # Batch-hämtning 1: Wikidata — alla poster med P14545
    # ------------------------------------------------------------------
    def fetch_wikidata_p14545_all(self) -> tuple[dict, dict]:
        """
        Returnerar:
          forward:  {sat_id → {q_id, label, ids_count}}
          reverse:  {q_id   → sat_id}
        """
        print("📥 Hämtar alla Wikidata-poster med P14545 (SPARQL batch)...")
        query = """
SELECT ?item ?itemLabel ?value ?ids WHERE {
 ?item wdt:P14545 ?value ;
       wikibase:identifiers ?ids .
 SERVICE wikibase:label { bd:serviceParam wikibase:language "sv,mul,en". }
}
ORDER BY DESC(?ids) (?item)
"""
        url = f"{self.WIKIDATA_SPARQL}?{urlencode({'query': query, 'format': 'json'})}"
        data = self._get_json(url)
        bindings = data.get("results", {}).get("bindings", [])

        forward = {}
        reverse = {}
        for b in bindings:
            sat_id = b["value"]["value"]
            q_id   = b["item"]["value"].split("/")[-1]
            label  = b.get("itemLabel", {}).get("value", "")
            ids_c  = int(b.get("ids", {}).get("value", 0))
            if sat_id not in forward:
                forward[sat_id] = {"q_id": q_id, "label": label, "ids_count": ids_c}
            reverse[q_id] = sat_id

        print(f"  ✅ {len(forward)} unika SAT-ID:n i Wikidata, {len(reverse)} Q-ID:n totalt")
        return forward, reverse

    # ------------------------------------------------------------------
    # Batch-hämtning 2: OSM — alla poster med ref:stockholmarchipelagotrail
    # ------------------------------------------------------------------
    def fetch_osm_sat_refs_all(self) -> dict:
        """
        Returnerar {osm:node:ID | osm:way:ID | osm:relation:ID → sat_ref_value}
        """
        print("📥 Hämtar alla OSM-poster med ref:stockholmarchipelagotrail (postpass batch)...")
        sql = (
            "SELECT osm_type, osm_id, "
            "tags->>'ref:stockholmarchipelagotrail' AS sat_ref, geom "
            "FROM postpass_pointlinepolygon "
            "WHERE tags ? 'ref:stockholmarchipelagotrail'"
        )
        url = f"{self.POSTPASS_URL}?{urlencode({'data': sql})}"
        data = self._get_json(url)
        features = data.get("features", [])

        osm_type_map = {"N": "node", "W": "way", "R": "relation"}
        lookup = {}
        for f in features:
            p = f["properties"]
            t = osm_type_map.get(p.get("osm_type", "?"), "node")
            key = f"osm:{t}:{p['osm_id']}"
            lookup[key] = p.get("sat_ref") or ""

        print(f"  ✅ {len(lookup)} OSM-poster med ref:stockholmarchipelagotrail")
        return lookup

    # ------------------------------------------------------------------
    # Batch-hämtning 3: Concordance + metadata
    # ------------------------------------------------------------------
    def fetch_concordance(self) -> dict:
        print("📥 Hämtar poi-concordance.json...")
        data = self._get_json(self.CONCORDANCE_URL)
        items = data.get("satIdOf", {})
        print(f"  ✅ {len(items)} poster i concordance")
        return items

    def fetch_pois_metadata(self) -> dict:
        """Returnerar {sat_id → {updated_at, first_seen, wikidata, name}}"""
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
                    "wikidata":   p.get("wikidata"),
                    "name":       p.get("name"),
                }
        print(f"  ✅ Metadata för {len(meta)} POI:er")
        return meta

    # ------------------------------------------------------------------
    # Bygg POI-poster
    # ------------------------------------------------------------------
    def build_records(
        self,
        concordance: dict,
        pois_meta: dict,
        wd_forward: dict,
        wd_reverse: dict,
        osm_lookup: dict,
        exclude_prefixes: list[str],
    ) -> list[POIRecord]:
        records = []
        skipped = 0
        for external_id, sat_id in concordance.items():
            # Filtrera bort oönskade prefix
            if any(external_id.startswith(p) for p in exclude_prefixes):
                skipped += 1
                continue

            # Bestäm source_type
            if external_id.startswith("wikidata:"):
                source_type = "wikidata"
            elif external_id.startswith("osm:"):
                source_type = "osm"
            else:
                source_type = "other"

            rec = POIRecord(
                external_id=external_id,
                sat_id=sat_id,
                source_type=source_type,
            )

            # Metadata från pois.geojson
            meta = pois_meta.get(sat_id, {})
            rec.updated_at = meta.get("updated_at")
            rec.first_seen = meta.get("first_seen")
            rec.name       = meta.get("name")

            # ---- Wikidata-källpost ----
            if source_type == "wikidata":
                q_id = external_id.split("wikidata:")[1]  # t.ex. Q140621337
                rec.wikidata_q = q_id

                # Kolla om Q-ID:t har P14545 (batch-reverse-lookup)
                wd_sat = wd_reverse.get(q_id)
                if wd_sat is None:
                    rec.wikidata_p14545_ok = False
                    rec.wikidata_p14545_value = None
                elif wd_sat == sat_id:
                    rec.wikidata_p14545_ok = True
                    rec.wikidata_p14545_value = wd_sat
                else:
                    rec.wikidata_p14545_ok = False   # har P14545 men fel värde
                    rec.wikidata_p14545_value = wd_sat

                # Hämta label + ids_count från forward-index om SAT-ID matchar
                if sat_id in wd_forward:
                    wd_info = wd_forward[sat_id]
                    rec.wikidata_label     = wd_info["label"]
                    rec.wikidata_ids_count = wd_info["ids_count"]
                    if not rec.name:
                        rec.name = wd_info["label"]

            # ---- OSM-källpost ----
            elif source_type == "osm":
                parts = external_id.split(":")   # ["osm", "node", "12345"]
                rec.osm_type       = parts[1] if len(parts) > 1 else "node"
                rec.osm_numeric_id = int(parts[2]) if len(parts) > 2 else None

                # Kolla om OSM-objektet har ref:stockholmarchipelagotrail (batch-lookup)
                osm_ref = osm_lookup.get(external_id)
                if osm_ref is None:
                    rec.osm_ref_ok    = False
                    rec.osm_ref_value = None
                elif osm_ref == sat_id:
                    rec.osm_ref_ok    = True
                    rec.osm_ref_value = osm_ref
                else:
                    rec.osm_ref_ok    = False   # har taggen men fel värde
                    rec.osm_ref_value = osm_ref

            records.append(rec)

        if skipped:
            print(f"  ⚠️  Exkluderade {skipped} poster (prefix-filter)")
        return records

    # ------------------------------------------------------------------
    # HTML-generering
    # ------------------------------------------------------------------
    def _osm_link(self, rec: POIRecord) -> str:
        if rec.osm_numeric_id is None:
            return rec.external_id
        url = f"https://www.openstreetmap.org/{rec.osm_type}/{rec.osm_numeric_id}"
        return f'<a href="{url}" target="_blank">{rec.external_id}</a>'

    def _wd_link(self, q_id: str) -> str:
        url = f"https://www.wikidata.org/wiki/{q_id}"
        return f'<a href="{url}" target="_blank">{q_id}</a>'

    def _badge(self, ok: Optional[bool], ok_text: str, fail_text: str) -> str:
        if ok is True:
            return f'<span class="badge-ok">✅ {ok_text}</span>'
        if ok is False:
            return f'<span class="badge-warn">⚠️ {fail_text}</span>'
        return '<span class="badge-neutral">—</span>'

    def generate_html(self, records: list[POIRecord], generated_at: str) -> str:
        # Statistik
        total        = len(records)
        wd_total     = sum(1 for r in records if r.source_type == "wikidata")
        wd_ok        = sum(1 for r in records if r.source_type == "wikidata" and r.wikidata_p14545_ok is True)
        wd_fail      = sum(1 for r in records if r.source_type == "wikidata" and r.wikidata_p14545_ok is False)
        osm_total    = sum(1 for r in records if r.source_type == "osm")
        osm_ok       = sum(1 for r in records if r.source_type == "osm" and r.osm_ref_ok is True)
        osm_fail     = sum(1 for r in records if r.source_type == "osm" and r.osm_ref_ok is False)

        rows = []
        for idx, r in enumerate(records, 1):
            if r.source_type == "wikidata":
                ext_cell = self._wd_link(r.wikidata_q)
                ids_cell = str(r.wikidata_ids_count) if r.wikidata_ids_count else "—"
                back_label = "P14545"
                back_cell  = self._badge(r.wikidata_p14545_ok, "Har P14545", "Saknar P14545")
                if r.wikidata_p14545_ok is False and r.wikidata_p14545_value:
                    back_cell += f'<br><small>Har: {r.wikidata_p14545_value}</small>'
            elif r.source_type == "osm":
                ext_cell   = self._osm_link(r)
                ids_cell   = r.osm_type or "—"
                back_label = "ref:sat"
                back_cell  = self._badge(r.osm_ref_ok, "Har ref", "Saknar ref")
                if r.osm_ref_ok is False and r.osm_ref_value:
                    back_cell += f'<br><small>Har: {r.osm_ref_value}</small>'
            else:
                ext_cell   = f"<code>{r.external_id}</code>"
                ids_cell   = "—"
                back_label = "—"
                back_cell  = "—"

            row_class = "row-ok" if (r.wikidata_p14545_ok or r.osm_ref_ok) else "row-warn"
            rows.append(f"""
      <tr class="{row_class}">
        <td>{idx}</td>
        <td>{ext_cell}</td>
        <td>
          <a href="https://map.stockholmarchipelagotrail.com/?{r.sat_id}" target="_blank"><code>{r.sat_id}</code></a>
          <a href="https://map.stockholmarchipelagotrail.com/api/objects/{r.sat_id}" target="_blank" style="margin-left:6px;font-size:.78em;color:#888">[json]</a>
        </td>
        <td>{r.source_type}</td>
        <td>{ids_cell}</td>
        <td>{back_cell}</td>
        <td data-val="{r.first_seen or ''}">{r.first_seen or "—"}</td>
        <td data-val="{r.updated_at or ''}">{r.updated_at or "—"}</td>
        <td>{r.name or "—"}</td>
      </tr>""")

        rows_html = "\n".join(rows)

        return f"""<!DOCTYPE html>
<html lang="sv">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAT POI Concordance Rapport</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#333}}
    .container{{max-width:1400px;margin:0 auto}}
    .header{{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:30px;}}
    .header h1{{font-size:2em;margin-bottom:8px}}
    .header p{{opacity:.85;font-size:1.05em}}
    .header small{{opacity:.7;font-size:.85em}}
    .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;padding:24px;background:#fff;border-bottom:2px solid #e9ecef}}
    .card{{background:#f8f9fa;padding:16px 20px;border-radius:8px;border-left:4px solid #667eea}}
    .card.green{{border-color:#28a745}}
    .card.red{{border-color:#dc3545}}
    .card.blue{{border-color:#0d6efd}}
    .card h3{{font-size:.8em;text-transform:uppercase;color:#666;margin-bottom:6px}}
    .card .num{{font-size:2em;font-weight:700;color:#222}}
    .card .sub{{font-size:.8em;color:#888;margin-top:4px}}
    .content{{padding:24px}}
    .table-wrap{{overflow-x:auto;background:#fff;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.07)}}
    table{{width:100%;border-collapse:collapse;font-size:.84em}}
    thead{{background:#f8f9fa;border-bottom:2px solid #667eea;position:sticky;top:0;z-index:10}}
    th{{padding:11px 12px;text-align:left;font-weight:600;white-space:nowrap;cursor:pointer;user-select:none}}
    th:hover{{background:#e9ecef}}
    th.sort-asc::after{{content:" ▲";opacity:.7}}
    th.sort-desc::after{{content:" ▼";opacity:.7}}
    th:not(.sort-asc):not(.sort-desc)::after{{content:" ⇅";opacity:.25}}
    td{{padding:9px 12px;border-bottom:1px solid #f0f2f5;vertical-align:top}}
    tr:hover td{{background:#fafbff}}
    .row-ok td{{}}
    .row-warn td{{background:#fffdf0}}
    code{{background:#f0f2f5;padding:2px 6px;border-radius:3px;font-size:.88em}}
    a{{color:#667eea;text-decoration:none;font-weight:500}}
    a:hover{{text-decoration:underline}}
    .badge-ok{{display:inline-block;background:#d4edda;color:#155724;padding:3px 9px;border-radius:12px;font-size:.82em;font-weight:600;white-space:nowrap}}
    .badge-warn{{display:inline-block;background:#fff3cd;color:#856404;padding:3px 9px;border-radius:12px;font-size:.82em;font-weight:600;white-space:nowrap}}
    .badge-neutral{{display:inline-block;background:#e2e3e5;color:#555;padding:3px 9px;border-radius:12px;font-size:.82em}}
    .footer{{text-align:center;padding:20px;color:#777;font-size:.88em;border-top:1px solid #e9ecef;background:#fff;margin-top:24px}}
    @media(max-width:768px){{th,td{{padding:6px 8px}} .stats{{grid-template-columns:1fr 1fr}}}}
  </style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🗺️ SAT POI Concordance Rapport</h1>
    <p>Validering av Stockholm Archipelago Trail-identifierare mot Wikidata (P14545) och OpenStreetMap (ref:stockholmarchipelagotrail)</p>
    <small>Genererad: {generated_at} &nbsp;|&nbsp; Kontakt: {self.email}</small>
  </div>

  <div class="stats">
    <div class="card"><h3>Totalt poster</h3><div class="num">{total}</div><div class="sub">exkl. grillplatser</div></div>
    <div class="card blue"><h3>Wikidata-poster</h3><div class="num">{wd_total}</div></div>
    <div class="card green"><h3>WD med P14545 ✅</h3><div class="num">{wd_ok}</div><div class="sub">{wd_fail} saknar P14545</div></div>
    <div class="card blue"><h3>OSM-poster</h3><div class="num">{osm_total}</div></div>
    <div class="card green"><h3>OSM med ref:sat ✅</h3><div class="num">{osm_ok}</div><div class="sub">{osm_fail} saknar ref</div></div>
    <div class="card {'green' if wd_ok+osm_ok == total else 'red'}">
      <h3>Total täckning</h3>
      <div class="num">{(wd_ok+osm_ok)*100//total if total else 0}%</div>
      <div class="sub">{wd_ok+osm_ok} / {total} OK</div>
    </div>
  </div>

  <div class="content">
    <div class="table-wrap">
      <table id="tbl">
        <thead>
          <tr>
            <th>#</th>
            <th>Extern ID</th>
            <th>SAT ID</th>
            <th>Källa</th>
            <th>Info</th>
            <th>Backreferens</th>
            <th>Första sedd</th>
            <th>Uppdaterad</th>
            <th>Namn</th>
          </tr>
        </thead>
        <tbody>
          {rows_html}
        </tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    Källor:
    <a href="{self.CONCORDANCE_URL}" target="_blank">poi-concordance.json</a> &nbsp;|&nbsp;
    <a href="{self.POIS_URL}" target="_blank">pois.geojson</a> &nbsp;|&nbsp;
    <a href="https://www.wikidata.org/wiki/Property:P14545" target="_blank">Wikidata P14545</a> &nbsp;|&nbsp;
    <a href="https://taginfo.openstreetmap.org/keys/ref%3Astockholmarchipelagotrail" target="_blank">OSM tag info</a>
  </div>
</div>

<script>
(function() {{
  const tbl = document.getElementById('tbl');
  let sortCol = -1, sortAsc = true;

  function cellVal(row, col) {{
    const td = row.cells[col];
    return (td.dataset.val || td.innerText || '').trim().toLowerCase();
  }}

  function sortBy(col) {{
    const ths = tbl.querySelectorAll('th');
    ths.forEach((th, i) => {{
      th.classList.remove('sort-asc','sort-desc');
      if (i === col) th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
    }});
    const tbody = tbl.tBodies[0];
    const rows = Array.from(tbody.rows);
    rows.sort((a, b) => {{
      const av = cellVal(a, col), bv = cellVal(b, col);
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
    }});
    rows.forEach(r => tbody.appendChild(r));
  }}

  tbl.querySelectorAll('th').forEach((th, i) => {{
    th.addEventListener('click', () => {{
      if (sortCol === i) sortAsc = !sortAsc; else {{ sortCol = i; sortAsc = true; }}
      sortBy(i);
    }});
  }});
}})();
</script>
</body>
</html>"""

    # ------------------------------------------------------------------
    # Huvudmetod
    # ------------------------------------------------------------------
    def run(
        self,
        output_file: str = "sat_poi_report.html",
        exclude_prefixes: list[str] = None,
    ):
        if exclude_prefixes is None:
            exclude_prefixes = []

        concordance  = self.fetch_concordance()
        pois_meta    = self.fetch_pois_metadata()
        wd_fwd, wd_rev = self.fetch_wikidata_p14545_all()
        osm_lookup   = self.fetch_osm_sat_refs_all()

        print("🔧 Bygger POI-poster...")
        records = self.build_records(
            concordance, pois_meta, wd_fwd, wd_rev, osm_lookup, exclude_prefixes
        )
        print(f"  ✅ {len(records)} poster att rapportera")

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        html = self.generate_html(records, generated_at)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"\n✅ Rapport sparad: {output_file}")
        self._print_stats(records)

    def _print_stats(self, records: list[POIRecord]):
        total     = len(records)
        wd_total  = sum(1 for r in records if r.source_type == "wikidata")
        wd_ok     = sum(1 for r in records if r.source_type == "wikidata" and r.wikidata_p14545_ok)
        osm_total = sum(1 for r in records if r.source_type == "osm")
        osm_ok    = sum(1 for r in records if r.source_type == "osm" and r.osm_ref_ok)
        print(f"\n📊 STATISTIK (totalt {total} poster)")
        print(f"   Wikidata : {wd_total} poster — {wd_ok} har P14545 ✅, {wd_total-wd_ok} saknar ❌")
        print(f"   OSM      : {osm_total} poster — {osm_ok} har ref:sat ✅, {osm_total-osm_ok} saknar ❌")


def main():
    parser = argparse.ArgumentParser(description="Generera SAT POI-concordance rapport (batch-version)")
    parser.add_argument("--email",          default="salgo60@msn.com")
    parser.add_argument("--output",         default="sat_poi_report.html")
    parser.add_argument("--exclude-prefix", action="append", dest="exclude_prefixes",
                        default=["grillplatser"],
                        help="Exkludera externa ID:n med detta prefix (kan anges flera gånger)")
    args = parser.parse_args()

    gen = POIReportGenerator(email=args.email)
    gen.run(output_file=args.output, exclude_prefixes=args.exclude_prefixes)


if __name__ == "__main__":
    main()
