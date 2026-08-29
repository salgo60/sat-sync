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
from typing import Optional


POIS_URL = "https://map.stockholmarchipelagotrail.com/data/geojson/pois.geojson"
OUTPUT_FILE = Path("sat_poi_quality_history.json")
DATA_JS_FILE = Path("sat_poi_quality_history_data.js")
USER_AGENT = "SAT-Sync/1.0 (+https://stockholmarchipelagotrail.com; salgo60@msn.com)"
HEADERS = {"User-Agent": "sat-sync-generator/1.0 (+https://github.com/salgo60/sat-sync)"}
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
    "opening_hours": ["opening_hours", "openingHours"],
    "description": ["description"],
    "booking_url": ["bookingUrl", "booking_url", "reservationUrl", "reservation_url"],
    "access": ["access"],
    "fee_or_access": ["fee", "charge", "access"],
}

# Fält som alltid spåras per POI
POI_SNAPSHOT_FIELDS = [
    "osm", "wikidata", "image", "website", "wheelchair",
    "opening_hours", "fee", "description", "passBuyUrl", "booking_url",
]

# Kategori-specifika obligatoriska fält (för completeness score)
CATEGORY_REQUIRED_FIELDS: dict[str, list[str]] = {
    "lodging":    ["osm", "wikidata", "image", "website", "opening_hours", "description", "passBuyUrl"],
    "food":       ["osm", "wikidata", "image", "website", "opening_hours", "phone", "description"],
    "shop":       ["osm", "wikidata", "image", "website", "opening_hours", "phone"],
    "attraction": ["osm", "wikidata", "image", "website", "description"],
    "beach":      ["osm", "wikidata", "image", "description"],
    "firepit":    ["osm", "image", "description"],
    "shelter":    ["osm", "wikidata", "image", "description"],
    "harbour":    ["osm", "image", "website", "fee"],
    "toilet":     ["osm", "image", "fee", "wheelchair", "access"],
    "water":      ["osm", "image", "fee", "access"],
    "shower":     ["osm", "image", "fee", "access"],
    "sauna":      ["osm", "image", "website", "fee", "description"],
    "rental":     ["osm", "wikidata", "image", "website", "description"],
    "viewpoint":  ["osm", "image"],
    "lighthouse": ["osm", "wikidata", "image"],
    "rowboat":    ["osm", "image", "fee", "opening_hours"],
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


def extract_osm_ref(same_as: list) -> Optional[tuple[str, int]]:
    """Extract OSM type (node/way/relation) and ID from sameAs.
    Handles both osm:type:id format and openstreetmap.org URLs.
    Returns (type, id) or None if not found."""
    if not same_as:
        return None
    for ref in same_as:
        if isinstance(ref, str):
            # Handle osm:node:123456 format
            if ref.startswith("osm:"):
                parts = ref.split(":")
                if len(parts) == 3:
                    osm_type = parts[1]
                    try:
                        osm_id = int(parts[2])
                        if osm_type in ("node", "way", "relation"):
                            return (osm_type, osm_id)
                    except ValueError:
                        pass
            # Handle openstreetmap.org/node/123456 format
            elif "openstreetmap.org" in ref:
                parts = ref.split("/")
                if len(parts) >= 2:
                    osm_type = parts[-2]
                    try:
                        osm_id = int(parts[-1])
                        if osm_type in ("node", "way", "relation"):
                            return (osm_type, osm_id)
                    except (ValueError, IndexError):
                        pass
    return None


def fetch_osm_operator(osm_type: str, osm_id: int) -> Optional[str]:
    """Fetch operator or brand tag from OSM API."""
    try:
        url = f"https://api.openstreetmap.org/api/0.6/{osm_type}/{osm_id}.json"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tags = data.get("elements", [{}])[0].get("tags", {})
            return tags.get("operator") or tags.get("brand")
    except Exception:
        return None


def extract_poi_snapshot(props: dict) -> dict:
    """Bygg en kompakt per-POI snapshot med nyckelattribut (1 = finns, 0 = saknas)."""
    slug = props.get("slug") or props.get("id") or ""
    name = props.get("name") or props.get("title") or slug
    section = props.get("section") or "unknown"
    category = props.get("category") or "unknown"

    # Koordinater hämtas i create_snapshot via feature.geometry
    has_osm = same_as_prefix_count(props, "osm:") > 0
    has_wikidata = same_as_prefix_count(props, "wikidata:") > 0 or has_value(props.get("wikidata"))

    result: dict = {
        "id": slug,
        "name": name,
        "section": section,
        "category": category,
        "osm": 1 if has_osm else 0,
        "wikidata": 1 if has_wikidata else 0,
    }

    # Alla spårade fält (utom osm/wikidata som hanteras ovan)
    for field in ["image", "website", "wheelchair", "opening_hours", "fee", "description",
                  "passBuyUrl", "booking_url", "phone", "access"]:
        aliases = FIELD_ALIASES.get(field, [field])
        result[field] = 1 if has_any_value(props, aliases) else 0

    # Completeness score baserat på kategori-specifika krav
    required = CATEGORY_REQUIRED_FIELDS.get(category, ["osm", "wikidata", "image", "website"])
    filled = sum(result.get(f, 0) for f in required)
    result["completeness"] = round(filled / len(required) * 100) if required else 0
    result["required_fields"] = required

    return result


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
    with_operator = 0
    operator_counter = Counter()
    field_counter = Counter()
    section_totals = Counter()
    section_osm = Counter()
    section_wikidata = Counter()
    section_operator = Counter()
    section_field_counter = {}
    poi_snapshots = []

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

        # Check operator from OSM tags
        same_as = props.get("sameAs") or []
        osm_ref = extract_osm_ref(same_as)
        operator = None
        if osm_ref:
            operator = fetch_osm_operator(osm_ref[0], osm_ref[1])
        if has_value(operator):
            with_operator += 1
            section_operator[section] += 1
            operator_counter[operator] += 1

        if section not in section_field_counter:
            section_field_counter[section] = Counter()
        for field, aliases in FIELD_ALIASES.items():
            if has_any_value(props, aliases):
                field_counter[field] += 1
                section_field_counter[section][field] += 1

        # Per-POI snapshot
        poi_snap = extract_poi_snapshot(props)
        coords = (feature.get("geometry") or {}).get("coordinates")
        if coords and len(coords) >= 2:
            poi_snap["lon"] = round(coords[0], 6)
            poi_snap["lat"] = round(coords[1], 6)
        poi_snapshots.append(poi_snap)

    total_poi = len(features)
    categories = [
        {"category": category, "count": count}
        for category, count in sorted(category_counter.items(), key=lambda x: (-x[1], x[0]))
    ]

    # Operator distribution (top 20 by count)
    operator_distribution = [
        {"operator": op, "count": count}
        for op, count in sorted(operator_counter.items(), key=lambda x: (-x[1], x[0]))[:20]
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
                    "operator": {
                        "count": section_operator[section],
                        "percent": percentage(section_operator[section], total),
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
            "operator": {"count": with_operator, "percent": percentage(with_operator, total_poi)},
        },
        "fieldCoverage": field_coverage,
        "sectionCoverage": section_coverage,
        "operatorDistribution": operator_distribution,
        "categories": categories,
        "poiSnapshots": poi_snapshots,
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
