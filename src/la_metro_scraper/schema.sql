pragma foreign_keys = on;

-- WAL survives in the database file once set, but running this on every
-- connect keeps a fresh database in WAL from its very first write.
pragma journal_mode = wal;

create table if not exists metro_vehicle_position(
  --! One row per vehicle position snapshot received over LA Metro's
  --! GTFS-realtime WebSocket feeds at api.metro.net. The upstream feed
  --! re-broadcasts each entity until the next change arrives, so
  --! de-duplicating on `(feed, vehicle_id, observed_at)` keeps the
  --! table compact. Each WebSocket frame is one FeedEntity, not the
  --! full FeedMessage envelope.

  --- Which Metro feed this row came from. 'bus' for LACMTA and 'rail'
  --- for LACMTA_Rail. Part of the natural key because the two feeds
  --- maintain disjoint vehicle_id namespaces.
  feed text not null,

  --- GTFS-realtime FeedEntity.id (and also vehicle.vehicle.id). Stable
  --- for a vehicle within a feed for the duration of its shift.
  vehicle_id text not null,

  --- Vehicle position timestamp from vehicle.timestamp, in unix seconds.
  --- This is the AVL-side reporting time, not when we received the frame.
  observed_at integer not null,

  --- Wallclock unix seconds when the WebSocket frame was received by
  --- the scraper. Useful for measuring feed latency
  --- (received_at - observed_at).
  received_at real not null,

  --- WGS84 latitude from vehicle.position.latitude.
  latitude real,

  --- WGS84 longitude from vehicle.position.longitude.
  longitude real,

  --- Compass bearing in degrees (0 = N, 90 = E) from
  --- vehicle.position.bearing. Often null on stopped vehicles.
  bearing real,

  --- Ground speed in meters per second (GTFS-realtime spec) from
  --- vehicle.position.speed.
  speed real,

  --- GTFS-realtime VehicleStopStatus enum string from
  --- vehicle.currentStatus: 'INCOMING_AT', 'STOPPED_AT', 'IN_TRANSIT_TO'.
  --- Null for vehicles not assigned to a trip.
  current_status text,

  --- Stop sequence index within the current trip, from
  --- vehicle.currentStopSequence. Observed 1-based (never 0).
  current_stop_sequence integer,

  --- GTFS stop_id the vehicle is at or approaching, from
  --- vehicle.stopId. Null off-trip.
  stop_id text,

  --- GTFS trip_id from vehicle.trip.tripId. Null for deadhead /
  --- not-in-service vehicles (whose payload has no `trip` object).
  trip_id text,

  --- GTFS route_id from vehicle.trip.routeId, e.g. '2-13196'. The
  --- suffix is Metro's schedule version tag.
  route_id text,

  --- Trip direction id (0 or 1) from vehicle.trip.directionId.
  direction_id integer,

  --- Calendar service date for the trip in 'YYYYMMDD' form, from
  --- vehicle.trip.startDate.
  trip_start_date text,

  --- Scheduled trip start time as 'HH:MM:SS', from
  --- vehicle.trip.startTime. May exceed 24h for trips that start
  --- after midnight relative to the service date.
  trip_start_time text,

  --- GTFS-realtime ScheduleRelationship enum from
  --- vehicle.trip.scheduleRelationship (e.g. 'SCHEDULED').
  trip_schedule_relationship text,

  --- Rider-facing fleet number from vehicle.vehicle.label.
  vehicle_label text,

  --- Metro-specific top-level 'route_code' field — usually the public
  --- line number ('2', '60', 'A', ...). Empty string normalized to null.
  --- Note: the raw payload JSON is NOT stored — as of 2026-08 every
  --- field the feed sends is decomposed into a column here (verified
  --- against 64k live frames), and the raw text tripled row size.
  route_code text,

  primary key (feed, vehicle_id, observed_at)
);

create index if not exists metro_vehicle_position_feed_time
  on metro_vehicle_position (feed, observed_at);

create table if not exists metro_vehicle(
  --! Current ("latest known") state of each vehicle, one row per
  --! (feed, vehicle_id). Maintained by an AFTER INSERT trigger on
  --! metro_vehicle_position: each newly-inserted history row upserts
  --! into this table, but only when the incoming observed_at is
  --! strictly newer — so out-of-order frames (e.g. a delayed WS
  --! redelivery of an older snapshot) can't make `metro_vehicle`
  --! stale. `first_observed_at` is set on first insert and never
  --! updated, so it doubles as a "first seen in this DB" timestamp.

  --- 'bus' or 'rail'. Part of the PK since the two feeds have
  --- disjoint vehicle_id namespaces.
  feed text not null,

  --- GTFS-realtime FeedEntity.id (also vehicle.vehicle.id, which is
  --- always identical to it on this feed).
  vehicle_id text not null,

  --- vehicle.timestamp from the most recent frame applied, in unix
  --- seconds. Updated only when an incoming frame has a strictly
  --- greater value.
  observed_at integer not null,

  --- First observed_at we ever saw for this (feed, vehicle_id). Set
  --- on insert; the trigger never overwrites it.
  first_observed_at integer not null,

  --- Wallclock unix seconds when the latest applied frame was
  --- received by the scraper.
  received_at real not null,

  --- Latest position. See metro_vehicle_position for column meanings.
  latitude real,
  longitude real,
  bearing real,
  speed real,
  current_status text,
  current_stop_sequence integer,
  stop_id text,
  trip_id text,
  route_id text,
  direction_id integer,
  trip_start_date text,
  trip_start_time text,
  vehicle_label text,
  route_code text,

  primary key (feed, vehicle_id)
);

