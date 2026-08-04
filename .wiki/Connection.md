# Connection & protocol behavior

## Handshake

Plain WebSocket upgrade, no authentication, no subprotocol, no query
parameters.

- **Origin is not enforced** (observed 2026-08-04): connecting with no
  `Origin` header, or with `Origin: https://example.com`, both succeed
  and receive frames. The live map sends
  `Origin: https://livemap.metro.net`; this scraper sends it anyway in
  case enforcement appears later.
- No client → server messages are needed (or known). The server starts
  pushing immediately after the upgrade.

## What comes back when

The server is a **snapshot re-broadcaster**, not a change stream:

1. **On connect** — a burst containing the entire active fleet, one
   frame per vehicle (observed: 1,722 of the 1,723 bus vehicles seen in
   75s arrived in the first burst; connect-to-first-frame ≈ 0.5s).
2. **Every ~2–5 seconds after that** — the full fleet again, whether or
   not anything changed (observed inter-burst gaps: bus mostly 2–4s,
   rail 2–8s). Bursts arrive as a rapid volley of frames, one vehicle
   per frame.

Consequences:

- **Duplicates dominate.** 76% of consecutive frames for a given bus
  carry an unchanged `vehicle.timestamp` — the vehicle simply hadn't
  reported new AVL data between bursts. Consumers must de-duplicate
  (this project uses `(feed, id, timestamp)` as the natural key).
- **No state is missed by a late joiner** — the next burst is a full
  snapshot, so reconnecting loses at most a few seconds of history.
- A vehicle that goes out of service silently disappears from
  subsequent bursts; there is no removal/tombstone message.

## Underlying AVL cadence

`vehicle.timestamp` (the vehicle's own report time) advances every
**~6s median** when it changes (bus p10–p90: 3–10s; rail p10–p90:
4–30s). So a consumer that de-duplicates sees roughly one genuine
update per vehicle per 6 seconds.

**Feed latency** (scraper receive time minus `vehicle.timestamp`):
averages ~10s for bus and ~6s for rail, with a long tail — gaps of
230s+ were observed, presumably vehicles with flaky cellular AVL
uplinks (guess).

## Volumes (weekday ~16:00, observed)

| Feed | Active vehicles | Frames/sec (avg) | Bytes/frame (typical) |
|------|-----------------|------------------|-----------------------|
| bus  | ~1,700          | ~600             | ~400 (in-service), ~190 (deadhead) |
| rail | ~160            | ~40              | same |

Overnight volumes will be far smaller (guess; not observed).

## Reconnection

Connections drop occasionally (observed over multi-hour scrapes).
Plain reconnect-on-close with no backoff has worked fine; the
on-connect snapshot makes recovery stateless. No server-side rate
limiting or connection dropping tied to client behavior was observed,
but nothing here is documented or guaranteed.
