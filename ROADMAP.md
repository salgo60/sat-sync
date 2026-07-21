# sat-sync Roadmap

## Current status

### Core

- [x] Reconciliation engine
- [x] Rule framework
- [x] Finding model
- [x] Message localization
- [x] Unit tests
- [x] SAT adapter
- [x] Taginfo prototype

---

## Architecture

### Source abstraction

- [ ] Define generic Source contract
- [ ] Introduce source adapters
- [ ] Keep rules independent from adapters

### Domain model

- [ ] Identity
- [ ] Relationship
- [ ] Geometry
- [ ] Accommodation
- [ ] Media

### Identifier model

- [ ] Shared SAT identifier validation
- [ ] Common regex
- [ ] Identifier utilities

---

## Adapters

### Open data

- [ ] OSM
- [ ] Wikidata
- [ ] Taginfo HTTP API
- [ ] Overpass
- [ ] Commons

### Tourism

- [ ] Booking.com
- [ ] Airbnb
- [ ] Naturkartan

---

## Rules

### Identity

- [x] Missing Wikidata
- [x] Missing in OSM

Future

- [ ] Duplicate identifiers
- [ ] Invalid identifiers
- [ ] Broken links
- [ ] Missing images
- [ ] Missing accommodation
- [ ] Broken relationships

---

## Reporting

- [ ] CLI improvements
- [ ] Markdown report
- [ ] GitHub Issue exporter
- [ ] JSON output

---

## Policies

- [ ] Severity
- [ ] Ignore lists
- [ ] Source specific policies

---

## Vision

SAT Sync compares independent systems.

It does not synchronize them.

It produces observations that help communities collaborate.