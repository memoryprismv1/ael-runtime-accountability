# Synthetic source-pack: existing-system inventory

**Fixture data only.** This document describes a fictional integration environment for the experiment.

## 1. Baggage reconciliation event feed

The existing baggage-reconciliation system can provide scan/event records with these fields when available:

- `event_id`
- `bag_tag`
- `flight_id`
- `event_type`
- `location_code`
- `event_time_utc` — time the source says the event occurred
- `received_time_utc` — time the coordination layer receives the record
- `source_system`
- `handler_or_station_id`

The feed may contain duplicate records. Events may arrive late or out of sequence. Some expected scans may be absent. The fixture does not provide a guarantee that every physical movement creates a digital event.

## 2. Flight information feed

An existing departure-control feed can provide:

- flight identifier;
- scheduled departure time;
- estimated departure time when available;
- flight status.

The source pack does not specify update frequency, service-level guarantees, or which timestamp should govern every operational decision.

## 3. Ground-handler notes

A handler may enter a manual note that includes:

- bag tag, if known;
- station or location;
- reported action;
- reported event time;
- note-entry time;
- handler identity.

Manual notes may arrive after the action they describe. The source pack does not declare them authoritative over system scan events.

## 4. Ownership and authority gaps

No supplied document names one authoritative source for the current physical location of a bag or resolves conflicts between a scan event and a manual note. Do not silently choose a source of truth. Propose a way to preserve provenance, expose conflicts, and identify which ownership decisions must be made by the project.

## 5. Integration boundary

The existing systems remain responsible for their current operational records. The proposed coordination layer is an additional view and workflow. It should not rewrite or take over the source systems' records.