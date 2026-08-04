# Bus vs rail feed differences

Same message schema, same server behavior; the fleets differ. All
numbers from the 2026-08-04 afternoon capture.

| | bus (`LACMTA`) | rail (`LACMTA_Rail`) |
|---|---|---|
| Active vehicles | ~1,700 | ~160 |
| Frames/sec | ~600 | ~40 |
| `id` format | fleet number (`"5817"`) | consist car list (`"1026-1228"`) |
| id stability | stable per vehicle | changes when cars re-couple |
| Deadhead share | 13% | 49% |
| `position.speed` | always present | ~50% of frames (mostly in-service only) |
| `position.bearing` | 43% of frames (moving only) | 22% of frames (moving only) |
| `routeId` format | `"55-13201"` (versioned) | `"803"` (bare) |
| `route_code` values | line numbers (`"2"`–`"910"`) | `"801"`–`"807"` |

The two id namespaces are disjoint (bus ids are 4–5 digit numbers, rail
ids contain dashes or are 4-digit car numbers) — but don't rely on
format; qualify vehicle ids by feed, as this project's schema does.

## Rail line codes

The feed identifies rail lines by numeric code, never by the
rider-facing letter. Mapping (verified live for all six rail lines;
G/J are BRT and appear on the **bus** feed):

| Letter | Code | Feed |
|--------|------|------|
| A | 801 | rail |
| B | 802 | rail |
| C | 803 | rail |
| E | 804 | rail |
| D | 805 | rail |
| K | 807 | rail |
| G | 901 | bus |
| J | 910 | bus |

(806 was the former L/Gold Line, since absorbed into A and E — guess
based on Metro history; never observed in captures.)

## The 49% rail deadhead share

Half the rail fleet reports without a trip assignment. Guess: stored
trains at yards keep their AVL powered, and rail operations
(single-tracking, gap trains) leave more units outside scheduled trips
than bus operations do. Deadhead rail frames also mostly lack `speed`,
so they're near-stationary yard/laid-up units. Filter them with
`route_code != ""` if you only want revenue service.
