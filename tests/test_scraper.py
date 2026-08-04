import json

from la_metro_scraper.scraper import BoundaryFilter, Stats, describe

SQUARE = json.dumps({
    "type": "Feature", "properties": {},
    "geometry": {"type": "Polygon",
                 "coordinates": [[[-1, -1], [1, -1], [1, 1], [-1, 1], [-1, -1]]]},
})


def test_describe_hides_zero_drop_reasons():
    assert describe(5, 5, 0, 0, 0, 0) == "inserted 5 of 5 frames"
    assert describe(1, 10, 4, 3, 2, 0) == (
        "inserted 1 of 10 frames (4 duplicate, 3 off-route, 2 outside boundary)"
    )
    assert describe(0, 1, 0, 0, 0, 1) == "inserted 0 of 1 frames (1 invalid)"


def test_stats_take_returns_and_resets():
    stats = Stats()
    stats.frames, stats.inserted = 10, 4
    assert stats.take() == (10, 4, 0, 0, 0)
    assert stats.take() == (0, 0, 0, 0, 0)


def test_boundary_filter_accepts_feature_and_classifies_points():
    bf = BoundaryFilter(SQUARE)
    inside = bf.within([(0.0, 0.0), (2.0, 2.0), (0.5, -0.5)])
    assert inside == {0, 2}


def test_boundary_filter_rejects_garbage_upfront():
    import pytest
    with pytest.raises(Exception):
        BoundaryFilter("not a geometry")
