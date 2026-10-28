# Seat Lock prototype (superseded)

> This is the original local Node/SQLite demo, kept for reference. The production build lives in `api/` and `web/`; see the root README. Run this prototype from the `prototype/` folder.

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

## PRD review: scope, contradictions, decisions, and risks

The PRD remains the product source of truth. This section records how the current local prototype maps to it; a prototype status does not mean a requirement is ready for public use. **First release (prototype)** means a user can demonstrate the flow with local demo profiles and simulated records. **Deferred** means the PRD requirement is not implemented or is intentionally outside this prototype. **Needs decision** means the PRD does not yet define one consistent, safe rule. None of these labels silently removes a PRD requirement. See the standalone [PRD review](PRD_REVIEW.md) for the full story-by-story assessment, decision register, risk register, architecture comparison, and launch gates.

### Requirement-by-requirement status

| PRD story | Original priority | Status | Current prototype and remaining work |
| --- | --- | --- | --- |
| US-01 Phone OTP signup | Must | Deferred | A profile switcher stands in for signup. SMS delivery, five-minute OTPs, attempt limits, sessions, and return-to-ride signup are absent. |
| US-02 Complete member profile | Must | Deferred | Seeded names and hometowns are demo data; photo, college/workplace, consent, profile completion, and corridor-city validation are absent. |
| US-03 Saved vehicle and UPI ID | Must | Deferred | Car details are entered with a ride; there is no saved vehicle profile, UPI ID validation, or confirmation-gated registration-number access. |
| US-04 Post a ride | Must | First release (partial prototype) | Drivers can post the basic route, time, seats, car, fare, and notes. The six-hour lead-time rule, vehicle-capacity enforcement, and complete co-driver/eligibility workflow are not production-enforced. |
| US-05 Suggested fair fare | Must | Needs decision | The prototype accepts a driver-entered fare. It has no maintained city-pair distance/toll/fuel table or 15% cap. The PRD itself leaves fuel/toll inputs and legal interpretation open. |
| US-06 WhatsApp share card | Must | First release (partial prototype) | Share text/link is available. The link is local to the demo computer; there is no public ride URL or server-rendered Open Graph preview with live seats. |
| US-07 Search rides | Must | First release (partial prototype) | Direction/date search, seats, fare, and a demo reliability summary are shown. Verified gender eligibility and the women-only search restriction are not enforced. |
| US-08 Request a seat | Must | First release (prototype) | A passenger can send a request with a note. OTP-backed profiles, abuse/rate limits, and authenticated identity are absent. |
| US-09 Accept or decline | Must | First release (partial prototype) | Drivers can accept requests and requests expire on a time rule. A secure, explicit policy agreement by both parties is not implemented; authentication and production authorization are absent. |
| US-10 UPI advance | Must | Deferred | The prototype records a simulated claim. It does not open a UPI deep link, validate a UPI ID, collect a UTR, or verify a transfer. |
| US-11 Confirm advance receipt | Must | First release (simulated) | The driver can record receipt and the seat becomes confirmed in the demo. This is not proof of payment and must not be described as a real payment feature. |
| US-12 Passenger cancellation | Must | First release (prototype) | The app records and displays demo cancellation/refund outcomes. Exact policy edge cases still need product/legal decisions below. |
| US-13 Driver cancellation | Must | First release (partial prototype) | Cancellation and refund-due records are represented. There are no outbound notifications, same-date priority access, festival-season strike enforcement, or posting block. |
| US-14 Refund acknowledgment/dispute | Must | First release (simulated) | A passenger can acknowledge a recorded refund; overdue due records can appear in the reliability summary. No money is returned and the dispute is not reviewed by a moderator. |
| US-15 No-show report | Must | First release (partial prototype) | The driver can report a no-show and the passenger can dispute it. There is no moderator review/resolution workflow, so an unresolved allegation is not independently verified. |
| US-16 Reconfirmation | Must | First release (in-app only) | The 72/48/12-hour check-ins and at-risk state are available when the app is opened. Scheduled SMS/email/push delivery and automatic waitlist alerts are absent. |
| US-17 Waitlist | Must | First release (in-app prototype) | A waitlist and timed offer/replacement flow are represented. There is no outbound offer notification or reliable background expiry worker. |
| US-18 Refill refund | Must | First release (simulated) | The replacement booking can be linked to the cancelled booking and a refund due can be recorded after the replacement advance is confirmed in the demo. No actual payment/refund is verified. |
| US-19 Women-only eligibility | Must | Deferred for real use | A display option is not identity or eligibility enforcement. Do not rely on the current option as a safety guarantee. Eligibility, privacy, and handling of undisclosed/other gender values need a decision. |
| US-20 Report and block | Must | First release (partial prototype) | Users can submit private demo reports and block another profile. There is no moderation queue, 24-hour review operation, escalation, or production access control. |
| US-21 Reliability record | Must | First release (partial prototype) | The prototype shows locally recorded trips, cancellations, and refund disputes. Events are not independently verified; public visibility, correction, appeal, and deletion rules need resolution. |
| US-22 Post-trip confirmation | Must | First release (prototype) | Both sides can record whether the trip happened; conflicting answers are flagged and not counted. There is no moderator resolution process for conflicts. |
| US-23 Seat-wanted posts and alerts | Should | Deferred | No passenger seat-wanted listing, matching service, email, or web-push alert. |
| US-24 Member vouching | Should | Deferred | No vouch creation, withdrawal, limit, or linked accountability. |
| US-25 Optional ID verification | Should | Deferred / decision required | No provider integration. Before selection, assess consent, provider, data minimization, result retention, and what a badge actually guarantees. |
| US-26 Emergency trip share | Should | Deferred | No emergency-contact form, share link, expiry, or trip tracking. |
| US-27 Group-admin page | Could | Deferred | No group page, admin verification, or group-specific ride list. |

