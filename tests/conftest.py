import json

import pytest

from la_metro_scraper._queries import Db


def make_frame(vehicle_id="5817", ts=100, route="55", trip_id="T1",
               lat=33.9, lon=-118.2, feed="bus", received_at=1000.0):
    """One buffered entry as the flusher hands it to the insert: a raw
    FeedEntity payload (in-service shape unless trip_id is None)."""
    entity = {
        "id": vehicle_id,
        "vehicle": {
            "position": {"latitude": lat, "longitude": lon, "speed": 1.0},
            "timestamp": str(ts),
            "vehicle": {"id": vehicle_id, "label": vehicle_id},
        },
        "route_code": route or "",
    }
    if trip_id is not None:
        entity["vehicle"] |= {
            "trip": {
                "tripId": trip_id, "startTime": "14:46:00",
                "startDate": "20260804", "scheduleRelationship": "SCHEDULED",
                "routeId": f"{route}-13201", "directionId": 1,
            },
            "currentStopSequence": 7,
            "currentStatus": "IN_TRANSIT_TO",
            "stopId": "30007",
        }
    return {"feed": feed, "received_at": received_at, "payload": json.dumps(entity)}


def insert(db, *frames):
    return db.insert_vehicle_positions(blobs=json.dumps(list(frames)))


@pytest.fixture
def db():
    return Db(":memory:")
