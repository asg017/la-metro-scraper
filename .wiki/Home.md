# LA Metro vehicle_positions WebSocket API

Unofficial documentation of the WebSocket feeds behind
[livemap.metro.net](https://livemap.metro.net), which this project
scrapes. Metro publishes no docs for these endpoints; everything here
is reverse-engineered from observation.

| Feed | URL |
|------|-----|
| bus  | `wss://api.metro.net/ws/LACMTA/vehicle_positions` |
| rail | `wss://api.metro.net/ws/LACMTA_Rail/vehicle_positions` |

Each WebSocket text frame is one JSON object: a GTFS-realtime
[FeedEntity](https://gtfs.org/documentation/realtime/reference/#message-feedentity)
with a `vehicle` (VehiclePosition) payload, rendered as protobuf-JSON,
plus one Metro extension field (`route_code`). There is no FeedMessage
envelope, no header, and no message other than these entities.

## Pages

- [[Connection]] — handshake, snapshot/re-broadcast behavior, cadence, volumes, latency
- [[Message-Schema]] — the JSON structure, the two entity shapes, presence rules
- [[Field-Reference]] — every field: type, format, observed values, guesses
- [[Bus-vs-Rail]] — how the two feeds differ

## Provenance

Derived 2026-08-04 from:

- a 75-second raw capture of both feeds (46,463 bus frames / 1,723
  vehicles; 3,054 rail frames / ~160 vehicles), taken ~16:15 local on a
  weekday afternoon;
- column statistics over a prior ~64k-row scrape;
- targeted connection experiments (e.g. Origin-header enforcement).

Facts are labeled **observed** (measured in the capture) or **guess**
(inference; reasoning given inline). Sample sizes are one afternoon of
one day — cadence and fleet-size numbers especially will vary by time
of day, and Metro can change any of this without notice.
