# SAT Sync Architecture

## Vision

SAT Sync is an identity reconciliation framework for loosely coupled open-data platforms.

It does not synchronize datasets.

Instead, it observes independent sources, reconciles identities, detects differences, and helps people communicate across communities.

The goal is to support collaboration without creating tight coupling between platforms.

---

# Design principles

## Every source remains authoritative

Every platform is the Source of Truth for its own domain.

Examples:

| Source | Owns |
|---------|------|
| SAT | Stockholm Archipelago Trail objects |
| OpenStreetMap | Geographic objects |
| Wikidata | Structured knowledge |
| Hjärtstartarregistret | Defibrillator registry |

SAT Sync never attempts to replace these systems.

---

## Loosely coupled architecture

External systems evolve independently.

Most of the time there is no communication between them.

Occasionally people communicate through:

- GitHub Issues
- OpenStreetMap Notes
- OSM changesets
- Wikidata edits
- SAT issue reports

SAT Sync supports these conversations.

---

## Observe rather than synchronize

SAT Sync never assumes all platforms should contain identical data.

Differences are expected.

Examples include:

- missing identifiers
- `ref:stockholmarchipelagetrail=unknown`
- Wikidata `some value`
- duplicate OSM objects
- different modelling granularity

These are observations—not necessarily errors.

---

# Architecture

```
              External Platforms

       SAT      OSM      Wikidata
         │        │          │
         └────────┼──────────┘
                  │
             Source Adapters
                  │
                  ▼
           Local Identity Cache
                  │
                  ▼
        Reconciliation Engine
                  │
                  ▼
               Findings
                  │
          Policy Evaluation
                  │
                  ▼
               Actions
                  │
     ┌────────────┼─────────────┐
     ▼            ▼             ▼
 Markdown     GitHub      OSM Notes
```

---

# Layers

## Sources

Sources know how to communicate with external systems.

Examples:

```
sources/
    sat.py
    osm.py
    wikidata.py
```

Sources translate external data into internal domain objects.

---

## Identity Cache

The cache stores normalized identities from all sources.

The cache is temporary.

External systems remain authoritative.

---

## Reconciliation Engine

The reconciliation engine compares observations from multiple sources.

It does not modify external systems.

Its only responsibility is producing Findings.

---

## Findings

A Finding represents an observation made by the reconciliation engine.

Examples:

- missing identifier
- duplicate object
- unknown identifier
- modelling difference

Findings are immutable.

They describe observations.

They do not prescribe actions.

---

## Policies

Policies determine how findings should be interpreted.

Examples:

- severity
- priority
- routing
- filtering

Policies contain configuration rather than business logic.

---

## Actions

Actions consume Findings.

Examples:

- generate Markdown reports
- create GitHub issues
- prepare OSM Notes
- export QuickStatements
- expose a REST API

Actions never change Findings.

---

# Future architecture

The current implementation calls Actions directly.

A future version may introduce an internal event bus.

```
Finding

↓

publish()

↓

Subscribers

↓

Markdown
GitHub
OSM Notes
Dashboard
REST API
```

Introducing an event bus should not require changes to the reconciliation engine.

---

# Philosophy

Linked data is not just about linked identifiers.

> **Linked data needs linked people.**

Software discovers differences.

Communities decide whether those differences represent:

- errors
- modelling choices
- different scope
- intentional divergence

SAT Sync exists to support those conversations.