# Route network, partial-route search and per-leg fares

Status: **Phase 1 built** on branch `feature/route-network` (2026-11-04). Phases 2 and 3 not started.
Replaces the fixed `city_pairs` model for posting, search and fares.

## Decisions taken (2026-11-04)

| # | Decision |
| --- | --- |
| D1 | Use a route network we own (places, legs, named routes) for distance, matching and fares. No maps API in the posting or search path. |
| D2 | Use **Mappls (MapmyIndia) place search** as a dropdown for the *exact pickup point* (and drop point). Keys stay on the API server. |
| D3 | Leg distances must be measured, not estimated: computed once per leg from Mappls routing when the leg is set up, then checked by the team. Never computed per search. |
| D4 | Tolls are confirmed by the team, and drivers can report the tolls they actually paid after a completed trip. Ops approves changes. |
| D5 | Fare cap stays **15% above the per-leg cost share** (current hard rule 2). The stricter cap in PR #3 is not adopted. |
| D6 | Advance stays a **percentage of the fare** (no ₹300 minimum or ₹1,000 maximum) and is **optional for the driver**: they can switch it off per ride. Such rides show a clear "No advance" label. |

## Concepts

- **Place**: a town or landmark on the corridor (`Pune`, `Ahilyanagar`, `Chhatrapati Sambhajinagar`, `Jalna`, `Wardha`, `Yavatmal`, `Wani`, `Chandrapur`, …). Has aliases (`Aurangabad`), a Mappls eLoc and coordinates.
- **Leg**: a road segment between two neighbouring places on a route. Stores `distance_km` (measured, D3), `tolls_inr` (confirmed, D4), `typical_minutes`, `source`, `verified_by`, `verified_at`. Directional (A→B and B→A are separate rows; tolls often differ).
- **Route**: an ordered list of legs with a name, e.g. *Pune → Chandrapur via Samruddhi and Wardha*, *Pune → Chandrapur via Jalna and Yavatmal*. A route's total distance is the sum of its legs.
- **Leg data is versioned** like `policy_versions`: a ride stores the leg version it was priced on, so later corrections never change an existing ride's fare (same principle as hard rule 5).

## Driver: posting a ride

1. **From** and **To**: searchable dropdowns over our Places (not Mappls). Any place on any route, not only the end cities.
2. **Route**: the app lists every route that contains From before To, as cards: name, total km, main stops, rough duration. The driver picks one. This is the via confirmation.
3. **Stops**: every place between From and To on that route is a possible stop, all on by default. The driver can switch off towns they won't stop in.
4. **Exact pickup point** at From (and any stop they serve): a Mappls place-search dropdown biased to that town, e.g. "Shivajinagar bus stand, Pune". Stores name, address, eLoc and coordinates. Only confirmed passengers see it (hard rule 3).
5. **Seats and fare**: the app shows the cost share for the full trip and the 15% cap. The driver sets one full-trip fare within the cap; partial-trip fares are derived from it (below).
6. **Advance**: on by default at the policy percentage; the driver may turn it off (D6, Q2).
7. **Review** shows the route diagram (milestone style: vertical line of stops with km and times) and the exact cutoffs, as today.

## Passenger: searching

- Pick **From** and **To** from the same Place dropdowns, plus date.
- A ride matches when both places are **enabled stops on its route, in that order**, and a seat is free on every leg between them.
  - Pune → Chandrapur via Wardha appears for Pune → Wardha, Wardha → Chandrapur, Pune → Chandrapur.
  - It does **not** appear for Yavatmal; the via-Yavatmal ride does.
- Each result shows the passenger's own fare, their pickup and drop place, and the estimated time at their stop.
- Booking stores `board_place`, `alight_place` and the passenger's chosen exact pickup point (Mappls dropdown) if the driver allows pickups along the way.

## Fares (hard rule 2, per leg)

```
cost(A→B)      = sum over legs from A to B of (distance_km × fuel_cost_per_km + tolls_inr)
cost share     = cost(A→B) ÷ (seats_offered + 1)
cap            = floor(cost share × 1.15)
driver's ratio = driver's full-trip fare ÷ full-trip cost share   (between 0 and 1.15)
seat fare A→B  = round(cost share(A→B) × driver's ratio)          integer rupees
```

The driver sets one price; every partial trip is priced at the same ratio, so short trips are never over-charged and the cap holds on every segment.

