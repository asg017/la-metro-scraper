from conftest import insert, make_frame


def test_insert_decomposes_payload(db):
    result = insert(db, make_frame())
    assert [(r.feed, r.vehicle_id) for r in result] == [("bus", "5817")]
    row = db.connection.execute(
        "select feed, vehicle_id, observed_at, latitude, route_id, route_code,"
        " trip_id, current_status, stop_id from metro_vehicle_position"
    ).fetchone()
    assert row == ("bus", "5817", 100, 33.9, "55-13201", "55", "T1", "IN_TRANSIT_TO", "30007")


def test_duplicate_snapshot_ignored(db):
    insert(db, make_frame(ts=100))
    assert insert(db, make_frame(ts=100)) == []
    assert insert(db, make_frame(ts=101)) != []


def test_deadhead_frame_has_null_trip_and_route(db):
    insert(db, make_frame(trip_id=None, route=None))
    trip_id, route_code = db.connection.execute(
        "select trip_id, route_code from metro_vehicle_position"
    ).fetchone()
    assert trip_id is None and route_code is None


def test_vehicle_trigger_keeps_latest_and_guards_out_of_order(db):
    insert(db, make_frame(ts=200, lat=34.0))
    insert(db, make_frame(ts=150, lat=33.0))  # stale frame arrives late
    observed_at, first, lat = db.connection.execute(
        "select observed_at, first_observed_at, latitude from metro_vehicle"
    ).fetchone()
    assert (observed_at, lat) == (200, 34.0)  # not clobbered by the stale frame
    assert first == 200  # first_observed_at fixed at first insert
    insert(db, make_frame(ts=300, lat=35.0))
    assert db.connection.execute(
        "select observed_at, first_observed_at from metro_vehicle"
    ).fetchone() == (300, 200)


def test_trip_and_route_triggers(db):
    insert(db, make_frame(vehicle_id="1", trip_id="T1", route="55"))
    insert(db, make_frame(vehicle_id="2", ts=200, trip_id="T1", route="55"))  # vehicle swap
    assert db.connection.execute(
        "select vehicle_id, last_observed_at from metro_trip"
    ).fetchall() == [("2", 200)]
    assert db.connection.execute(
        "select feed, route_id, route_code from metro_route"
    ).fetchall() == [("bus", "55-13201", "55")]


def test_database_created_in_wal_mode(tmp_path, db):
    from la_metro_scraper._queries import Db
    file_db = Db(str(tmp_path / "t.sqlite"))
    assert file_db.connection.execute("pragma journal_mode").fetchone() == ("wal",)
