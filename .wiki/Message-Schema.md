# Message schema

Every frame is one JSON object with **exactly** these three top-level
keys (46,463/46,463 bus and 3,054/3,054 rail frames in the capture —
no exceptions, no extra keys ever observed):

```json
{ "id": "...", "vehicle": { ... }, "route_code": "..." }
```

`id`/`vehicle` are the GTFS-realtime FeedEntity fields in protobuf-JSON
form; `route_code` is a Metro extension. See [[Field-Reference]] for
per-field details.

## The two shapes

`vehicle` (a GTFS-rt VehiclePosition) comes in exactly two shapes, with
nothing in between — fields are either all present or all absent as a
block:

### In-service (87% of bus frames, 51% of rail)

The vehicle is assigned to a trip. All seven keys always appear
together:

```json
{
  "id": "5817",
  "vehicle": {
    "trip": {
      "tripId": "10055003011446-JUNE26",
      "startTime": "14:46:00",
      "startDate": "20260804",
      "scheduleRelationship": "SCHEDULED",
      "routeId": "55-13201",
      "directionId": 1
    },
    "position": {"latitude": 33.92568, "longitude": -118.23902, "speed": 0.0},
    "currentStopSequence": 61,
    "currentStatus": "IN_TRANSIT_TO",
    "timestamp": "1785885252",
    "stopId": "30007",
    "vehicle": {"id": "5817", "label": "5817"}
  },
  "route_code": "55"
}
```

`trip` itself always has exactly those six keys — never a subset.

### Deadhead / not in service (13% of bus frames, 49% of rail)

No trip assignment; the AVL unit is still reporting. Only three keys:

```json
{
  "id": "5820",
  "vehicle": {
    "position": {"latitude": 33.858665, "longitude": -118.279305, "speed": 0.0},
    "timestamp": "1785885224",
    "vehicle": {"id": "5820", "label": "5820"}
  },
  "route_code": ""
}
```

**`route_code == ""` if and only if `trip` is absent** — the
correlation was exact in all 49,517 captured frames. Either is a
reliable in-service test.

## Presence summary

| Path | In-service | Deadhead | Notes |
|------|-----------|----------|-------|
| `id` | always | always | |
| `route_code` | always (non-empty) | always (`""`) | |
| `vehicle.timestamp` | always | always | **string**, not number |
| `vehicle.position.latitude` / `.longitude` | always | always | |
| `vehicle.position.speed` | bus: always · rail: usually | bus: always · rail: rarely | see [[Bus-vs-Rail]] |
| `vehicle.position.bearing` | only while moving | only while moving | bearing ⟹ speed > 0 (observed, both feeds) |
| `vehicle.trip.*` (all six) | always | never | |
| `vehicle.currentStopSequence` | always | never | |
| `vehicle.currentStatus` | always | never | |
| `vehicle.stopId` | always | never | |
| `vehicle.vehicle.id` / `.label` | always | always | both always equal top-level `id` |

## GTFS-rt fields that never appear

From the standard VehiclePosition message: `occupancyStatus`,
`occupancyPercentage`, `congestionLevel`, `multiCarriageDetails` were
never observed. From TripDescriptor: `modifiedTrip`. The feed also
never sends `is_deleted`, `alert`, or `tripUpdate` entities — this
endpoint is vehicle positions only.
