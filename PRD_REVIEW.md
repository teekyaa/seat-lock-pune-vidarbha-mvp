# Seat Lock PRD Review: Contradictions, Decisions, and Risks

**Review date:** 2026-10-28  
**Source of truth:** *Seat Lock PRD: Pune to Vidarbha Carpool MVP* (Oct 27, 2026)  
**Repository:** [`teekyaa/seat-lock-pune-vidarbha-mvp`](https://github.com/teekyaa/seat-lock-pune-vidarbha-mvp)

This review records how the current prototype maps to the PRD and identifies product and delivery decisions that remain open. The PRD remains the product source of truth; this review does not silently remove its requirements. “First release” below means available in the local demonstration, often with simulated records. It does **not** mean safe or complete for a public beta.

## Executive summary

Seat Lock is intended to help owner-drivers and passengers arrange cost-sharing rides from Pune to Vidarbha, agree on a clear advance/refund policy, refill cancelled seats from a waitlist, and build a reliability record. WhatsApp is the acquisition and sharing channel, not something the app is intended to replace. The key product promise is that both parties know what happens to the advance if plans change.

The current prototype demonstrates a local version of the core journey: post/search a ride, request and accept a seat, record simulated advance receipt, cancel or refill a seat, use the waitlist, reconfirm, and record post-trip/no-show outcomes. It uses demo profiles, Node.js, browser JavaScript/CSS, and SQLite. It does not provide real OTP, UPI, notifications, moderation, verified identity, production privacy controls, durable scheduled jobs, or public WhatsApp previews.

The highest-priority gaps before a public beta are:

1. Resolve seat reservation and cancellation/refill semantics, including exact 48-hour and 12-hour cutoffs.
2. Confirm the fare formula and any legal limits before presenting fares as compliant.
3. Define who can see reliability events and how no-show/refund disputes are reviewed and appealed.
4. Implement real authentication, privacy/access controls, women-only eligibility enforcement, and a staffed safety workflow.
5. Choose a production architecture for concurrency-safe bookings, background notifications, backups, monitoring, and public ride pages.
6. Run the PRD's concierge test, record baseline cancellation and demand data, and use its gates before treating success targets as validated.

## Product definition

### Intended value

- **Owner-driver:** find passengers who are likely to show up, share trip costs, and avoid last-minute empty seats.
- **Passenger:** find a seat, see useful trust information, and understand the refund outcome before committing.
- **Co-driver:** share driving responsibilities with clear expectations and a defined fare treatment.
- **WhatsApp group admin:** reduce unstructured posts and scams without making the app compete with the group.

The PRD's provisional success measures are late cancellations at half the concierge baseline, 50% ride activation within 24 hours, 40% waitlist refill of freed seats, under 5% overdue refund disputes, 40% driver return between festival windows, and 70% two-sided trip confirmation. These targets need event definitions, instrumentation, and baseline data before they can be used as evidence of success.

### Product boundaries

The PRD excludes train-ticket resale, holding/routing money, commissions, daily commuting, other corridors, in-app chat, live GPS, native apps, and dynamic pricing. The current prototype is local and should not be used to coordinate real rides, collect real personal information, or represent simulated payment records as transfers.

## Requirement disposition

| Story | PRD priority | Disposition | Current state and remaining gap |
| --- | --- | --- | --- |
| US-01 Phone OTP signup | Must | Deferred | Profile switcher only; no SMS OTP, expiry/attempt limit, session, or return to a shared ride after signup. |
| US-02 Member profile | Must | Deferred | Seeded names/hometowns only; no required photo, college/workplace, consent, profile completion, or hometown validation. |
| US-03 Saved vehicle and UPI ID | Must | Deferred | Car text can be attached to a ride; no saved vehicle, UPI ID validation, or confirmation-gated registration-number visibility. |
| US-04 Post a ride | Must | First release — partial | Basic route, date/time, seats, car, fare, and notes can be posted. The six-hour lead-time rule, vehicle capacity, and complete co-driver/eligibility constraints are not production-enforced. |
| US-05 Suggested fair fare | Must | Needs decision | The driver enters a fare. There is no city-pair/fuel/toll table or 15% cap; the PRD leaves inputs and legal interpretation open. |
| US-06 WhatsApp share card | Must | First release — partial | Share text/link is available. It is not a public ride URL and has no server-rendered Open Graph preview with live route/date/seats. |
| US-07 Search rides | Must | First release — partial | Direction/date search and demo fare, seats, and reliability are shown. Verified women-only eligibility is absent. |
| US-08 Request a seat | Must | First release | A passenger can send a request with an optional note. Authentication and production abuse limits are absent. |
| US-09 Accept or decline | Must | First release — partial | Driver acceptance and request expiry are demonstrated. There is no secure identity layer or explicit, timestamped policy agreement by both people. |
| US-10 UPI advance | Must | Deferred | Simulated claim only; no UPI deep link, verified UPI ID, optional UTR, or payment verification. |
| US-11 Confirm advance receipt | Must | First release — simulated | Driver records receipt and locks the demo seat. The record is not evidence that money arrived. |
| US-12 Passenger cancellation | Must | First release — prototype | Demo cancellation and refund outcomes are represented; policy boundary/refill details need decisions below. |
| US-13 Driver cancellation | Must | First release — partial | Cancellation/refund-due records exist. No outbound notification, same-date priority access, festival-season strike rule, or posting block. |
| US-14 Refund acknowledgment/dispute | Must | First release — simulated | A refund can be acknowledged in the demo and overdue records can appear in reliability summaries. No money moves and no moderator resolves disputes. |
| US-15 No-show report | Must | First release — partial | Driver report and passenger dispute are demonstrated. There is no evidence review, moderator queue, or resolution process. |
| US-16 Reconfirmation | Must | First release — in-app | 72/48/12-hour check-in states and an at-risk view are calculated when the app is opened. No scheduled messages or automatic waitlist alert. |
| US-17 Waitlist | Must | First release — in-app | Timed offers and replacement booking are represented. No background expiry worker or delivered offer notification. |
| US-18 Refill refund | Must | First release — simulated | The replacement booking can link to the cancelled booking and record a refund due after simulated advance confirmation. No transfer is verified. |
| US-19 Women-only eligibility | Must | Deferred for real use | A UI option is not eligibility enforcement. Do not rely on it as a safety guarantee. |
| US-20 Report and block | Must | First release — partial | Private demo reports and blocking are available. No moderation operation, review SLA, escalation, or production access control. |
| US-21 Reliability record | Must | First release — partial | Locally recorded trips, cancellations, and disputes are summarized. Events are not independently verified; visibility, appeals, and corrections need decisions. |
| US-22 Post-trip confirmation | Must | First release | Both sides can confirm yes/no; conflicting answers are flagged and not counted. There is no moderator resolution process. |
| US-23 Seat-wanted posts and alerts | Should | Deferred | No seat-wanted listings, matching service, email, or web-push alerts. |
| US-24 Vouching | Should | Deferred | No vouch, withdrawal, active-vouch limit, or linked accountability. |
| US-25 ID verification | Should | Deferred — decision required | No provider integration. Provider, consent, retention, and badge meaning require review before selection. |
| US-26 Emergency trip sharing | Should | Deferred | No emergency-contact form, expiring share link, or trip tracking. |
| US-27 Group-admin page | Could | Deferred | No group ride page, admin verification, or group-specific list. |

Hindi/Marathi, installable PWA/web push, short reviews, and other Could items are also deferred. The complete interactive prototype walkthrough and feature inventory remain in [README.md](README.md#end-to-end-demo-walkthrough).

## Contradictions and ambiguities in the PRD

| Area | Conflict or missing rule | Why it matters | Decision required |
| --- | --- | --- | --- |
| **Money in MVP** | Scope says the MVP ships the advance policy and US-10 requires a UPI deep link, but the same scope says “everything that touches money flow” waits. The non-goal specifically excludes holding/routing money, which is not the same as a direct UPI link and manual receipt record. | Teams may build inconsistent booking/payment states or promise a real payment experience when only a policy demo is intended. | Define whether first release includes simulated records only, a direct UPI link with two-party confirmation, or no advance flow. State explicitly that the platform never takes custody or verifies transfers unless that changes after legal review. |
| **What locks a seat** | Overview language says an advance locks the seat; the advance section says the driver must confirm receipt. Unpaid holds expire in two hours, while the lifecycle note says only confirmed bookings count against seats. | If accepted/claimed requests do not reserve capacity, several passengers may pay for one last seat. If they do reserve it, “only confirmed bookings count” and waitlist timing need adjustment. | Define requested → accepted/held → advance claimed → confirmed transitions, which states reserve capacity, exact hold start/expiry, and atomic last-seat behavior. |
| **Passenger cancellation/refill** | The policy says a refill always means a full refund. For penalty tiers, it says the outcome is decided at departure or refill, whichever comes first. It does not say whether an accepted, unpaid, or confirmed replacement counts as a refill. | A passenger and driver may disagree about whether the original advance is due back, particularly if a replacement claim fails. | Define refill as a specific durable state (recommend a replacement booking confirmed under the applicable payment policy), exact refund trigger/due time, evidence, and rounding of a half-advance. |
| **Cutoff boundaries** | Tables use “more than 48,” “48 to 12,” and “under 12” without defining equality at exactly 48 or 12 hours, or how minute/second precision and rescheduled departures work. | Small timing differences can change a user's financial outcome. | Define inclusive/exclusive boundaries and compute from a stored departure timestamp. Specify whether a departure change resets cutoff times and policy agreement. |
| **“Free” cancellation vs refund** | Overview calls early cancellation free; the table says the full refund is due within 24 hours. A refund “due within 24 hours” can mean a 24-hour deadline or a refund scheduled at the end of that interval. | Users need a precise promise about whether they lose money temporarily and when the refund should arrive. | Use separate fields/labels for refund amount, refund-due timestamp, and latest expected completion deadline. Explain direct-to-driver responsibility and that the app cannot enforce a refund. |
| **Reliability event scope** | Overview says “every cancellation builds a public reliability record,” while lifecycle says only confirmed bookings count and earlier exits leave no mark. No-show reports are allegations until a dispute period/review passes. | Public records can unfairly damage a member's reputation and conflict with privacy/deletion expectations. | Define event types, eligible booking states, public/private fields, provisional/disputed display, review/appeal, correction event, and deletion/anonymization policy. |
| **Driver cancellation remedy** | Affected passengers get “first access” to same-date rides, but no priority duration, allocation rule, or inventory mechanism is specified. | This is an operational promise that cannot be implemented or measured as written. | Define eligible rides, priority window, how conflicting claims are resolved, and what support is offered if no replacement exists—or remove the promise. |
| **Second late cancellation** | A second late cancellation in a festival season blocks posting, but the season dates, counted events, appeal/reversal, and exact reinstatement time are not defined. | Strike enforcement may be inconsistent between festival windows or after a reviewed dispute is corrected. | Define season records, timezone, qualifying event, event reversal, appeal, and unblock rule. Decide whether driver rescheduling over two hours is a cancellation strike. |
| **No-show/refund review** | The PRD requires manual review, a 24-hour report review SLA, and an open public refund dispute, but it has no reviewer roles, evidence standard, queue, appeal, or interim visibility rules. | A single unreviewed report can affect safety and reputation; a missed SLA undermines trust. | Define reviewer authority, evidence, response/appeal timelines, access controls, interim state, and staffing before public users can file reports. |
| **Co-driver** | A co-driver has a licence, takes some driving duty, and may pay less, but no story covers licence checks, duty/insurance expectations, fare discount, or reliability classification. The fare formula counts “seats offered + 1” without clarifying whether a co-driver seat is included. | A co-driver is materially different from an ordinary passenger and creates safety, pricing, and liability questions. | Decide whether co-driver is in the first public beta; specify proof, responsibilities, insurance/legal terms, booking role, fare, and record labels. |
| **Fare formula and law** | Formula depends on maintained city-pair distance/tolls and fuel cost per km. The PRD asks who maintains those values and says the 15% margin is provisional. Weekly driver caps are conditional on legal requirements. | A suggested fare can be mistaken for legal advice or a compliance guarantee. Stale data can produce misleading amounts. | Obtain legal review; approve route distance/toll/fuel sources, owner/update cadence, rounding, denominator, cap, and any required driver limits before enforcing or advertising the fare. |
| **Policy version and agreement** | The narrative requires each booking to retain its policy version and both sides to agree, but acceptance criteria do not specify the acknowledgment record or policy changes while a request is pending/rescheduled. | A later policy update could be applied retroactively or parties may have accepted different rules. | Store immutable policy text/version with the booking and each party's timestamped acknowledgment. Specify which version applies at each transition and after schedule changes. |
| **Women-only eligibility** | Only women drivers may post and only women may request, but the profile supports female/male/other/undisclosed and defines no verification or appeal. | A toggle without enforcement may expose users to risk while implying a safety promise; identity collection itself has privacy implications. | Define eligibility/self-attestation or verification, allowed values, privacy, access control, appeals, and support. Do not present this as a guarantee until enforced and operated. |
| **Notification promises** | The PRD expects SMS OTP plus email/web push for the rest, delivery within two minutes, and specific waitlist/pickup alerts. Consent, provider failure, retries, duplicate delivery, quiet hours, and fallbacks are missing. | A user may rely on an alert that was never delivered or be offered a seat after it has expired. | Define channels/consent, provider ownership, delivery state, retry/idempotency, fallback, and user-visible missed-notification behavior. |
| **Corridor and metrics** | Pune–Vidarbha names several cities, but the ordered city-pair table, stops/via route, reverse-direction normalization, and season windows are not specified. Ride activation within 24 hours has no rule for rides posted less than 24 hours before departure. | Search results, fare calculations, and reported metrics can vary by implementation. | Approve route pairs and direction model; define festival seasons, metric denominators/exclusions, analytics events, and concierge baseline before reading targets as success. |
| **MVP vs launch plan** | The PRD calls 22 Must stories a launchable MVP but says the concierge test should answer the core advance-trust risk before code is written and that a failed gate should change policy before building. | Building all Must stories before testing payment acceptance could spend time on the wrong policy. | Treat the concierge experiment as a gate, not a post-launch metric. Run it and document decisions before expanding beyond a local prototype. |

## Decisions to record before public beta

| Priority | Decision | Suggested decision record / exit criterion |
| --- | --- | --- |
| P0 | Advance amount and payment boundary | Approve 30%/₹300 floor/₹1,000 cap/₹50 rounding or a replacement rule; define deep-link data, who confirms, and what “paid” means. Validate acceptance in the concierge test. |
| P0 | Seat holds and last-seat concurrency | State whether accepted/claimed bookings reserve inventory, hold expiry, waitlist offer expiry, and how duplicate confirmations are prevented. Add concurrent last-seat acceptance checks. |
| P0 | Cancellation/refund calculator | Document exact cutoff inclusivity, base amount for half retention, refill proof, no-show outcome, schedule-change behavior, due timestamp, and 24-hour dispute clock. Obtain legal/product sign-off. |
| P0 | Fare and carpool compliance | Approve corridor table inputs, driver cost share, cap/rounding, co-driver treatment, per-driver limits, and reviewed terms. Do not publish “compliant” claims before this gate. |
| P0 | Trust/safety operations | Define women-only eligibility, report/no-show evidence, reviewer roles, appeal and correction flow, response SLA, incident escalation, and who is on call. |
| P0 | Authentication and data handling | Define OTP provider/rate limits/session lifetimes, data consent and retention, contact reveal, export/deletion, profile photo handling, and authorization checks. |
| P1 | Policy versioning and acknowledgments | Specify immutable policy snapshot and timestamped driver/passenger acceptance, including pending requests and changed departures. |
| P1 | Notifications and support | Select providers, opt-in/opt-out behavior, retries/fallback, waitlist notification guarantees, and customer-support process. |
| P1 | Corridor, season, and metric definitions | Approve city pairs, departure windows, festival season boundaries, event instrumentation, baseline collection, and exclusions for every success metric. |
| P1 | Production architecture | Select the runtime/database/worker/hosting path only after the concierge gate; document migration from this local prototype and operation/backup ownership. |

## Risk register

Likelihood/impact are qualitative planning estimates, not measured incident rates.

| Risk | Likelihood | Impact | Current exposure | Mitigation before public beta |
| --- | --- | --- | --- | --- |
| Passenger pays a stranger but the driver does not refund when required | Medium–high | High | Simulated records cannot verify or enforce a transfer; no dispute operation exists. | Test willingness to pay, clarify direct-payment responsibilities, staff dispute review, and make the app's limits explicit. Revisit escrow only through a separate legal/product decision. |
| User believes a simulated payment or refund is real | High in a demo if unlabeled | High | Prototype actions record claims without opening UPI or checking a UTR. | Keep visible demo/payment-simulation notices; no real bookings or payment instructions until the flow is implemented and reviewed. |
| Women-only label does not enforce eligibility | High | High | Demo identity is switchable and unverified. | Remove/disable safety claims in public beta until eligibility, access control, privacy, appeal, and operations are implemented. |
| False or disputed no-show/cancellation creates reputational harm | Medium | High | Prototype has no moderator resolution queue. | Use provisional states, evidence standards, trained review, appeal/correction, and a limited visibility policy. |
| Two users confirm the last seat at once | Medium under multi-user deployment | High | Local SQLite/single-process demo is not a production concurrency guarantee. | Use database transactions/locking or equivalent atomic reservation, idempotency, and race-condition tests at production scale. |
| Reminders or offer expiries are missed | High | Medium–high | States are evaluated when app opens; no durable scheduled worker sends alerts. | Add persistent notification/outbox records, idempotent workers, retry/monitoring, and explicit fallback before relying on deadlines. |
| Public profile/contact or sensitive data is exposed | Medium | High | No production auth, role checks, privacy/access workflow, export/delete, or retention controls. | Threat-model API access; implement least-privilege authorization, consent, redaction, retention/deletion, HTTPS, audit, and security review. |
| Fare rule violates applicable carpool requirements | Medium | High | 15% cap is provisional; fare data and weekly cap are unresolved. | Obtain qualified legal review and maintain an approved city-pair table; block out-of-policy fares server-side. |
| Local database is lost or shared accidentally | Medium | Medium–high | SQLite state is ignored by Git and the project config has no automatic backup; accidental file sharing could expose real data. | Keep demo data synthetic, stop the app before copying a database, make encrypted backups, and test restore. Never commit DB/WAL files. |
| Festival demand/adoption does not meet assumptions | Medium | High | Baseline and admin participation are unknown; targets are provisional. | Concierge-test selected WhatsApp groups/admins, track activation and cancellation baselines, and use gates to change policy before feature expansion. |
| Local share link is mistaken for a public ride page | Medium | Medium | `localhost` links only work on the same machine; no dynamic Open Graph preview exists. | Label local demos clearly; use a deployed public URL and server-rendered metadata before asking users to share live rides. |

## Architecture difference from the PRD

| Layer | PRD proposal | Current prototype | Reason and unresolved production work |
| --- | --- | --- | --- |
| Web | Next.js App Router, TypeScript, Tailwind, PWA, server-rendered ride pages | Static HTML, browser JavaScript and CSS | Fast local demo without a build/deploy pipeline. Dynamic public link previews, PWA, production accessibility, and real onboarding remain unimplemented. |
| API | Django REST Framework | Node.js built-in HTTP server with a small JSON API | Keeps the prototype dependency-free. Production auth, admin/moderation, schema migrations, audit, and API hardening remain open. |
| Background jobs | Celery/beat and Redis | No worker or scheduler | Time-based state is recalculated on app open/action. Durable reminders, expiry, alerts, retries, and restart behavior are absent. |
| Data | PostgreSQL 16, enums, row locks, materialized reliability view | Local SQLite using Node's built-in `node:sqlite` | Easy same-day setup; not a multi-instance concurrency or managed-backup solution. A migration plan and tested atomic seat reservation are needed. |
| Media/integrations | Object storage, SMS/email/push, monitoring | No external service credentials or real user media | Avoids integrations in a local prototype; consent, provider, retention, and operations must be decided before collection/use. |
| Hosting | Vercel web plus Railway API, worker, PostgreSQL, Redis | Server binds to `127.0.0.1` | Local-only by design. Public TLS, availability, operations, backups, monitoring, and deployment are not configured. |

The PRD's proposed design is a multi-component modular monolith rather than the smallest same-day demo. The current stack is a deliberate prototype shortcut, not a replacement product decision. Keep the production choice open until the concierge gate validates the core behavior; preserve the PRD's service requirements when that decision is made.

## Safe demo claims versus public-launch claims

### Safe to demonstrate locally

- Posting and searching seeded/demo rides.
- Sending a seat request, accepting it as the driver, and seeing a simulated advance receipt lock the seat.
- Walking through cancellation, waitlist, refund-due, reconfirmation, trip-confirmation, report/block, and no-show/dispute screens with synthetic profiles.
- Showing the visual design and explaining the intended corridor workflow.

### Do not claim as production-ready

- Phone identity, profile authenticity, driver/vehicle identity, women-only eligibility, or verified trust.
- A UPI transfer, refundable advance, actual refund, financial protection, or payment dispute resolution.
- SMS/email/push/WhatsApp alerts, guaranteed offer delivery, or background expiry enforcement.
- Legal fare compliance, insured co-driving, public reliability accuracy, or staffed safety response.
- Production privacy, data deletion/export, HTTPS deployment, backups, disaster recovery, or cross-device ride sharing.

## Recommended gate sequence

1. **Concierge gate:** interview/test with the selected admins and riders; measure baseline cancellation, advance acceptance/refusal, refund expectations, and ride activation.
2. **Policy gate:** record decisions on fare, advance, cancellation/refill, seat holds, driver changes, season strikes, and policy version before implementing real payment links.
3. **Trust/safety gate:** implement identity/access controls, women-only rules, report/no-show/refund review, appeals, and incident ownership before public discovery.
4. **Reliability gate:** implement atomic seat allocation, durable background jobs, notification delivery/fallback, monitoring, backups, and restore testing.
5. **Privacy/legal gate:** review terms, fare limits, consent, retention/deletion, public reliability, and data access with qualified reviewers.
6. **Controlled beta:** instrument PRD metrics, publish clear service limits, monitor incidents and disputes, and expand only when the prior gates are met.

## Prototype storage note

The project defaults to `data/seat-lock-prototype.sqlite`; `SEATLOCK_DB_PATH` can select another path. The current local workspace also has `data/seat-lock.sqlite`, which contains older demo records. Both database files are intentionally excluded from Git. A fresh database is created and seeded when the app starts with no existing users, but opening an existing DB may run schema migrations; the app does not merge the two files. Stop the server and back up each database before changing, deleting, or selecting one. Keep any backup local and do not publish it.
