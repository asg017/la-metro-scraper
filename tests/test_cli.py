from click.testing import CliRunner

from conftest import insert, make_frame
from la_metro_scraper._queries import Db
from la_metro_scraper.cli import LINE_CODES, app


def test_unknown_feed_rejected_before_connecting():
    result = CliRunner().invoke(app, ["run", "--feeds", "tram"])
    assert result.exit_code != 0
    assert "unknown feed(s) tram" in result.output


def test_line_codes_cover_all_letter_lines():
    assert set(LINE_CODES) == set("ABCDEGJK")
    assert LINE_CODES["A"] == "801" and LINE_CODES["J"] == "910"


def test_stats_and_vehicles_commands(tmp_path):
    path = str(tmp_path / "t.sqlite")
    insert(Db(path), make_frame(vehicle_id="5817"), make_frame(vehicle_id="9001", ts=200))
    runner = CliRunner()

    result = runner.invoke(app, ["stats", "-o", path])
    assert result.exit_code == 0
    assert "positions 2  vehicles 2  trips 1  routes 1" in result.output

    result = runner.invoke(app, ["vehicles", "-o", path])
    assert result.exit_code == 0
    assert result.output.strip().endswith("2 vehicles")
    assert "5817" in result.output


def test_vehicles_within_filters(tmp_path):
    import json
    path = str(tmp_path / "t.sqlite")
    insert(Db(path),
           make_frame(vehicle_id="in", lat=0.5, lon=0.5),
           make_frame(vehicle_id="out", lat=40.0, lon=-70.0))
    boundary = tmp_path / "b.geojson"
    boundary.write_text(json.dumps({
        "type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
    }))
    result = CliRunner().invoke(app, ["vehicles", "-o", path, "--within", str(boundary)])
    assert result.exit_code == 0
    assert "in" in result.output and "out " not in result.output
    assert "1 vehicles" in result.output