The other **Should** items (Hindi/Marathi, installable PWA/web push, and written reviews) and **Could** items (group-admin tooling) remain deferred as well. The PRD's non-goals remain in force: no train-ticket resale, escrow, in-app payment custody/commission, commute pooling, other corridors, live GPS, native app, or dynamic pricing.

### Contradictions and decisions to settle

These are product decisions in the PRD, not assumptions this prototype should settle implicitly.

| Topic | PRD conflict or gap | Decision needed before a public beta |
| --- | --- | --- |
| Whether payments are in MVP | Scope says the MVP ships the advance policy and US-10 requires a UPI deep link, but the same scope says “everything that touches money flow” waits. The non-goal is specifically holding/routing money, which is different from generating a link and recording confirmations. | Define “money flow”: demo-only records, direct UPI deep links with manual confirmation, or defer payment-related launch entirely. Never imply a recorded claim proves a transfer. |
| What locks a seat | The overview says an advance locks a seat; the policy says confirmation happens only after the driver taps “Advance received.” A two-hour unpaid hold is also specified, while the lifecycle note says only confirmed bookings count against seats. | Decide whether an accepted/claimed booking reserves capacity during its hold. Define the exact state transitions, concurrency rule, expiry behavior, and when waitlist offers may consume the released seat. |
| Cancellation and refill | A refilled seat always gives a full refund, but the policy also delays the outcome for penalty-tier cancellations until departure or refill, whichever comes first. “Refilled” is not defined consistently as accepted, advance-claimed, or confirmed. | Define the refund trigger, refund due timestamp, evidence of refill, half-refund rounding, treatment of pending UPI transfers, and exact boundary behavior at 48 and 12 hours. State how a changed departure time recalculates cutoffs. |
| Reliability record scope | “Every cancellation builds a public reliability record” conflicts with the lifecycle note that only confirmed bookings count and earlier exits leave no mark. A no-show can be reported by one party and disputed by the other. | Define which confirmed actions create events, whether free/driver cancellations and no-shows are separate, what is public, what is provisional while disputed, who resolves appeals, and how corrections/deletion work. |
| Late-cancellation strike | A second late driver cancellation in a festival season blocks posting, but the season calendar, counting rules, appeal, reset, and unblocking date are unspecified. | Define each season's dates/time zone, what counts as a strike, whether rescheduled/cancelled rides count, and how an appeal or reversal affects the limit. |
| Driver cancellation remedy | Affected passengers get “first access” to same-date rides, but there is no priority window, seat reservation, matching rule, or operational mechanism in the stories/schema. | Define eligibility, duration, matching, and what happens when no alternate seat exists; otherwise remove the promise from user-facing policy. |
| No-show and refund disputes | The PRD requires hand review, 24-hour review SLAs, and an open public dispute, but does not define evidence, reviewer authority, appeals, or a moderator/admin workflow. | Define an interim human-review process and whether an allegation or overdue refund is visible before review. Do not present unreviewed claims as verified facts. |
| Co-driver role | A co-driver is a passenger with a driving licence and may receive a reduced fare, but no story defines licence checks, driving duties, insurance/liability, price calculation, or how a co-driver differs in booking and reliability. | Decide whether co-driver is in the public beta, what proof/duty is required, how fare is set, and which events are labelled differently. |
| Fare and legal cap | The formula depends on seats offered, fuel cost per km, and tolls; the PRD asks who maintains these values and says the 15% margin is provisional pending legal review. A weekly driver cap is mentioned only conditionally. | Approve corridor city-pair data, update owner/cadence, seat-count denominator, rounding, co-driver treatment, margin, weekly cap (if legally required), and lawyer-reviewed terms before fares are presented as compliant. |
| Policy version and agreement | The narrative requires an immutable policy version per booking and agreement by both sides. The stories do not specify the exact acknowledgment record, policy display/version, or what happens when policy changes after request/acceptance. | Store the policy snapshot/version and each party's timestamped acknowledgment before confirmation. Define which version applies to a pending request and a rescheduled ride. |
| Women-only eligibility | The requirement allows only women drivers and passengers, while profile gender includes female, male, other, and undisclosed; the verification method and privacy implications are not defined. | Define self-attestation or verification, permitted values, access behavior, appeals, and data handling. Do not advertise this as a safety guarantee until enforcement and operations exist. |
| Notification promise | The PRD requires email/web-push messages and delivery within two minutes, but the prototype only calculates time-based states when opened. The 48-hour waitlist alert and 12-hour pickup details also have no channel/consent/fallback rules. | Choose providers, consent and unsubscribe rules, retry/duplicate behavior, quiet hours, failure handling, and who is accountable for missed alerts. |
| Route and activation scope | The corridor names Pune, Nagpur, Wardha, and Chandrapur, but the city-pair table, intermediate stops, reverse-direction normalization, and exact festival windows are not specified. The 24-hour activation metric also needs a rule for rides posted less than 24 hours before departure. | Approve the supported city-pair/stop list, direction model, season windows, and metric denominator before using these as launch or success claims. |
| Trust, privacy, and safety operations | Public reliability, photos, phone/contact reveal, gender, reports, blocks, data export/deletion, anonymization, and DPDP consent are requirements, but there is no retention schedule or complete access/appeal policy. | Define what is visible to whom and when, data retention/deletion, consent, moderator access, abuse escalation, and incident response. Get legal/privacy review before real personal data is collected. |

