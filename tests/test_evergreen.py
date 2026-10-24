import json
from pathlib import Path

from sat_sync.engine import ReconciliationEngine
from sat_sync.evergreen import build_findings, build_version, render_report
from sat_sync.rules.evergreen_identity import EvergreenIdentityRule
from sat_sync.sources.sat import SATSource


SAMPLE = Path(__file__).parent / "data" / "evergreen_sample.json"


def _findings():
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    return build_findings(data["sat"], data["osm"], data["wikidata"])


def test_build_findings_detects_missing_duplicate_conflicting_and_invalid_links():
    findings = _findings()
    types = {finding["type"] for finding in findings}

    assert {
        "missing_osm_target",
        "missing_wikidata_target",
        "duplicate_osm_reference",
        "duplicate_wikidata_reference",
        "conflicting_osm_mapping",
        "conflicting_wikidata_mapping",
        "invalid_reference",
    } <= types
    assert all(finding["id"].startswith("evergreen-") for finding in findings)
    assert len({finding["id"] for finding in findings}) == len(findings)


def test_finding_ids_are_stable_and_references_include_direct_links():
    first = _findings()
    second = _findings()
    assert [item["id"] for item in first] == [item["id"] for item in second]

    duplicate = next(item for item in first if item["type"] == "duplicate_osm_reference")
    assert duplicate["links"]["sat"] == [
        "https://map.stockholmarchipelagotrail.com/?sat:poi:alpha"
    ]
    assert set(duplicate["links"]["osm"]) == {
        "https://www.openstreetmap.org/way/101",
        "https://www.openstreetmap.org/node/202",
    }


def test_finding_ids_do_not_depend_on_source_record_order():
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    first_ids = [
        finding["id"]
        for finding in build_findings(data["sat"], data["osm"], data["wikidata"])
    ]
    reversed_ids = [
        finding["id"]
        for finding in build_findings(
            {"features": list(reversed(data["sat"]["features"]))},
            {"features": list(reversed(data["osm"]["features"]))},
            list(reversed(data["wikidata"])),
        )
    ]

    assert first_ids == reversed_ids


def test_evergreen_rule_runs_through_the_existing_reconciliation_engine():
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    identities = SATSource.identities_from_data(data["sat"])
    engine = ReconciliationEngine(
        [EvergreenIdentityRule(data["osm"], data["wikidata"])]
    )

    assert engine.run(identities) == build_findings(
        data["sat"], data["osm"], data["wikidata"]
    )


def test_piers_are_out_of_poi_scope_and_non_matching_objects_are_reported():
    findings = _findings()
    invalid = [
        evidence
        for finding in findings
        if finding["type"] == "invalid_reference"
        for evidence in finding["evidence"]
    ]
    assert any(item.get("satId") == "sat:poi:removed" for item in invalid)
    assert all(item.get("satId") != "sat:pier:example" for item in invalid)


def test_version_history_tracks_changes_and_existing_quality_history():
    findings = _findings()
    history = {"versions": [{"findings": [findings[0]]}]}
    document = build_version(
        findings,
        history,
        generated_at="2026-10-24T12:00:00Z",
        sat_generated_at="2026-10-23T08:00:00Z",
        quality_history={
            "versions": [
                {
                    "version": 7,
                    "capturedAt": "2026-10-23T09:00:00Z",
                    "generatedAt": "2026-10-22T08:00:00Z",
                    "totalPoi": 42,
                }
            ]
        },
    )
    latest = document["versions"][-1]
    assert latest["version"] == 2
    assert latest["summary"]["unchanged"] == 1
    assert latest["summary"]["new"] == len(findings) - 1
    assert latest["qualityHistory"]["version"] == 7
    assert "SAT POI quality history" in render_report(document)


def test_empty_report_is_an_explanatory_public_landing_page():
    assert "No live snapshot has been published yet." in render_report(
        {"schemaVersion": 1, "versions": []}
    )
