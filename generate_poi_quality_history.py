#!/usr/bin/env python3
"""
Skapar versionshistorik för SAT POI-kvalitet.

Ny snapshot sparas endast när metadata.generatedAt i pois.geojson har ändrats.
"""

import json
import urllib.request
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path


POIS_URL = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
OUTPUT_FILE = Path("sat_poi_quality_history.json")
DATA_JS_FILE = Path("sat_poi_quality_history_data.js")
USER_AGENT = "SAT-Sync/1.0 (+https://stockholmarchipelagotrail.com; salgo60@msn.com)"
FIELD_ALIASES = {
    "wheelchair": ["wheelchair"],
    "fee": ["fee", "charge"],
    "image": ["image", "photos"],
    "website": ["website"],
    "phone": ["phone", "contact:phone"],
    "menu": ["menu", "website:menu"],
    "social_media": ["social_media", "socialMedia", "contact:social_media"],
    "facebook": ["facebook", "contact:facebook"],
    "instagram": ["instagram", "contact:instagram"],
    "address": ["address"],
    "internet_access": ["internet_access"],
    "passBuyUrl": ["passBuyUrl"],
    "passSells": ["passSells"],
    "passStamps": ["passStamps"],
}


def fetch_pois() -> dict:
    req = urllib.request.Request(
        POIS_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return True


def same_as_prefix_count(properties: dict, prefix: str) -> int:
    same_as = properties.get("sameAs") or []
    if not isinstance(same_as, list):
        return 0
    return sum(1 for item in same_as if isinstance(item, str) and item.startswith(prefix))


def percentage(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((part / total) * 100, 2)


def has_any_value(properties: dict, aliases: list[str]) -> bool:
    for field in aliases:
        if has_value(properties.get(field)):
            return True
    return False


def load_existing_history() -> dict:
    if not OUTPUT_FILE.exists():
        return {"source": POIS_URL, "versions": []}
    return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))


def write_data_js(history: dict) -> None:
    payload = json.dumps(history, ensure_ascii=False)
    DATA_JS_FILE.write_text(
        f"window.SAT_POI_QUALITY_HISTORY = {payload};\n",
        encoding="utf-8",
    )


def create_snapshot(pois_data: dict, version_number: int) -> dict:
    features = pois_data.get("features") or []
    generated_at = ((pois_data.get("metadata") or {}).get("generatedAt")) or ""
    now_utc = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    category_counter = Counter()
    with_osm = 0
    with_wikidata = 0
    field_counter = Counter()
    section_totals = Counter()
    section_osm = Counter()
    section_wikidata = Counter()
    section_field_counter = {}

    for feature in features:
        props = feature.get("properties") or {}
        category_counter[(props.get("category") or "unknown")] += 1
        section = (props.get("section") or "unknown")
        section_totals[section] += 1

        if same_as_prefix_count(props, "osm:") > 0:
            with_osm += 1
            section_osm[section] += 1
        if same_as_prefix_count(props, "wikidata:") > 0 or has_value(props.get("wikidata")):
            with_wikidata += 1
            section_wikidata[section] += 1

        if section not in section_field_counter:
            section_field_counter[section] = Counter()
        for field, aliases in FIELD_ALIASES.items():
            if has_any_value(props, aliases):
                field_counter[field] += 1
                section_field_counter[section][field] += 1

    total_poi = len(features)
    categories = [
        {"category": category, "count": count}
        for category, count in sorted(category_counter.items(), key=lambda x: (-x[1], x[0]))
    ]

    field_coverage = {}
    for field in FIELD_ALIASES:
        count = field_counter[field]
        field_coverage[field] = {
            "count": count,
            "percent": percentage(count, total_poi),
        }

    section_coverage = []
    for section, total in sorted(section_totals.items(), key=lambda x: (-x[1], x[0])):
        row_fields = {}
        for field in FIELD_ALIASES:
            count = section_field_counter[section][field]
            row_fields[field] = {
                "count": count,
                "percent": percentage(count, total),
            }
        section_coverage.append(
            {
                "section": section,
                "totalPoi": total,
                "linkCoverage": {
                    "osm": {
                        "count": section_osm[section],
                        "percent": percentage(section_osm[section], total),
                    },
                    "wikidata": {
                        "count": section_wikidata[section],
                        "percent": percentage(section_wikidata[section], total),
                    },
                },
                "fieldCoverage": row_fields,
            }
        )

    return {
        "version": version_number,
        "generatedAt": generated_at,
        "capturedAt": now_utc,
        "totalPoi": total_poi,
        "linkCoverage": {
            "osm": {"count": with_osm, "percent": percentage(with_osm, total_poi)},
            "wikidata": {"count": with_wikidata, "percent": percentage(with_wikidata, total_poi)},
        },
        "fieldCoverage": field_coverage,
        "sectionCoverage": section_coverage,
        "categories": categories,
    }


def main():
    history = load_existing_history()
    versions = history.get("versions") or []

    data = fetch_pois()
    generated_at = ((data.get("metadata") or {}).get("generatedAt")) or ""
    if not generated_at:
        raise ValueError("metadata.generatedAt saknas i pois.geojson")

    latest_generated_at = versions[-1]["generatedAt"] if versions else None
    if latest_generated_at == generated_at:
        refreshed = create_snapshot(data, versions[-1]["version"]) if versions else None
        if refreshed is not None:
            refreshed["capturedAt"] = versions[-1].get("capturedAt", refreshed["capturedAt"])
            versions[-1] = refreshed
            history["versions"] = versions
            OUTPUT_FILE.write_text(
                json.dumps(history, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        write_data_js(history)
        print(f"⏭️ Ingen ny version: generatedAt oförändrad ({generated_at}), statistik uppdaterad")
        return

    snapshot = create_snapshot(data, len(versions) + 1)
    versions.append(snapshot)
    history["source"] = POIS_URL
    history["versions"] = versions

    OUTPUT_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_data_js(history)

    print(
        f"✅ Sparade version {snapshot['version']} "
        f"(generatedAt={snapshot['generatedAt']}, totalPoi={snapshot['totalPoi']})"
    )


if __name__ == "__main__":
    main()
