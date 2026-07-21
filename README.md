# SAT Sync

**SAT Sync is an identity reconciliation framework for loosely coupled open-data platforms.**

It helps maintain identity links across independent datasets such as:

- Stockholm Archipelago Trail (SAT)
- OpenStreetMap (OSM)
- Wikidata

Rather than copying or synchronizing data, SAT Sync builds a local identity cache and produces audit reports that make differences between platforms visible.

![Architecture](SATsync.png)

---

## Why?

Open-data platforms evolve independently.

Each has its own:

- community
- governance
- release cycle
- data model
- priorities

There is no central authority coordinating changes between them.

Most of the time there is **no communication at all**. Occasionally, contributors communicate through GitHub issues, OpenStreetMap changesets, Wikidata discussions or bug reports.

SAT Sync supports this ecosystem by helping contributors discover differences that deserve human attention.

---

## Design principles

SAT Sync never assumes that all sources should agree.

Every platform remains the **Source of Truth** for its own domain.

Instead of forcing consistency, SAT Sync preserves each platform's perspective while making differences explicit and auditable.

Examples include:

- a place exists in SAT but not yet in OpenStreetMap
- an OSM object is tagged `ref:stockholmarchipelagetrail=unknown`
- Wikidata uses **some value** because the identifier is known to exist but is not yet known
- one SAT object corresponds to multiple OSM objects
- platforms intentionally model different levels of detail (for example a hostel versus its toilets and showers)

These are not necessarily errors.

They are often the natural consequence of independent communities maintaining independent datasets.

---

## Architecture

```
             Independent Communities

      SAT          OSM          Wikidata
       │            │               │
       │            │               │
       └────────────┼───────────────┘
                    │
             Source Adapters
                    │
                    ▼
          Local Identity Cache
                    │
                    ▼
        Identity Reconciliation
                    │
                    ▼
             Audit Reports
                    │
                    ▼
      GitHub • OSM • Wikidata • SAT
      discussions and improvements
```

SAT Sync acts as an **identity broker** rather than a synchronization engine.

Its primary output is **knowledge**, not modified data.

---

## Goals

- Build and maintain a local identity cache.
- Preserve identity mappings across independent platforms.
- Detect missing, unknown and duplicate identities.
- Highlight differences in modelling.
- Produce audit reports for human review.
- Support collaboration between open-data communities.

---

## Philosophy

Linked data is not just about linked identifiers.

> **Linked data needs linked people.**

Software can discover inconsistencies.

People decide whether those differences represent:

- an error
- a modelling choice
- different scope
- or an intentional divergence.

SAT Sync exists to make those conversations easier.
