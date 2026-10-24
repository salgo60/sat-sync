"""Read-only, versioned reconciliation for SAT POI identities."""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from urllib.parse import quote

from sat_sync.models import Identity

SAT_POI_ID = re.compile(r"^sat:poi:[a-z0-9]+$")
WIKIDATA_ID = re.compile(r"^Q[1-9][0-9]*$")
SAT_MAP_URL = "https://map.stockholmarchipelagotrail.com/?{sat_id}"
OSM_TAG = "ref:stockholmarchipelagotrail"


def _timestamp(value: str | None = None) -> str:
    if value:
        return value
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sat_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value and not value.startswith("sat:"):
        value = f"sat:poi:{value}"
    return value or None


def _wikidata_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"(?:^|[/ :])(Q[1-9][0-9]*)$", value.strip())
    return match.group(1) if match else None


def _osm_target(value: object) -> tuple[str, str] | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return ("", str(value))
    if not isinstance(value, str):
        return None
    value = value.strip()
    match = re.search(r"(?:^|/|:)(node|way|relation)[/:](\d+)$", value)
    if match:
        return match.group(1), match.group(2)
    if value.isdigit():
        return "", value
    return None


def _osm_url(osm_type: str, osm_id: str) -> str:
    if osm_type not in {"node", "way", "relation"} or not osm_id.isdigit():
        return ""
    return f"https://www.openstreetmap.org/{osm_type}/{osm_id}"


