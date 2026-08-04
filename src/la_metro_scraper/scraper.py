"""Stream LA Metro bus + rail vehicle positions over WebSocket into SQLite."""
import asyncio
import json
import sqlite3
import time
import logging

import sqlite_tg
import websockets

from la_metro_scraper._queries import Db

log = logging.getLogger("la_metro_scraper")

FEEDS = {
    "bus":  "wss://api.metro.net/ws/LACMTA/vehicle_positions",
    "rail": "wss://api.metro.net/ws/LACMTA_Rail/vehicle_positions",
}
HEADERS = {
    "Origin": "https://livemap.metro.net",
    "User-Agent": "python-websockets/13",
}
FLUSH_INTERVAL = 1.0


class Stats:
    """Counters accumulated between bucketed reports.

    A frame is one WebSocket message (one FeedEntity). Frames drop for
    four reasons: `duplicate` (Metro re-broadcasts each vehicle's entity
    until it next changes, and the primary key ignores re-inserts),
    `off_route` (route_code not selected by --routes, or missing when it
    is set), `outside` (position outside the --within boundary, or
    missing when a boundary is set), and `invalid` (unparseable JSON).
    """

    def __init__(self) -> None:
        self.frames = self.inserted = self.off_route = self.outside = self.invalid = 0

    def take(self) -> tuple[int, int, int, int, int]:
        counts = (self.frames, self.inserted, self.off_route, self.outside, self.invalid)
        self.frames = self.inserted = self.off_route = self.outside = self.invalid = 0
        return counts


def describe(
    inserted: int, frames: int, duplicate: int, off_route: int, outside: int, invalid: int
) -> str:
    dropped = []
    if duplicate:
        dropped.append(f"{duplicate} duplicate")
    if off_route:
        dropped.append(f"{off_route} off-route")
    if outside:
        dropped.append(f"{outside} outside boundary")
    if invalid:
        dropped.append(f"{invalid} invalid")
    msg = f"inserted {inserted} of {frames} frames"
    return f"{msg} ({', '.join(dropped)})" if dropped else msg


class BoundaryFilter:
    """Point-in-boundary test evaluated by sqlite-tg on an in-memory db.

    The filter can't live in the insert statement in procedures.sql:
    solite's codegen validates against a stock SQLite that can't load the
    tg extension.
    """

    def __init__(self, boundary: str) -> None:
        self.boundary = boundary
        self.connection = sqlite3.connect(":memory:")
        self.connection.enable_load_extension(True)
        sqlite_tg.load(self.connection)
        self.connection.enable_load_extension(False)
        # Fail fast on an unparseable boundary, before any scraping starts.
        self.connection.execute("select tg_geom(?)", (boundary,))

    def within(self, points: list[tuple[float, float]]) -> set[int]:
        """Return the indexes of the (lon, lat) points inside the boundary."""
        rows = self.connection.execute(
            """
            select j.key from json_each(?) as j
            where tg_within(tg_point(j.value ->> 0, j.value ->> 1), tg_geom(?))
            """,
            (json.dumps(points), self.boundary),
        ).fetchall()
        return {key for (key,) in rows}


async def reader(feed: str, url: str, buf: list[tuple[str, float, str]]) -> None:
    async for ws in websockets.connect(url, additional_headers=HEADERS):
        log.info("%s feed connected", feed)
        try:
            async for msg in ws:
                text = msg if isinstance(msg, str) else msg.decode("utf-8", "replace")
                buf.append((feed, time.time(), text))
        except websockets.ConnectionClosed:
            log.warning("%s feed connection closed, reconnecting", feed)
            continue


async def flusher(
    db: Db,
    buf: list[tuple[str, float, str]],
    stats: Stats,
    routes: set[str] | None,
    boundary: BoundaryFilter | None,
    quiet: bool,
) -> None:
    while True:
        await asyncio.sleep(FLUSH_INTERVAL)
        if not buf:
            continue
        batch, buf[:] = buf[:], []
        invalid = off_route = outside = 0
        candidates = []
        for feed, ts, payload in batch:
            # Validate JSON; the SQL side parses it again, but catching
            # garbage here means a malformed frame can't poison the batch.
            try:
                parsed = json.loads(payload)
            except ValueError:
                invalid += 1
                continue
            # Route check before the boundary work — it's cheaper. A frame
            # with no route_code can't be shown to be on a selected route.
            if routes is not None and (parsed.get("route_code") or "").upper() not in routes:
                off_route += 1
                continue
            entry = {"feed": feed, "received_at": ts, "payload": payload}
            if boundary is None:
                candidates.append((entry, None))
                continue
            position = (parsed.get("vehicle") or {}).get("position") or {}
            lon, lat = position.get("longitude"), position.get("latitude")
            # A frame with no position can't be shown to be inside.
            if lon is None or lat is None:
                outside += 1
                continue
            candidates.append((entry, (lon, lat)))
        if boundary is None:
            entries = [entry for entry, _ in candidates]
        else:
            inside = boundary.within([point for _, point in candidates])
            entries = [entry for i, (entry, _) in enumerate(candidates) if i in inside]
            outside += len(candidates) - len(entries)
        inserted = 0
        if entries:
            with db:
                inserted = len(db.insert_vehicle_positions(blobs=json.dumps(entries)) or [])
        stats.frames += len(batch)
        stats.inserted += inserted
        stats.off_route += off_route
        stats.outside += outside
        stats.invalid += invalid
        log.log(
            logging.DEBUG if quiet else logging.INFO,
            describe(inserted, len(batch), len(entries) - inserted, off_route, outside, invalid),
        )


async def reporter(db: Db, stats: Stats, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        frames, inserted, off_route, outside, invalid = stats.take()
        if frames == 0:
            log.warning("no frames received in the last %.0fs", interval)
            continue
        positions, vehicles = db.connection.execute(
            "select (select count(*) from metro_vehicle_position),"
            " (select count(*) from metro_vehicle)"
        ).fetchone()
        duplicate = frames - inserted - off_route - outside - invalid
        log.info(
            "last %.0fs: %s | db: %s positions, %s vehicles",
            interval,
            describe(inserted, frames, duplicate, off_route, outside, invalid),
            f"{positions:,}", f"{vehicles:,}",
        )


async def run(
    db_path: str,
    boundary: str | None = None,
    bucket: float | None = None,
    feeds: set[str] | None = None,
    routes: set[str] | None = None,
) -> None:
    db = Db(db_path)
    bfilter = BoundaryFilter(boundary) if boundary is not None else None
    filters = [f for f, on in [("routes", routes), ("boundary", bfilter)] if on]
    log.info(
        "writing to %s%s", db_path,
        f" (only positions matching: {', '.join(filters)})" if filters else "",
    )
    buf: list[tuple[str, float, str]] = []
    stats = Stats()
    async with asyncio.TaskGroup() as tg:
        tg.create_task(flusher(db, buf, stats, routes, bfilter, quiet=bucket is not None))
        if bucket is not None:
            tg.create_task(reporter(db, stats, bucket))
        for feed, url in FEEDS.items():
            if feeds is None or feed in feeds:
                tg.create_task(reader(feed, url, buf))
