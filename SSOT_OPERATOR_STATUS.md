# 📊 SSOT (Single Source of Truth) Status Report

## 🎯 Vision
Establish OSM (OpenStreetMap) as the Single Source of Truth for SAT POI operator data, with Wikidata providing persistent identifiers and linked data integration.

## 📈 Current Coverage

**Total POIs**: 599
**POIs with operator**: 102 (17%)
**POIs with operator:wikidata**: 54 (9%)

**Goal**: Move from 17% to 100% operator coverage, with all operators linked to Wikidata.

## 🏢 Operators Found (sorted by frequency)

| Status | Operator | POIs | Wikidata Coverage | Link |
|--------|----------|------|-------------------|------|
| ❌ | (unknown) | 497 | 0% | No data |
| ⚠️ | Skärgårdsstiftelsen | 44 | 63.6% | [Q10670989](https://www.wikidata.org/wiki/Q10670989) |
| ✅ | Svenska Turistföreningen | 6 | 100.0% | [Q1492844](https://www.wikidata.org/wiki/Q1492844) |
| ❌ | Arholma Nord | 4 | 16.7% | TBD |
| ❌ | Arholma Handel | 3 | 0.0% | TBD |
| ✅ | Möja konsumtionsförening | 3 | 100.0% | [Q134459778](https://www.wikidata.org/wiki/Q134459778) |
| ✅ | Nåttarö gård och resort | 3 | 100.0% | [Q134691316](https://www.wikidata.org/wiki/Q134691316) |
| ❌ | Grinda Wärdshus AB | 2 | 0.0% | TBD |
| ❌ | Multiple other local operators | 26 | 0-16% | TBD |

**Key Insight**: 83% of POIs have **unknown operators** — this is the biggest opportunity for SSOT improvement.

## 🎯 Next Steps (SSOT Roadmap)

### Phase 1: Expose Current State ✅
- [x] Analyze SAT POIs and OSM operator tags
- [x] Create TODO-list with operator filtering
- [x] Identify gaps and missing Wikidata links
- [x] Create Issue #73 for crowdsourcing updates
- [x] Publish SSOT status report

### Phase 2: Crowdsource OSM Updates (IN PROGRESS)
- [ ] Fill in missing operator tags in OSM (83% of POIs)
- [ ] Add operator:wikidata links to Wikidata
- [ ] Validate against live OSM data
- [ ] Track completion in Issue #73 and related issues

### Phase 3: Sync & Validate
- [ ] Re-fetch all operator data from OSM
- [ ] Verify coverage reaches 80%+ with Wikidata links
- [ ] Document operator hierarchy (STF, Trafikverket, private, local, etc.)
- [ ] Create persistent operator dataset

### Phase 4: Integration
- [ ] Link operator data to quality metrics
- [ ] Enable operator-based filtering in SAT tools
- [ ] Create operator management dashboard
- [ ] Support operator API for third-party tools

## 💡 Call to Action

**For mappers**: Help us reach SSOT! Pick an operator from the list above and add `operator` and `operator:wikidata` tags in OSM.

**For data quality teams**: Use this report to prioritize operator coverage improvements.

**For API consumers**: This enables reliable operator-based queries once we reach 80%+ coverage.

## 📚 Key Concepts

### SSOT (Single Source of Truth)
- Operators are defined & maintained in **OpenStreetMap**
- **Wikidata** provides persistent identifiers (Q-numbers)
- **SAT tools** fetch from OSM as the authoritative source
- No duplicate definitions across systems
- Enables audit trails and versioning

### Why OpenStreetMap?
- ✅ Open & community-driven (no vendor lock-in)
- ✅ Federated model (volunteers worldwide)
- ✅ Full history & audit trail (changeset tracking)
- ✅ Versioning & rollback capabilities
- ✅ Wikidata integration for linked data
- ✅ OAuth support for automated updates

### Why Wikidata?
- ✅ Persistent, citable identifiers (Q-numbers)
- ✅ Structured data about organizations
- ✅ Links to other knowledge bases (Wikipedia, GND, etc.)
- ✅ Semantic queries possible
- ✅ FAIR data principles compliant
- ✅ Multi-language support

## 🔗 Related GitHub Issues
- [#71: Establish Operator as SSOT](https://github.com/salgo60/sat-sync/issues/71)
- [#72: Add operator data and filtering to TODO list](https://github.com/salgo60/sat-sync/pulls/72)
- [#73: Complete operator:wikidata for Archipelago Foundation POIs](https://github.com/salgo60/sat-sync/issues/73)

## 📖 Resources

### OpenStreetMap Documentation
- [Key:operator - OSM Wiki](https://wiki.openstreetmap.org/wiki/Key:operator)
- [Key:operator:wikidata - OSM Wiki](https://wiki.openstreetmap.org/wiki/Key:operator:wikidata)
- [API Documentation](https://wiki.openstreetmap.org/wiki/API_v0.6)
- [iD Editor](https://wiki.openstreetmap.org/wiki/ID)
- [JOSM Editor](https://wiki.openstreetmap.org/wiki/JOSM)

### Wikidata Resources
- [Wikidata Data Model](https://www.wikidata.org/wiki/Wikidata:Introduction)
- [Organization Items](https://www.wikidata.org/wiki/Q43229)
- [Creating New Items](https://www.wikidata.org/wiki/Help:Items)
- [SPARQL Query Tool](https://query.wikidata.org/)

### Quality & Linked Data
- [FAIR Data Principles](https://www.go-fair.org/fair-principles/)
- [Linked Data on the Web](https://www.w3.org/DesignIssues/LinkedData.html)
- [Data Provenance](https://www.w3.org/TR/prov-overview/)

## 📊 Quality Metrics

### Coverage Tiers
- 🔴 **0-25%**: Needs immediate attention
- 🟡 **25-75%**: In progress (target: Skärgårdsstiftelsen)
- 🟢 **75-100%**: Meets SSOT standard

### Success Criteria
- [ ] 80%+ POIs have `operator` tag
- [ ] 50%+ `operator` tags have `operator:wikidata`
- [ ] All major operators (>5 POIs) linked to Wikidata
- [ ] Changeset comments track SSOT updates

---

**Status**: Phase 1 & 2 in progress | Last updated: 2026-07-26 | POIs tracked: 599 | Operators: 41 unique

*Help us build the SSOT! 🗺️ Contribute via [GitHub Issues](https://github.com/salgo60/sat-sync/issues) or [OpenStreetMap](https://www.openstreetmap.org/)*
