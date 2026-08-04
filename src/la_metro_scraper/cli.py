import asyncio
import logging
import sqlite3
import time
from pathlib import Path

import click
import sqlite_tg

from la_metro_scraper import scraper

# Rider-facing letter lines -> the numeric route_code the feeds publish
# (verified live 2026-08-04). A-K are rail; G and J are BRT lines that
# ride the bus feed.
LINE_CODES = {
    "A": "801", "B": "802", "C": "803", "E": "804",
    "D": "805", "K": "807", "G": "901", "J": "910",
}

out_option = click.option(
    "-o", "--out", "out", default="vehicle_positions.sqlite", show_default=True,
    metavar="FILE.sqlite", help="SQLite database path.",
)
within_option = click.option(
    "--within", type=click.Path(exists=True, dir_okay=False, path_type=Path),
    metavar="FILE.geojson", default=None,
    help="Only include positions inside this GeoJSON geometry (Feature or "
    "bare geometry; WKT/WKB also accepted).",
)


@click.group()
def app() -> None:
    """Stream LA Metro vehicle positions into SQLite and query the result."""


@app.command()
@out_option
@click.option(
    "--feeds", default="bus,rail", show_default=True, metavar="FEEDS",
    help="Comma-separated feeds to subscribe to: bus, rail, or both.",
)
@click.option(
    "--routes", default=None, metavar="CODES",
    help="Comma-separated route codes to store (e.g. '2,720,A'). "
    "Letter lines (A B C D E G J K) are converted to the numeric "
    "codes the feeds publish (A=801 ... J=910). Frames for other "
    "routes — including deadheading vehicles with no route — are "
    "dropped before the database.",
)
@within_option
@click.option(
    "--bucket", type=float, default=None, metavar="SECONDS",
    help="Instead of logging every flush, log one aggregated line every "
    "SECONDS (plus running database totals).",
)
@click.option(
    "-v", "--verbose", is_flag=True,
    help="Log at DEBUG level (with --bucket, shows per-flush lines too).",
)
def run(out: str, feeds: str, routes: str | None, within: Path | None,
        bucket: float | None, verbose: bool) -> None:
    """Stream bus + rail vehicle positions into SQLite until interrupted.

    --within only stores positions inside the given GeoJSON geometry
    (Feature or bare geometry; WKT/WKB also accepted).
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # websockets logs a full traceback per reconnect at DEBUG; its INFO
    # events are covered by our own connect/close messages.
    logging.getLogger("websockets").setLevel(logging.WARNING)
    feed_set = {f.strip() for f in feeds.split(",") if f.strip()}
    if unknown := feed_set - scraper.FEEDS.keys():
        raise click.BadParameter(
            f"unknown feed(s) {', '.join(sorted(unknown))}; "
            f"choose from {', '.join(scraper.FEEDS)}", param_hint="--feeds",
        )
    route_set = (
        {LINE_CODES.get(c, c) for c in (r.strip().upper() for r in routes.split(",")) if c}
        if routes else None
    )
    try:
        asyncio.run(scraper.run(
            out,
            boundary=within.read_text() if within else None,
            bucket=bucket,
            feeds=feed_set,
            routes=route_set,
        ))
    except KeyboardInterrupt:
        pass


@app.command()
@out_option
@within_option
def vehicles(out: str, within: Path | None) -> None:
    """List the latest known position of each vehicle.

    --within only lists vehicles inside the given GeoJSON geometry
    (Feature or bare geometry; WKT/WKB also accepted).
    """
    conn = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
    # This query can't live in procedures.sql: solite's codegen validates
    # against a stock SQLite and has no way to load the tg extension, so
    # tg_* functions fail to prepare there.
    sql = """
        select feed, vehicle_id, vehicle_label, route_code,
               latitude, longitude, speed, observed_at
        from metro_vehicle
        where latitude is not null
    """
    params: list[str] = []
    if within is not None:
        conn.enable_load_extension(True)
        sqlite_tg.load(conn)
        conn.enable_load_extension(False)
        sql += " and tg_within(tg_point(longitude, latitude), tg_geom(?))"
        params.append(within.read_text())
    sql += " order by feed, cast(route_code as integer), route_code, vehicle_id"
    rows = conn.execute(sql, params).fetchall()
    now = time.time()
    for feed, vehicle_id, label, route_code, lat, lon, speed, observed_at in rows:
        age = max(0, int(now - observed_at))
        click.echo(
            f"{feed:<4} route {route_code or '-':>4}  vehicle {label or vehicle_id:<5} "
            f"{lat:>9.5f},{lon:>10.5f}  {speed if speed is not None else 0:5.1f} m/s  {age:>4}s ago"
        )
    suffix = f" within {within}" if within is not None else ""
    click.echo(f"{len(rows)} vehicles{suffix}")


@app.command()
@out_option
def stats(out: str) -> None:
    """Print row counts and time range for a scrape database."""
    conn = sqlite3.connect(f"file:{out}?mode=ro", uri=True)
    positions, vehicles, trips, routes, t_min, t_max = conn.execute(
        """
        select
          (select count(*) from metro_vehicle_position),
          (select count(*) from metro_vehicle),
          (select count(*) from metro_trip),
          (select count(*) from metro_route),
          (select min(received_at) from metro_vehicle_position),
          (select max(received_at) from metro_vehicle_position)
        """
    ).fetchone()
    click.echo(f"positions {positions}  vehicles {vehicles}  trips {trips}  routes {routes}")
    if t_min is not None:
        click.echo(f"received_at {t_min:.0f} .. {t_max:.0f} ({t_max - t_min:.0f}s span)")


if __name__ == "__main__":
    app()
