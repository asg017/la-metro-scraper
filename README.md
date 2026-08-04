# la-metro-scraper

CLI for continuously streaming LA Metro bus + rail vehicle positions from the `api.metro.net`
GTFS-realtime WebSocket feeds into a SQLite database.

```sh
uv run la-metro-scraper run -o vehicle_positions.sqlite   # runs until ^C
uv run la-metro-scraper run -o vehicle_positions.sqlite \
    --within query.geojson          # only store positions inside the boundary
uv run la-metro-scraper run -o vehicle_positions.sqlite \
    --feeds rail --routes A,C       # rail feed only; A + C line only
uv run la-metro-scraper stats -o vehicle_positions.sqlite
uv run la-metro-scraper vehicles -o vehicle_positions.sqlite \
    --within query.geojson          # only list vehicles inside the boundary
```

Each WebSocket frame is one FeedEntity; frames are buffered and flushed
to SQLite once a second. `schema.sql` decomposes the payload into a
history table (`metro_vehicle_position`, deduped on
`(feed, vehicle_id, observed_at)`) with triggers maintaining
latest-state tables `metro_vehicle`, `metro_trip`, and `metro_route`.
The raw payload JSON is not stored — every field the feed sends has its
own column. The insert statement lives in `procedures.sql`. The typed
wrapper `_queries.py` is codegen'd from both SQL files — after editing
either, regenerate with `make` (runs `solite codegen` piped through
`tools/codegen.py`; solite is pinned to 0.0.1a36 because later
prereleases stopped embedding the schema in the generated setup).

## CLI Reference

### `run` — stream vehicle positions into SQLite until interrupted

Connects to the selected WebSocket feeds and continuously inserts
position snapshots. Databases are created in WAL mode. Filters
(`--feeds`, `--routes`, `--within`) compose with AND; filtered frames
are dropped before they reach the database.

| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--out FILE.sqlite` | `vehicle_positions.sqlite` | Database to stream into; created (in WAL mode) if missing. |
| `--feeds FEEDS` | `bus,rail` | Comma-separated feeds to subscribe to. Unselected feeds are never connected. |
| `--routes CODES` | all routes | Comma-separated route codes to store, e.g. `2,720,A`. Letter lines A B C D E G J K auto-convert to the numeric codes the feeds publish (A=801, B=802, C=803, E=804, D=805, K=807, G=901, J=910; G and J ride the bus feed). Deadheading vehicles (no route) are dropped. |
| `--within FILE.geojson` | no filter | Only store positions inside this geometry (GeoJSON Feature or bare geometry; WKT/WKB also work), tested per-frame with [sqlite-tg](https://github.com/asg017/sqlite-tg). Frames with no position are dropped. |
| `--bucket SECONDS` | off | Log one aggregated line per interval (with running db totals) instead of one line per flush. Warns if an interval passes with no frames. |
| `--verbose`, `-v` | off | DEBUG logging; with `--bucket`, also shows the per-flush lines. |

Log lines count every drop reason: `duplicate` (Metro re-broadcasts
unchanged positions; deduped by primary key), `off-route` (`--routes`),
`outside boundary` (`--within`), `invalid` (unparseable JSON).

### `vehicles` — list the latest known position of each vehicle

One line per vehicle from `metro_vehicle` (feed, route, fleet label,
lat/lon, speed, age of last observation), ordered by feed then route.
Opens the database read-only, so it's safe against a live `run`.

| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--out FILE.sqlite` | `vehicle_positions.sqlite` | Database to inspect. |
| `--within FILE.geojson` | no filter | Only list vehicles currently inside this geometry (same formats as `run --within`). |

### `stats` — print row counts and time range

One-shot summary: counts of positions, vehicles, trips, and routes,
plus the `received_at` time span of the stored history. Read-only.

| Flag | Default | Description |
|------|---------|-------------|
| `-o`, `--out FILE.sqlite` | `vehicle_positions.sqlite` | Database to inspect. |