create table if not exists metro_trip(
  --! Current state of each in-progress trip, one row per
  --! (feed, trip_id, trip_start_date). Maintained by the same
  --! observed_at-guarded trigger as `metro_vehicle`. trip_id alone
  --! is not unique — Metro reuses trip_ids across service days — so
  --! trip_start_date participates in the PK.

  --- 'bus' or 'rail'.
  feed text not null,

  --- GTFS trip_id from vehicle.trip.tripId.
  trip_id text not null,

  --- Calendar service date for the trip ('YYYYMMDD') from
  --- vehicle.trip.startDate. Part of the PK because trip_id is only
  --- unique within a service date.
  trip_start_date text not null,

  --- Vehicle currently operating the trip, per the latest frame.
  --- Trips occasionally swap vehicles mid-run (operator change /
  --- equipment failure), so this can change over the trip's life.
  vehicle_id text not null,

  --- GTFS route_id and direction this trip is on.
  route_id text,
  direction_id integer,

  --- Scheduled trip start time as 'HH:MM:SS' from
  --- vehicle.trip.startTime; may exceed 24h.
  trip_start_time text,

  --- vehicle.timestamp of the most recent frame applied to this trip.
  last_observed_at integer not null,

  --- Latest progress along the trip from vehicle.currentStopSequence.
  last_current_stop_sequence integer,

  --- Latest stop the vehicle was at or approaching.
  last_stop_id text,

  --- Latest VehicleStopStatus enum string.
  last_status text,

  primary key (feed, trip_id, trip_start_date)
);

create table if not exists metro_route(
  --! Discovery directory of every (feed, route_id) we've seen in the
  --! WebSocket stream, plus the rider-facing route_code Metro
  --! publishes alongside it. Populated by an `insert or ignore`
  --! trigger on metro_vehicle_position, so each route appears once
  --! the first time a vehicle is assigned to it. route_code can
  --! change for the same route_id across schedule versions; we keep
  --! the first one observed.

  --- 'bus' or 'rail'.
  feed text not null,

  --- GTFS route_id, e.g. '2-13196' (bus) or '801' (rail).
  route_id text not null,

  --- Rider-facing route_code from the top-level 'route_code' field
  --- ('2', '801', ...). May be null for trips whose frame has no
  --- route_code.
  route_code text,

  primary key (feed, route_id)
);

create trigger if not exists metro_vehicle_position_to_vehicle
after insert on metro_vehicle_position
begin
  insert into metro_vehicle (
    feed, vehicle_id, observed_at, first_observed_at, received_at,
    latitude, longitude, bearing, speed,
    current_status, current_stop_sequence, stop_id,
    trip_id, route_id, direction_id,
    trip_start_date, trip_start_time, vehicle_label, route_code
  )
  values (
    new.feed, new.vehicle_id, new.observed_at, new.observed_at, new.received_at,
    new.latitude, new.longitude, new.bearing, new.speed,
    new.current_status, new.current_stop_sequence, new.stop_id,
    new.trip_id, new.route_id, new.direction_id,
    new.trip_start_date, new.trip_start_time, new.vehicle_label, new.route_code
  )
  on conflict(feed, vehicle_id) do update set
    observed_at = excluded.observed_at,
    received_at = excluded.received_at,
    latitude = excluded.latitude,
    longitude = excluded.longitude,
    bearing = excluded.bearing,
    speed = excluded.speed,
    current_status = excluded.current_status,
    current_stop_sequence = excluded.current_stop_sequence,
    stop_id = excluded.stop_id,
    trip_id = excluded.trip_id,
    route_id = excluded.route_id,
    direction_id = excluded.direction_id,
    trip_start_date = excluded.trip_start_date,
    trip_start_time = excluded.trip_start_time,
    vehicle_label = excluded.vehicle_label,
    route_code = excluded.route_code
  where excluded.observed_at > metro_vehicle.observed_at;
end;

create trigger if not exists metro_vehicle_position_to_trip
after insert on metro_vehicle_position
when new.trip_id is not null
begin
  insert into metro_trip (
    feed, trip_id, trip_start_date, vehicle_id,
    route_id, direction_id, trip_start_time,
    last_observed_at, last_current_stop_sequence, last_stop_id, last_status
  )
  values (
    new.feed, new.trip_id, new.trip_start_date, new.vehicle_id,
    new.route_id, new.direction_id, new.trip_start_time,
    new.observed_at, new.current_stop_sequence, new.stop_id, new.current_status
  )
  on conflict(feed, trip_id, trip_start_date) do update set
    vehicle_id = excluded.vehicle_id,
    route_id = excluded.route_id,
    direction_id = excluded.direction_id,
    trip_start_time = excluded.trip_start_time,
    last_observed_at = excluded.last_observed_at,
    last_current_stop_sequence = excluded.last_current_stop_sequence,
    last_stop_id = excluded.last_stop_id,
    last_status = excluded.last_status
  where excluded.last_observed_at > metro_trip.last_observed_at;
end;

create trigger if not exists metro_vehicle_position_to_route
after insert on metro_vehicle_position
when new.route_id is not null
begin
  insert or ignore into metro_route (feed, route_id, route_code)
  values (new.feed, new.route_id, new.route_code);
end;