def _finding(
    finding_type: str,
    sat_ids: list[str],
    title: str,
    severity: str,
    evidence: list[dict],
    *,
    osm_objects: list[dict] | None = None,
    wikidata_ids: list[str] | None = None,
) -> dict:
    stable_key = {
        "type": finding_type,
        "satIds": sorted(sat_ids),
        "osm": sorted(
            f"{obj.get('type', '')}:{obj.get('id', '')}"
            for obj in osm_objects or []
        ),
        "wikidata": sorted(wikidata_ids or []),
        "evidence": sorted(
            (
                {
                    "source": item.get("source"),
                    "satId": item.get("satId"),
                    "id": item.get("id"),
                    "reason": item.get("reason"),
                    "recordCount": item.get("recordCount"),
                    "satIds": item.get("satIds"),
                    "osm": (
                        {
                            "type": item["osm"].get("type"),
                            "id": item["osm"].get("id"),
                            "satId": item["osm"].get("satId"),
                        }
                        if isinstance(item.get("osm"), dict)
                        else item.get("osm")
                    ),
                    "wikidata": item.get("wikidata"),
                }
                for item in evidence
            ),
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        ),
    }
    finding_id = hashlib.sha256(
        json.dumps(stable_key, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()[:20]
    return {
        "id": f"evergreen-{finding_id}",
        "type": finding_type,
        "severity": severity,
        "title": title,
        "satIds": sorted(sat_ids),
        "evidence": evidence,
        "links": {
            "sat": [
                SAT_MAP_URL.format(sat_id=quote(sat_id, safe=":"))
                for sat_id in sorted(set(sat_ids))
            ],
            "osm": [
                url
                for obj in (osm_objects or [])
                if (url := _osm_url(obj.get("type", ""), str(obj.get("id", ""))))
            ],
            "wikidata": [
                f"https://www.wikidata.org/wiki/{qid}"
                for qid in sorted(set(wikidata_ids or []))
                if WIKIDATA_ID.fullmatch(qid)
            ],
        },
    }


def _normalize_sat(data: dict | list[Identity] | list[dict]) -> tuple[dict[str, list[dict]], list[dict]]:
    features = data if isinstance(data, list) else data.get("features", [])
    records: dict[str, list[dict]] = defaultdict(list)
    invalid = []
    for feature in features:
        if isinstance(feature, Identity):
            props = {
                "id": feature.sat_id,
                "name": feature.name,
                "osm": feature.osm_id,
                "wikidata": feature.wikidata,
            }
        else:
            props = feature.get("properties", feature)
        sat_id = _sat_id(props.get("id") or props.get("satId") or props.get("sat_id"))
        if not sat_id or not SAT_POI_ID.fullmatch(sat_id):
            invalid.append({"source": "sat", "id": str(sat_id or ""), "reason": "invalid SAT POI identifier"})
            continue
        records[sat_id].append(
            {
                "name": props.get("name"),
                "osm": props.get("osm"),
                "wikidata": props.get("wikidata"),
            }
        )
    for sat_records in records.values():
        sat_records.sort(
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
        )
    return records, invalid


def _normalize_osm(data: dict) -> tuple[list[dict], list[dict]]:
    elements = data.get("elements")
    if elements is None:
        elements = data.get("features", [])
    objects = []
    invalid = []
    for element in elements:
        props = element.get("properties", {})
        tags = props.get("tags", element.get("tags", {}))
        ref = tags.get(OSM_TAG)
        if not isinstance(ref, str) or not ref.startswith("sat:poi:"):
            continue
        osm_type = element.get("type") or props.get("osm_type") or ""
        osm_id = element.get("id") or props.get("osm_id")
        if element.get("type") == "Feature":
            osm_type = props.get("osm_type") or ""
        entry = {
            "type": osm_type,
            "id": str(osm_id or ""),
            "satId": ref.strip(),
            "name": tags.get("name"),
        }
        if not SAT_POI_ID.fullmatch(ref.strip()):
            invalid.append(
                {"source": "osm", "satId": ref, "osm": entry, "reason": "invalid SAT POI reference"}
            )
        objects.append(entry)
    objects.sort(
        key=lambda item: (
            item["satId"],
            item["type"],
            item["id"],
            item.get("name") or "",
        )
    )
    return objects, invalid


def _normalize_wikidata(assertions: list[dict]) -> tuple[dict[str, list[str]], list[dict]]:
    by_sat: dict[str, list[str]] = defaultdict(list)
    invalid = []
    for assertion in assertions:
        qid = _wikidata_id(assertion.get("wikidata") or assertion.get("item"))
        raw_sat_id = assertion.get("satId") or assertion.get("sat_id")
        sat_id = _sat_id(raw_sat_id)
        if not qid or not WIKIDATA_ID.fullmatch(qid):
            invalid.append(
                {"source": "wikidata", "wikidata": str(assertion.get("wikidata") or assertion.get("item") or ""), "satId": raw_sat_id, "reason": "invalid Wikidata item identifier"}
            )
            continue
        if not sat_id or not SAT_POI_ID.fullmatch(sat_id):
            invalid.append(
                {"source": "wikidata", "wikidata": qid, "satId": str(raw_sat_id or ""), "reason": "invalid SAT POI identifier"}
            )
            continue
        by_sat[sat_id].append(qid)
    return by_sat, invalid


def build_findings(
    sat_data: dict | list[Identity] | list[dict],
    osm_data: dict,
    wikidata_assertions: list[dict],
) -> list[dict]:
    """Compare independent POI identity observations without prescribing edits."""
    sat_records, invalid_sat = _normalize_sat(sat_data)
    osm_objects, invalid_osm = _normalize_osm(osm_data)
    wikidata_by_sat, invalid_wikidata = _normalize_wikidata(wikidata_assertions)
    known_sat = set(sat_records)
    osm_by_sat: dict[str, list[dict]] = defaultdict(list)
    for obj in osm_objects:
        if SAT_POI_ID.fullmatch(obj["satId"]):
            osm_by_sat[obj["satId"]].append(obj)

    findings = []

    for sat_id, records in sorted(sat_records.items()):
        if len(records) > 1:
            findings.append(
                _finding(
                    "duplicate_sat_identifier",
                    [sat_id],
                    f"SAT POI identifier appears {len(records)} times in SAT",
                    "warning",
                    [{"source": "sat", "satId": sat_id, "recordCount": len(records)}],
                )
            )

    for sat_id, objects in sorted(osm_by_sat.items()):
        if sat_id not in known_sat:
            continue
        if len(objects) > 1:
            findings.append(
                _finding(
                    "duplicate_osm_reference",
                    [sat_id],
                    f"OSM reference occurs on {len(objects)} objects",
                    "review",
                    [{"source": "osm", **obj} for obj in objects],
                    osm_objects=objects,
                )
            )

    for sat_id, qids in sorted(wikidata_by_sat.items()):
        unique_qids = sorted(set(qids))
        if sat_id in known_sat and len(unique_qids) > 1:
            findings.append(
                _finding(
                    "duplicate_wikidata_reference",
                    [sat_id],
                    f"P14545 points to this SAT POI from {len(unique_qids)} Wikidata items",
                    "review",
                    [{"source": "wikidata", "wikidata": qid, "satId": sat_id} for qid in unique_qids],
                    wikidata_ids=unique_qids,
                )
            )

    for obj in osm_objects:
        if SAT_POI_ID.fullmatch(obj["satId"]) and obj["satId"] not in known_sat:
            invalid_osm.append(
                {
                    "source": "osm",
                    "satId": obj["satId"],
                    "osm": obj,
                    "reason": "SAT POI reference does not exist in the current SAT dataset",
                }
            )
    for sat_id, qids in wikidata_by_sat.items():
        if sat_id not in known_sat:
            invalid_wikidata.extend(
                {
                    "source": "wikidata",
                    "wikidata": qid,
                    "satId": sat_id,
                    "reason": "P14545 references a SAT POI absent from the current SAT dataset",
                }
                for qid in sorted(set(qids))
            )

    for sat_id, records in sorted(sat_records.items()):
        record = records[0]
        for source_record in records:
            raw_osm = source_record.get("osm")
            if raw_osm not in (None, "", False) and _osm_target(raw_osm) is None:
                invalid_sat.append(
                    {
                        "source": "sat",
                        "satId": sat_id,
                        "osm": raw_osm,
                        "reason": "invalid OSM target identifier in SAT",
                    }
                )
            raw_wikidata = source_record.get("wikidata")
            if raw_wikidata not in (None, "", False) and _wikidata_id(raw_wikidata) is None:
                invalid_sat.append(
                    {
                        "source": "sat",
                        "satId": sat_id,
                        "wikidata": raw_wikidata,
                        "reason": "invalid Wikidata target identifier in SAT",
                    }
                )
        sat_osm_targets = {
            _osm_target(item.get("osm"))
            for item in records
            if _osm_target(item.get("osm")) is not None
        }
        sat_wikidata_targets = {
            _wikidata_id(item.get("wikidata"))
            for item in records
            if _wikidata_id(item.get("wikidata"))
        }
        if len(sat_osm_targets) > 1:
            findings.append(
                _finding(
                    "conflicting_sat_mapping",
                    [sat_id],
                    "SAT records disagree about the OSM mapping",
                    "warning",
                    [{"source": "sat", "satId": sat_id, "osm": item.get("osm")} for item in records],
                )
            )
        if len(sat_wikidata_targets) > 1:
            findings.append(
                _finding(
                    "conflicting_sat_mapping",
                    [sat_id],
                    "SAT records disagree about the Wikidata mapping",
                    "warning",
                    [{"source": "sat", "satId": sat_id, "wikidata": item.get("wikidata")} for item in records],
                    wikidata_ids=sorted(sat_wikidata_targets),
                )
            )
        osm_objects_for_sat = osm_by_sat.get(sat_id, [])
        wd_items_for_sat = sorted(set(wikidata_by_sat.get(sat_id, [])))
        if not osm_objects_for_sat:
            findings.append(
                _finding(
                    "missing_osm_target",
                    [sat_id],
                    "No OSM object currently carries the SAT reference",
                    "review",
                    [
                        {"source": "sat", "satId": sat_id, "name": record.get("name")},
                        {"source": "osm", "tag": OSM_TAG, "matchingObjects": 0},
                    ],
                )
            )
        if not wd_items_for_sat:
            findings.append(
                _finding(
                    "missing_wikidata_target",
                    [sat_id],
                    "No Wikidata item currently asserts P14545 for this SAT POI",
                    "review",
                    [
                        {"source": "sat", "satId": sat_id, "name": record.get("name")},
                        {
                            "source": "wikidata",
                            "property": "P14545",
                            "matchingItems": 0,
                        },
                    ],
                )
            )

        sat_osm_targets = {
            target
            for item in records
            if (target := _osm_target(item.get("osm"))) is not None
        }
        if sat_osm_targets and osm_objects_for_sat:
            observed = {
                (obj["type"], obj["id"])
                for obj in osm_objects_for_sat
                if obj["id"].isdigit()
            }
            unmatched = [
                target
                for target in sat_osm_targets
                if observed
                and not any(
                    (not target[0] or not obj_type or target[0] == obj_type)
                    and target[1] == obj_id
                    for obj_type, obj_id in observed
                )
            ]
            if unmatched:
                findings.append(
                    _finding(
                        "conflicting_osm_mapping",
                        [sat_id],
                        "SAT's OSM mapping differs from the OSM object carrying its reference",
                        "warning",
                        [
                            *(
                                {"source": "sat", "satId": sat_id, "osm": item.get("osm")}
                                for item in records
                                if _osm_target(item.get("osm")) in unmatched
                            ),
                            *({"source": "osm", **obj} for obj in osm_objects_for_sat),
                        ],
                        osm_objects=osm_objects_for_sat,
                    )
                )

        unmatched_wikidata = {
            qid
            for item in records
            if (qid := _wikidata_id(item.get("wikidata")))
            and wd_items_for_sat
            and qid not in wd_items_for_sat
        }
        if unmatched_wikidata:
            findings.append(
                _finding(
                    "conflicting_wikidata_mapping",
                    [sat_id],
                    "SAT's Wikidata mapping differs from the items asserting P14545",
                    "warning",
                    [
                        *(
                            {"source": "sat", "satId": sat_id, "wikidata": qid}
                            for qid in sorted(unmatched_wikidata)
                        ),
                        *({"source": "wikidata", "satId": sat_id, "wikidata": qid} for qid in wd_items_for_sat),
                    ],
                    wikidata_ids=[*unmatched_wikidata, *wd_items_for_sat],
                )
            )

    for entry in [*invalid_sat, *invalid_osm, *invalid_wikidata]:
        sat_id = entry.get("satId") or entry.get("id")
        qid = _wikidata_id(entry.get("wikidata"))
        osm = entry.get("osm")
        findings.append(
            _finding(
                "invalid_reference",
                [sat_id] if isinstance(sat_id, str) and SAT_POI_ID.fullmatch(sat_id) else [],
                f"Invalid reference reported by {entry['source']}",
                "warning",
                [entry],
                osm_objects=[osm] if isinstance(osm, dict) else [],
                wikidata_ids=[qid] if qid else [],
            )
        )

    # Explicit references may point to an absent target even when they do not
    # appear in the reverse-link assertions.
    claims_by_osm: dict[tuple[str, str], set[str]] = defaultdict(set)
    claims_by_wikidata: dict[str, set[str]] = defaultdict(set)
    for sat_id, records in sat_records.items():
        for record in records:
            osm_target = _osm_target(record.get("osm"))
            if osm_target:
                claims_by_osm[osm_target].add(sat_id)
            qid = _wikidata_id(record.get("wikidata"))
            if qid:
                claims_by_wikidata[qid].add(sat_id)
    for (osm_type, osm_id), sat_ids in sorted(claims_by_osm.items()):
        if len(sat_ids) > 1:
            findings.append(
                _finding(
                    "conflicting_mapping",
                    sorted(sat_ids),
                    "Multiple SAT POIs claim the same OSM object",
                    "warning",
                    [{"source": "sat", "osm": f"{osm_type}:{osm_id}", "satIds": sorted(sat_ids)}],
                    osm_objects=[{"type": osm_type, "id": osm_id}],
                )
            )
    for qid, sat_ids in sorted(claims_by_wikidata.items()):
        if len(sat_ids) > 1:
            findings.append(
                _finding(
                    "conflicting_mapping",
                    sorted(sat_ids),
                    "Multiple SAT POIs claim the same Wikidata item",
                    "warning",
                    [{"source": "sat", "wikidata": qid, "satIds": sorted(sat_ids)}],
                    wikidata_ids=[qid],
                )
            )

    unique_findings = {finding["id"]: finding for finding in findings}
    return sorted(unique_findings.values(), key=lambda item: (item["type"], item["id"]))


def build_version(
    findings: list[dict],
    previous: dict | None,
    *,
    generated_at: str | None = None,
    sat_generated_at: str | None = None,
    quality_history: dict | None = None,
) -> dict:
    timestamp = _timestamp(generated_at)
    versions = list((previous or {}).get("versions", []))
    previous_findings = {
        finding["id"]
        for finding in (versions[-1].get("findings", []) if versions else [])
    }
    current_ids = {finding["id"] for finding in findings}
    version = {
        "version": len(versions) + 1,
        "generatedAt": timestamp,
        "satGeneratedAt": sat_generated_at,
        "summary": {
            "total": len(findings),
            "new": len(current_ids - previous_findings),
            "unchanged": len(current_ids & previous_findings),
            "resolved": len(previous_findings - current_ids),
        },
        "qualityHistory": _quality_history_reference(quality_history),
        "findings": findings,
    }
    versions.append(version)
    return {"schemaVersion": 1, "versions": versions}


def _quality_history_reference(history: dict | None) -> dict | None:
    if not history:
        return None
    versions = history.get("versions", [])
    if not versions:
        return None
    latest = versions[-1]
    return {
        "url": "sat_poi_quality_history.html",
        "version": latest.get("version"),
        "capturedAt": latest.get("capturedAt"),
        "satGeneratedAt": latest.get("generatedAt"),
        "totalPoi": latest.get("totalPoi"),
    }


def render_report(document: dict) -> str:
    if not document.get("versions"):
        return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evergreen identity findings · SAT Sync</title>
<style>
body{font:16px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#17202a}
</style>
</head>
<body>
<h1>Evergreen identity findings</h1>
<p>This read-only pilot compares SAT POI identifiers, OpenStreetMap references,
and Wikidata P14545. No live snapshot has been published yet.</p>
<p>Start a snapshot from <a href="https://github.com/salgo60/sat-sync/actions/workflows/evergreen-findings.yml">the manual GitHub Actions workflow</a>.
The workflow only publishes generated findings; it never edits SAT, OSM, Wikidata, or GitHub Issues.</p>
<p><a href="evergreen_findings.json">Versioned findings JSON</a> ·
<a href="EVERGREEN.md">How to report and review findings</a></p>
</body>
</html>
"""
    latest = document["versions"][-1]
    findings = latest["findings"]
    rows = []
    for finding in findings:
        sat_links = [
            f'<a href="{html.escape(url)}">SAT {html.escape(sat_id)}</a>'
            for sat_id, url in zip(finding["satIds"], finding["links"]["sat"])
        ]
        external_links = [
            f'<a href="{html.escape(url)}">OSM</a>'
            for url in finding["links"]["osm"]
        ] + [
            f'<a href="{html.escape(url)}">Wikidata {html.escape(url.rsplit("/", 1)[-1])}</a>'
            for url in finding["links"]["wikidata"]
        ]
        rows.append(
            "<tr>"
            f"<td>{html.escape(finding['severity'])}</td>"
            f"<td>{html.escape(finding['title'])}</td>"
            f"<td>{' · '.join(sat_links + external_links)}</td>"
            f"<td><details><summary>Evidence</summary><pre>{html.escape(json.dumps(finding['evidence'], ensure_ascii=False, indent=2))}</pre></details>"
            f"<code>{html.escape(finding['id'])}</code></td>"
            "</tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="4">No findings in this snapshot.</td></tr>'
    quality = latest.get("qualityHistory")
    quality_link = (
        f'<a href="{html.escape(quality["url"])}">SAT POI quality history'
        f' (version {html.escape(str(quality["version"]))})</a>'
        if quality
        else "No quality-history snapshot is available yet."
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Evergreen identity findings · SAT Sync</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#17202a}}
table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:.65rem;border-bottom:1px solid #d8dee4}}
th{{background:#f6f8fa}}a{{margin-right:.5rem}}code{{font-size:.85em}}.meta{{color:#57606a}}
</style>
</head>
<body>
<h1>Evergreen identity findings</h1>
<p>This read-only pilot compares SAT POI identifiers, OSM references, and Wikidata P14545.
Findings are observations for community review, not instructions to make matching edits.</p>
<p class="meta">Snapshot {latest["version"]} · generated {html.escape(latest["generatedAt"])} ·
{latest["summary"]["total"]} findings · <a href="evergreen_findings.json">versioned JSON</a> · {quality_link}</p>
<table><thead><tr><th>Review level</th><th>Finding</th><th>Source links</th><th>Stable ID</th></tr></thead>
<tbody>{body}</tbody></table>
<p>Review modelling differences and each source's own rules before reporting a suspected issue.
See <a href="EVERGREEN.md">how to report, review, and help resolve findings</a>.</p>
</body>
</html>
"""
