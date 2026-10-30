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

### Legitimate modelling differences

These examples show why a finding needs human interpretation. The links are
discussion and evidence, not a universal rule that every similar case is
already resolved.

| Case | Example and source | How to interpret it |
| --- | --- | --- |
| A village of cabins | The SAT discussion [“Saknas bra modell för stugby”](https://github.com/salgo60/Stockholm_Archipelago_Trail/issues/484) links two SAT POIs to two OSM ways within a cabin village. | A group of nearby cabins may be represented as individual buildings in OSM, while SAT's places to visit or stay can use a different grouping. Proximity or a shared name alone does not prove duplicate identity. |
| A bathing place | The discussion [“Badplatser ett modulerings problem ?!?!? OSM”](https://github.com/salgo60/Stockholm_Archipelago_Trail/issues/433) documents SAT bathing-place IDs alongside OSM `natural=beach` ways and `leisure=bathing_place` nodes, and raises `leisure=swimming_area` as a possible modelling approach. | A SAT bathing place can cover a beach and a designated swimming area, which OSM may map as separate physical or functional features. Treat a one-to-many relationship as a modelling possibility; do not merge IDs or call the features duplicates without checking their meanings. |
| A wind shelter with a firepit | SAT may show the shelter and its associated grill as one point, while OSM can map the shelter and firepit separately, or describe both functions on one object. | The SAT point can represent a visitor-facing place or amenity grouping rather than a single OSM feature. Different object counts are not, by themselves, evidence of a bad link. |
| A hotel with a restaurant | One SAT place may offer both accommodation and food, while OSM can represent those functions on one feature or on separate features. | Multiple categories or linked OSM objects can describe distinct services at the same venue. Check whether the mappings refer to the venue, a building, or a particular service. |

At the **concept level**, a maintained category crosswalk may use SKOS relations
such as `skos:closeMatch` or `skos:broadMatch` when the concepts are genuinely
similar or broader/narrower. Record the relation and its rationale; do not
assert equivalence where the meanings differ. At the **object level**, record
the actual SAT-to-OSM/Wikidata links and their evidence. SKOS concept mappings
do not establish that two individual features are the same, and
`owl:sameAs` should not be inferred from shared names, proximity, or a
one-to-many mapping.

Evergreen should keep reporting the observed source facts. A documented
modelling pattern can provide context for reviewers, but should not silently
hide a finding: exceptions and category mappings need explicit evidence and
community review.

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
