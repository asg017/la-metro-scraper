# Field reference

Types are JSON types as they appear on the wire. "Observed" = measured
in the 2026-08-04 capture; "guess" = inference with reasoning.

## Top level

### `id` — string

GTFS-rt FeedEntity id. Doubles as the vehicle identifier (always equals
`vehicle.vehicle.id` — verified across all 49,517 frames).

- **Bus**: the fleet number, 4–5 digits (`"5817"`, `"10000"`).
- **Rail**: the car numbers of the train's consist joined by `-`, one
  to three cars (`"1008"`, `"1026-1228"`, `"1003-1019-1032"`).
  Consequence (observed): the id is only stable while the consist stays
  coupled — the same physical car appeared in two different ids within
  one afternoon (`1003-1019-1032`, `1003-1032-1209`). Treat rail ids as
  train-formation ids, not vehicle ids.

### `route_code` — string

Metro extension, not part of GTFS-rt. The **rider-facing** route
designator: bus line numbers (`"55"`, `"720"`), rail lines as their
numeric codes (`"801"`–`"807"`; see [[Bus-vs-Rail]] for the letter
mapping), BRT as `"901"` (G Line) / `"910"` (J Line).

- `""` exactly when the vehicle has no trip (observed, exact).
- Always equals the numeric prefix of `trip.routeId` when present
  (observed) — so it's derivable, but saves you the string surgery.

## `vehicle` (VehiclePosition)

### `timestamp` — **string** of unix seconds

When the vehicle's AVL unit generated this report — *not* when the
server sent the frame. Median ~6s between changes per vehicle. Beware
the type: it's `"1785885252"`, a string, unlike every other numeric
field. (Protobuf-JSON renders 64-bit ints as strings — guess at the
cause, but consistent with `directionId`, a 32-bit int, arriving as a
JSON number.)

### `position.latitude`, `position.longitude` — number

WGS84 degrees, ~6 decimal places (≈0.1 m quantization). Always present.

### `position.speed` — number

Ground speed in **meters per second** (GTFS-rt spec; consistent with
observed values — bus max 29.5 m/s ≈ 66 mph). `0.0` while stopped
(38% of bus frames). Bus: always present. Rail: present in ~97% of
in-service frames and ~1% of deadhead frames — rail speed apparently
comes from the trip-tracking system rather than the AVL unit (guess).

### `position.bearing` — number

Compass heading in degrees, 0–360, 0 = north. Present **only while
moving**: in both feeds, every frame with `bearing` had `speed > 0`
(observed; the converse doesn't hold — many moving bus frames lack
bearing). Absence means "unknown/stationary", not "north".

### `currentStatus` — string enum

GTFS-rt VehicleStopStatus relative to `stopId`. Observed values and
shares (bus): `IN_TRANSIT_TO` 47%, `STOPPED_AT` 53%. The third GTFS-rt
value `INCOMING_AT` ("about to arrive") was **never observed** in this
capture — either unused by Metro's AVL or rare (guess).

### `currentStopSequence` — number (int)

Position of `stopId` within the trip's stop sequence (GTFS
`stop_times.stop_sequence`). Observed minimum is 1 across all 42k
in-service frames — never 0 — so it's 1-based in practice. Observed up
to 61+ on long bus locals.

### `stopId` — string

GTFS stop id (join key into Metro's static GTFS `stops.txt`) the
vehicle is stopped at or heading to, per `currentStatus`.

### `vehicle.id`, `vehicle.label` — string

Inner VehicleDescriptor. Both always equal the top-level `id` in both
feeds (observed, all frames) — no extra information today, but `label`
is nominally the rider-facing variant and could diverge someday.

## `vehicle.trip` (TripDescriptor)

Always all six fields or absent entirely.

### `tripId` — string

GTFS trip id plus a schedule-version suffix after `-`
(`"10055003011446-JUNE26"` — the JUNE26 tag is Metro's
schedule-shakeup name, guess: June 2026). Join key into the matching
version of Metro's static GTFS.

### `routeId` — string

GTFS route id. Bus: `"<line>-<version>"` (`"55-13201"`; 13201 appears
to be a numeric schedule-version tag — it was uniform across all
routes in the capture). Rail: bare line code (`"803"`), no suffix.

### `directionId` — number, 0 or 1

GTFS direction. Which compass direction each value means varies by
route (per GTFS semantics; not derivable from the feed alone).

### `startDate` — string `YYYYMMDD`, `startTime` — string `HH:MM:SS`

The trip's service date and scheduled start. Together with `tripId`
they uniquely identify a trip instance (Metro reuses trip ids across
days). Times past midnight on the service date may exceed `24:00:00`
per GTFS convention — not observed in this afternoon capture, but the
original scraper's data model allows it.

### `scheduleRelationship` — string enum

Only `"SCHEDULED"` was ever observed (all 42,073 in-service frames).
GTFS-rt also defines `ADDED`, `UNSCHEDULED`, `CANCELED`, `DUPLICATED`;
whether Metro ever emits them is unknown.