Worked example (numbers are **illustrative only**, real leg data comes from D3/D4): Pune → Chandrapur via Wardha, 3 seats, fuel ₹7/km, driver charges exactly the cost share.

| Trip | km | tolls | cost | seat fare |
| --- | --- | --- | --- | --- |
| Pune → Chandrapur | 800 | ₹1,400 | ₹7,000 | ₹1,750 |
| Pune → Wardha | 640 | ₹1,100 | ₹5,580 | ₹1,395 |
| Wardha → Chandrapur | 160 | ₹300 | ₹1,420 | ₹355 |

Advance (when on) = policy percentage of the passenger's own fare, rounded to ₹50. Cancellation tiers and refunds are unchanged and apply to each booking's own fare.

## Seats

**Phase 2 default (Q1):** a booking for any part of the trip holds the seat for the whole ride. Simple, and towns along the way still see the ride.
**Phase 3 (if demand):** count seats per leg so Pune→Wardha and Wardha→Chandrapur can share one seat. Availability for a search = minimum free seats across the legs needed. The ride row stays the lock.

## Distance and toll data (D3, D4)

- **Distance**: an admin action "Measure leg" calls the Mappls routing/distance API once for the leg's two endpoints along the intended road, stores the km, `source=mappls`, and marks it *unverified*. A team member checks it against the actual route and marks it *verified*. Only verified legs can be used on public routes.
- **Tolls**: entered by the team per leg (direction-specific), `verified_by` recorded.
- **Driver reports**: after both sides confirm a completed trip, the driver may optionally enter the total tolls they paid. Reports are stored per route; ops sees the median against the stored figure and can publish a new leg version. Reports never change fares automatically.

## Mappls integration (D2, D3)

- Server-side only. The API exchanges client ID and secret for an OAuth token (cached until expiry) and exposes `GET /api/v1/places/search?q=…&near=<place_id>` to the web app. Keys live in `api/.env` (`MAPPLS_CLIENT_ID`, `MAPPLS_CLIENT_SECRET`); nothing reaches the browser.
- Rate-limit and cache searches per query and town to keep usage in the free tier. Pricing and free-tier limits for 2026 still need confirming on Mappls' own pricing page.
- If Mappls is down, the pickup field falls back to free text so posting is never blocked.
- New third-party service: approved by Rohan on 2026-11-04 for place search and one-time leg measurement.

## Rule and doc changes needed

- **Hard rule 2**: "Distance and tolls come from verified route legs" instead of `city_pairs`; formula applied per leg; 15% cap unchanged.
- **Policy section**: advance is a percentage only and optional per ride; no-advance bookings go requested → accepted → confirmed by the driver, with no payment or refund records.
- **Scope**: matching on stops along a chosen route is ordered-stop matching, not "smart matching".
- **Data model**: `places`, `legs` (versioned), `routes`, `route_legs`; `rides.route_id`, `rides.from_place`, `rides.to_place`, enabled stops; `bookings.board_place`, `bookings.alight_place`, pickup point fields; `toll_reports`.
- PR #3's `conservative_fare_cap` and `fare_allowance_inr` are dropped (D5).

## Phases

1. **Route network and posting** (built): Place, Leg, Route tables with admin; Mappls OAuth + place search proxy; "Measure leg" admin action; From/To/route/stops posting flow; exact pickup dropdown; route diagram; migrate existing rides onto equivalent routes. Tests for leg sums and the 15% cap per leg.
2. **Partial-route search and per-leg fares**: ordered-stop matching, per-booking board/alight, partial fares and advances, share card shows the route. Seats held for the whole ride.
3. **Per-leg seats** (optional), driver toll reports, and a real OpenStreetMap map if wanted.

## Open questions

- **Q1 Seat sharing across parts of a trip**: not answered. Spec assumes whole-seat holds until Phase 3.
- ~~Q2 Optional advance~~: decided 2026-11-04, see D6. On a no-advance ride the driver confirms a booking directly (no UPI step), there is nothing to refund, and the cancellation tiers don't apply. Cancellations, no-shows and completed trips still create reliability events, so the record keeps people honest. Search results and the share card show "No advance".
- **Q3 Which routes first**: list the via-routes to cover at launch (e.g. Samruddhi/Wardha, Jalna/Yavatmal, Amravati/old NH).
- **Q4 Mappls account**: who creates it and holds the keys; confirm the free-tier limits.
