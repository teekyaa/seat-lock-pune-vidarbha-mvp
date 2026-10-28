# Seat Lock · Pune to Vidarbha Carpool MVP

A phone-first, local prototype for arranging cost-sharing carpools between Pune and Vidarbha. It is built with Node.js, SQLite, and plain browser JavaScript and CSS. No npm packages or external service credentials are required to run the demo.

> **Prototype only:** this build uses demo profiles and simulated payment records. It is not ready for public bookings, real payments, or safety-critical use. See [Prototype boundaries](#prototype-boundaries).

## Requirements

- Node.js 22.13 or newer (the project uses Node's built-in `node:sqlite`, which is experimental in Node 22)
- A modern desktop or mobile browser

## Start the app

From the project directory:

```powershell
npm start
```

Open [http://localhost:3001](http://localhost:3001). The server binds to `127.0.0.1`; it is only available on the computer running it. A ride link copied from this local demo works on that same computer.

No `npm install` is needed. If port 3001 is already in use, stop the other process or set a different `PORT`, for example:

```powershell
$env:PORT = 3010
npm start
```

## Demo accounts and sample data

The header's **Demo as** menu switches between these seeded profiles:

| Profile | Role | Hometown |
| --- | --- | --- |
| Aditi Deshmukh | Driver | Nagpur |
| Rahul Patil | Passenger | Wardha |
| Neha Kulkarni | Passenger | Wardha |

The app creates a sample Pune–Nagpur ride on first startup. New rides and bookings are saved in `data/seat-lock-prototype.sqlite`. That database is intentionally git-ignored. To reset the demo and reseed the sample ride, stop the server and remove that database file. No real user data should be stored here.

## End-to-end demo walkthrough

### 1. Post and share a ride

1. Select **Driver · Aditi** in the profile menu.
2. Open **Offer a ride** and enter the route, departure time, trip duration, seats, car, fare, and optional notes.
3. Post the ride. Use **Copy link** or **WhatsApp** on the ride page to share the local demo card.

### 2. Request and lock a seat

1. Switch to **Passenger · Rahul** and open **Find a ride**.
2. Choose a route and optional travel date. Open the ride card and tap **Request a seat**.
3. Add an optional note in the in-app request form and send the request.
4. Switch to **Driver · Aditi** and open **My bookings** or manage the ride. Accept the request.
5. Switch to Rahul and record the simulated advance claim. Switch back to Aditi and choose **Advance received** to lock the seat.

### 3. Try cancellation, the waitlist, and refunds

1. With a confirmed booking, switch to the passenger and choose **Cancel booking**. The app displays and records the applicable demo refund outcome.
2. If the ride was full, another passenger can join the first-come, first-served waitlist. A freed seat creates a timed offer (two hours, or 30 minutes when departure is under 12 hours away).
3. Accept the offer as that passenger, record the simulated advance, then confirm it as the driver. When the replacement advance is confirmed, the original passenger's full refund is marked due.
4. The passenger can choose **Refund received**. A due refund left unconfirmed for 24 hours past its due time appears as an open dispute in the member reliability summary.

### 4. Try driver cancellation and request expiry

- As Aditi, cancel a ride with a confirmed passenger to create full-refund-due records. The driver's reliability summary records an early or late cancellation based on the departure time.
- Unanswered seat requests expire after 12 hours, or 12 hours before departure if that comes first. The driver and passenger see the expired state, and the server refuses late acceptance. A new seat request cannot be made within 12 hours of departure.

### 5. Try departure check-ins and the post-trip record

1. Post and confirm a ride that departs within 72 hours.
2. In **My bookings**, the passenger can answer the 72-, 48-, and 12-hour check-ins; the driver can answer at 48 and 12 hours.
3. If the passenger has not answered the 48-hour check-in six hours after it opens, the driver sees an at-risk seat. A reported plan change also shows as at risk.
4. These checks are shown when a traveler opens the app. The prototype does not send scheduled messages or alert the waitlist.
5. After estimated arrival, both travelers can answer whether the trip happened. A matching “Yes” adds the trip to both reliability records; conflicting answers are flagged and not counted.
6. For a quick demo, Aditi can choose **Simulate arrival now** on a confirmed ride. This changes the demo arrival timestamp; it does not track a vehicle.

### 6. Try reports, blocks, and no-show disputes

- From **My bookings**, report the other traveler using a fixed reason list. Reports remain private to the reporter in this prototype; there is no moderator review queue.
- Blocking a traveler hides rides between those profiles and prevents new requests between them.
- Thirty minutes after departure, the driver can report a confirmed passenger as a no-show. The passenger can dispute the report within 24 hours. An undisputed report then appears on the passenger's reliability summary; disputed reports remain off the record pending manual review.

## Features in this prototype

- Premium, phone-first interface with different gradient treatments for **Find a ride**, **Offer a ride**, **My bookings**, and ride details.
- Ride posting, corridor and date search, seats-left count, reliability summary, and WhatsApp share text/link.
- Seat request with optional passenger note, request expiry, driver acceptance, and recorded advance claim/receipt.
- Cancellation policy cutoffs shown in IST, passenger cancellation outcomes, driver cancellation, refill-linked refunds, refund acknowledgment, and overdue refund-dispute visibility.
- First-come waitlist, timed offers, and replacement booking flow.
- 72/48/12-hour in-app reconfirmations and the six-hour 48-hour at-risk flag.
- Post-trip confirmation by both travelers, conflict flagging, and completed-trip reliability entries.
- Driver no-show report, 24-hour passenger dispute window, and undisputed no-show entry on the passenger's reliability summary.
- Private reports and mutual ride/request blocking.
- Seeded demo accounts and persistent local SQLite storage.

## Prototype boundaries

These items are **not implemented as production features** and must not be represented as working services:

- Login is a profile switcher, not phone OTP verification. Demo accounts have seeded names and phone numbers; there are no real user profiles, photos, college/workplace fields, or gender verification.
- Advances and refunds only change local records. No UPI app opens, no UTR is collected or verified, and no money moves.
- There is no scheduled job or outbound SMS, push, email, WhatsApp, or waitlist notification service. Time-based states are calculated when the app is opened or an action is attempted.
- Disputed no-show cases have no moderator resolution screen. Reports have no moderation queue.
- Fare is entered by the driver. The city-pair cost-share table, 15% cap, vehicle-capacity validation, and co-driver flow are not implemented.
- Women-only rides are not protected by verified gender/eligibility checks. Do not rely on this option for real-world safety.
- Contact details are not released by an authenticated confirmation workflow. There is no chat, emergency-trip link, live tracking, or production privacy/access-control layer.
- No-show, cancellation, and reliability entries are prototype records and are not independently verified.

Do not expose this local server to the public internet or use this prototype to coordinate real rides or payments.

## Project layout

```text
public/
  index.html       App shell and profile switcher
  app.js           Screens, interactions, and API client
  styles.css       Responsive visual system and page gradients
src/
  server.js        Local HTTP server and JSON API
  domain.js        Booking rules and domain operations
  store.js         SQLite schema, migrations, and seed data
data/              Local SQLite files (ignored by Git)
README.md          Setup, feature walkthrough, and limitations
package.json       Start script and Node version requirement
```

## Storage and environment

- Default SQLite file: `data/seat-lock-prototype.sqlite`
- Override the database path with `SEATLOCK_DB_PATH`.
- Override the HTTP port with `PORT` (default `3001`).
- Use `SEATLOCK_DB_PATH=:memory:` for a temporary in-memory database.

The app serves only local static files and a small JSON API. It has no external runtime dependencies.
