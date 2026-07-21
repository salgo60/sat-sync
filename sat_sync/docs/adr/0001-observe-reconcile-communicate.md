# ADR 0001

## Title

Observe → Reconcile → Communicate

## Status

Accepted

## Context

SAT, OpenStreetMap and Wikidata are independently maintained systems.

SAT Sync should not modify them automatically.

## Decision

SAT Sync separates the process into three stages:

1. Observe
2. Reconcile
3. Communicate

The reconciliation engine produces Findings.

Findings may later be communicated through reports, GitHub Issues, OSM Notes or other integrations.

## Consequences

The reconciliation engine remains independent of output formats and communication channels.