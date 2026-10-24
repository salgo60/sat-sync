#!/usr/bin/env python3
"""Fetch current SAT/OSM/Wikidata assertions and publish read-only findings."""

import json
from datetime import UTC, datetime
from pathlib import Path

from fetch_postpass_data import fetch_postpass_data
from generate_poi_quality_history import fetch_pois
from sat_sync.engine import ReconciliationEngine
from sat_sync.evergreen import OSM_TAG, build_version, render_report
from sat_sync.sources.osm import OSMSource
from sat_sync.sources.sat import SATSource
from sat_sync.sources.wikidata import WikidataSource
from sat_sync.rules.evergreen_identity import EvergreenIdentityRule


FINDINGS_FILE = Path("evergreen_findings.json")
REPORT_FILE = Path("evergreen_report.html")
QUALITY_HISTORY_FILE = Path("sat_poi_quality_history.json")


def generate() -> dict:
    sat_data = fetch_pois()
    if not isinstance(sat_data.get("features"), list) or not sat_data["features"]:
        raise RuntimeError("SAT returned no POI features; refusing to publish incomplete findings")
    osm_data = fetch_postpass_data()
    if osm_data is None:
        raise RuntimeError("PostPass did not return OSM data; refusing to publish incomplete findings")
    features = osm_data.get("features", [])
    if not features:
        raise RuntimeError("PostPass returned no features; refusing to publish incomplete findings")
    if not any(
        isinstance((feature.get("properties", {}).get("tags") or {}).get(OSM_TAG), str)
        and (feature.get("properties", {}).get("tags") or {}).get(OSM_TAG, "").startswith("sat:poi:")
        for feature in features
    ):
        raise RuntimeError("PostPass returned no SAT POI references; refusing to publish incomplete findings")
    ids_to_resolve = {
        props["osm_id"]
        for feature in features
        for props in [feature.get("properties", {})]
        if not props.get("osm_type")
        and isinstance(props.get("osm_id"), int)
        and not isinstance(props.get("osm_id"), bool)
    }
    type_candidates = OSMSource().object_types(list(ids_to_resolve))
    for feature in features:
        props = feature.get("properties", {})
        osm_id = props.get("osm_id")
        candidates = type_candidates.get(osm_id, [])
        if not props.get("osm_type") and len(candidates) == 1:
            props["osm_type"] = candidates[0]
    wikidata_assertions = WikidataSource().identity_assertions()
    if not wikidata_assertions:
        raise RuntimeError("Wikidata returned no P14545 assertions; refusing to publish incomplete findings")

    previous = (
        json.loads(FINDINGS_FILE.read_text(encoding="utf-8"))
        if FINDINGS_FILE.exists()
        else None
    )
    quality_history = (
        json.loads(QUALITY_HISTORY_FILE.read_text(encoding="utf-8"))
        if QUALITY_HISTORY_FILE.exists()
        else None
    )
    metadata = sat_data.get("metadata") or {}
    identities = SATSource.identities_from_data(sat_data)
    engine = ReconciliationEngine(
        rules=[EvergreenIdentityRule(osm_data, wikidata_assertions)]
    )
    findings = engine.run(identities)
    document = build_version(
        findings,
        previous,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        sat_generated_at=metadata.get("generatedAt"),
        quality_history=quality_history,
    )
    FINDINGS_FILE.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_FILE.write_text(render_report(document), encoding="utf-8")
    latest = document["versions"][-1]
    print(
        f"Evergreen snapshot {latest['version']}: "
        f"{latest['summary']['total']} findings "
        f"({latest['summary']['new']} new, {latest['summary']['resolved']} resolved)"
    )
    return document


if __name__ == "__main__":
    generate()
