-- schema: ./schema.sql

-- name: insert_vehicle_positions
-- Inserts a batch of vehicle position snapshots received over the
-- Metro GTFS-realtime WebSocket. :blobs is a JSON array; each element
-- is `{feed, received_at, payload}` where `payload` is the raw
-- FeedEntity JSON (as text). The CTE parses payload once per row so
-- the column expressions don't reparse it N times. Duplicate
-- `(feed, vehicle_id, observed_at)` snapshots are silently skipped via
-- the PK — Metro keeps re-broadcasting unchanged entities, so this is
-- the hot path.
with rows(feed, received_at, payload) as (
  select
    b.value ->> 'feed',
    b.value ->> 'received_at',
    b.value ->> 'payload'
  from json_each(:blobs) as b
)
insert or ignore into metro_vehicle_position (
  feed,
  vehicle_id,
  observed_at,
  received_at,
  latitude,
  longitude,
  bearing,
  speed,
  current_status,
  current_stop_sequence,
  stop_id,
  trip_id,
  route_id,
  direction_id,
  trip_start_date,
  trip_start_time,
  trip_schedule_relationship,
  vehicle_label,
  route_code
)
select
  rows.feed,
  rows.payload ->> '$.id',
  cast(rows.payload ->> '$.vehicle.timestamp' as integer),
  rows.received_at,
  rows.payload ->> '$.vehicle.position.latitude',
  rows.payload ->> '$.vehicle.position.longitude',
  rows.payload ->> '$.vehicle.position.bearing',
  rows.payload ->> '$.vehicle.position.speed',
  rows.payload ->> '$.vehicle.currentStatus',
  rows.payload ->> '$.vehicle.currentStopSequence',
  rows.payload ->> '$.vehicle.stopId',
  rows.payload ->> '$.vehicle.trip.tripId',
  rows.payload ->> '$.vehicle.trip.routeId',
  rows.payload ->> '$.vehicle.trip.directionId',
  rows.payload ->> '$.vehicle.trip.startDate',
  rows.payload ->> '$.vehicle.trip.startTime',
  rows.payload ->> '$.vehicle.trip.scheduleRelationship',
  rows.payload ->> '$.vehicle.vehicle.label',
  nullif(rows.payload ->> '$.route_code', '')
from rows
returning feed, vehicle_id;
