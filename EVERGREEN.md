# Evergreen identity findings pilot

Evergreen is a **read-only pilot** for checking SAT POI identifiers across the
SAT POI GeoJSON, OpenStreetMap's `ref:stockholmarchipelagotrail` tag, and
Wikidata property P14545. The pilot intentionally starts with SAT POIs; SAT
piers and other SAT identifier families are outside its scope.

It reuses the SAT POI fetcher, the existing PostPass OSM fetcher, and the
repository's POI quality-history snapshots. A separate SPARQL request retrieves
all P14545 assertions, including items without Swedish labels. The audit checks
missing reverse links, duplicate source references, conflicting mappings, and
malformed or dangling SAT POI references. Findings contain evidence and stable
IDs, and each manually triggered run appends a timestamped JSON snapshot to
[`evergreen_findings.json`](evergreen_findings.json). The generated public
report is [`evergreen_report.html`](evergreen_report.html).
SAT GeoJSON is normalized by the existing SAT source adapter, and an Evergreen
rule is evaluated by the existing `ReconciliationEngine`.

The existing SAT Sync dashboards and reports primarily show current coverage,
field completeness, and OSM/SAT comparisons. The existing reconciliation
package has rule prototypes, but it does not publish a versioned three-source
finding history with stable finding IDs and direct source links. Evergreen adds
that small review surface; it does not replace those reports or the general
reconciliation architecture. The JSON snapshot links to the latest existing
SAT POI quality-history version for context and change over time.

## Interpretation and boundaries

Each platform remains authoritative for its own data. A missing match or a
duplicate reference is a prompt for review, not proof of an error. One SAT POI
may legitimately be represented by multiple OSM objects, and communities may
model places at different levels of detail. Check the source objects and their
context before reporting a finding.

The workflow only reads SAT, OSM, and Wikidata. It writes the generated report
and finding history to this repository. It does **not** edit SAT source data,
OSM, Wikidata, or GitHub Issues; it does not create or close issues.

## Run and review

1. From **Actions → Refresh Evergreen identity findings → Run workflow**, run
   the pilot manually. The workflow fetches current sources and commits only
   `evergreen_findings.json` and `evergreen_report.html`.
2. Review the published [findings report](https://salgo60.github.io/sat-sync/evergreen_report.html)
   and inspect each linked SAT, OSM, and Wikidata object. The versioned JSON is
   available [here](https://salgo60.github.io/sat-sync/evergreen_findings.json).
3. For a likely data problem, report it in the repository's GitHub Issues or
   the relevant community's normal discussion channel. Include the finding ID,
   its evidence, and links to the source records. Say explicitly when a
   modelling difference may explain the observation.
4. Anyone can review the evidence, add context, or help the relevant
   community decide whether and how to update its own source. Updates are made
   by that source's contributors, not by this workflow. A later Evergreen run
   records whether the finding remains or has disappeared.

## Local development

Run unit tests with `python -m pytest tests/test_evergreen.py`. They use the
small fixture in `tests/data/evergreen_sample.json`; tests do not contact or
modify any external service. Running `python3 generate_evergreen_report.py`
fetches live data and updates the two generated report files.