### PRD non-functional requirements and prototype gap

| PRD requirement | Status and implication |
| --- | --- |
| OTP, per-phone/IP limits, short-lived sessions, role authorization | Deferred. The profile switcher is not authentication; the local API is not safe for untrusted users. |
| Hide phone, UPI, and car registration until confirmed; consent, export/delete, anonymization | Deferred. Do not enter real personal/contact/payment data into this demo. |
| UPI direct-to-driver, no money custody or commission | Simulated only. The app does not open a UPI app or verify either side's payment claim. |
| Fare cap and any legally required driver limits | Needs the fare/legal decisions above; no cap is currently enforced. |
| Reports/blocks and review within 24 hours | Report/block UI is a prototype; no reviewer queue or response operation exists. |
| Search p95 under 500 ms; server-rendered ride pages and rich WhatsApp previews | Not measured or implemented. The local app has no public ride URL or server-generated preview. |
| Scheduled delivery within two minutes, restart-safe jobs, daily backups/PITR | Deferred. No worker, scheduler, outbound notification provider, or backup service is configured. |
| IST cutoffs with day-of-week wording | The prototype formats displayed times in IST, but exact boundary cases still need policy decisions and production acceptance tests. |
| 44 px tap targets, contrast, light/dark, keyboard access | Not audited against the PRD; treat as unverified until accessibility review. |
| Success metrics and baseline | Targets are provisional and no analytics instrumentation or concierge baseline is included in this code. The PRD says the Diwali concierge gate should inform policy before launch. |

### Product and safety risks

- **Payment-trust risk:** simulated receipts can look like money moved. In reality a driver may not refund, UPI claims are not verified, and the prototype has no dispute staff. Keep demo labeling visible and do not coordinate real bookings/payments here.
- **Safety and identity risk:** demo profiles are switchable and unverified. Women-only eligibility, contact access, blocks, and report review do not have production authentication or operational enforcement.
- **Seat-allocation risk:** SQLite and this single-process prototype are suitable for a local demo, not a guarantee against simultaneous confirmations across multiple users/processes. A real launch needs transactional seat reservation and concurrency tests.
- **Reliability-record risk:** cancellations, no-shows, and disputes can be false or incomplete. Public reputational records need evidence, review, appeal, and correction mechanisms before real users rely on them.
- **Missed-notification risk:** check-ins and expiry/at-risk states are evaluated in-app; no background worker sends the PRD's reminders or waitlist alerts. Users may miss a critical time window.
- **Data-loss/privacy risk:** local SQLite files are not backed up by the project. Losing the machine loses its demo state; committing or sharing the files could expose personal data if real details are entered.
- **Legal and adoption risk:** the 15% fare cap is provisional and unreviewed, and advance/refund expectations may be unacceptable to users. Run the concierge test with group admins and measure baseline cancellations before public launch.

### Architecture difference from the PRD

The PRD proposes Next.js/TypeScript/Tailwind on Vercel, Django REST Framework plus Celery workers on Railway, PostgreSQL, Redis, SMS/email/web push providers, and object storage. This prototype instead uses a dependency-free Node.js HTTP server, browser JavaScript/CSS, and local SQLite. That smaller stack was chosen for a same-day, single-developer demo: it avoids provisioning services and makes the main journeys runnable locally. It is **not** an implementation of the PRD's production reliability, authentication, scheduled delivery, server-rendered share previews, concurrent seat locking, admin review, backup, or privacy guarantees. Keep the production stack decision open until the concierge gate and product decisions above are resolved; do not infer that the prototype has production parity.

### Recommended decision order before public beta

1. Resolve advance/cancellation/refill rules, exact cutoff boundaries, seat-hold semantics, and policy-version acknowledgment.
2. Confirm the legal fare model and carpool terms with a qualified reviewer; set the city-pair data and any driver caps.
3. Decide the women-only eligibility model and the moderation/no-show/refund appeal process; staff the required review SLA.
4. Specify authentication, personal-data access/retention/deletion, contact reveal, and incident handling.
5. Choose the production architecture and implement durable jobs, real notifications, backups, monitoring, and concurrency-safe seat allocation.
6. Instrument the provisional metrics and run the planned concierge test with selected WhatsApp group admins before treating targets as validated.

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
