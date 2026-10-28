const crypto = require('node:crypto');
const { db, transaction } = require('./store');

const nowIso = () => new Date().toISOString();
const refundDueAt = () => new Date(Date.now() + 24 * 3600000).toISOString();
const id = (prefix) => `${prefix}_${crypto.randomUUID()}`;
const queryRows = (sql, ...args) => db.prepare(sql).all(...args);
const queryRow = (sql, ...args) => db.prepare(sql).get(...args);

function user(id) {
  return queryRow('SELECT id, name, role, hometown FROM users WHERE id = ?', id);
}

function reliabilitySummary(userId) {
  const summary = queryRow(`SELECT
    SUM(CASE WHEN kind = 'early_cancel' THEN 1 ELSE 0 END) AS early_cancellations,
    SUM(CASE WHEN kind = 'late_cancel' THEN 1 ELSE 0 END) AS late_cancellations
    FROM reliability_events WHERE user_id = ?`, userId) || {};
  const latest = queryRow(`SELECT kind, hours_before_departure FROM reliability_events
    WHERE user_id = ? ORDER BY created_at DESC LIMIT 1`, userId);
  const disputes = queryRow(`SELECT COUNT(DISTINCT p.booking_id) AS open_refund_disputes
    FROM payment_records p JOIN bookings b ON b.id = p.booking_id JOIN rides r ON r.id = b.ride_id
    WHERE p.kind = 'refund' AND p.status = 'due' AND p.due_at IS NOT NULL
      AND datetime(p.due_at, '+24 hours') <= datetime('now')
      AND (r.driver_id = ? OR b.passenger_id = ?)`, userId, userId);
  const completed = queryRow(`SELECT COUNT(DISTINCT b.id) AS completed_trips
    FROM bookings b JOIN rides r ON r.id = b.ride_id
    JOIN trip_confirmations dc ON dc.booking_id = b.id AND dc.user_id = r.driver_id AND dc.happened = 1
    JOIN trip_confirmations pc ON pc.booking_id = b.id AND pc.user_id = b.passenger_id AND pc.happened = 1
    WHERE r.driver_id = ? OR b.passenger_id = ?`, userId, userId);
  const noShows = queryRow(`SELECT COUNT(*) AS count FROM no_show_cases n
    WHERE n.passenger_id = ? AND n.status = 'pending' AND datetime(n.marked_at, '+24 hours') <= datetime('now')`, userId);
  return {
    completed_trips: Number(completed.completed_trips || 0),
    no_shows: Number(noShows.count || 0),
    open_refund_disputes: Number(disputes.open_refund_disputes || 0),
    early_cancellations: Number(summary.early_cancellations || 0),
    late_cancellations: Number(summary.late_cancellations || 0),
    latest_cancel_kind: latest?.kind || null,
    latest_cancel_hours_before: latest?.hours_before_departure ?? null,
  };
}

function isBlockedBetween(userA, userB) {
  if (!userA || !userB || userA === userB) return false;
  return Boolean(queryRow(`SELECT 1 AS found FROM blocks
    WHERE (blocker_id = ? AND blocked_id = ?) OR (blocker_id = ? AND blocked_id = ?) LIMIT 1`, userA, userB, userB, userA));
}

function canViewRide(rideId, viewerId) {
  if (!viewerId) return true;
  const ride = queryRow('SELECT driver_id FROM rides WHERE id = ?', rideId);
  if (!ride) return false;
  return !isBlockedBetween(viewerId, ride.driver_id);
}

function listRides(viewerId = null) {
  return queryRows(`SELECT r.*, u.id AS reliability_user_id, u.name AS driver_name, u.hometown AS driver_hometown,
    (SELECT COUNT(*) FROM bookings b WHERE b.ride_id = r.id AND b.status IN ('accepted','advance_claimed','confirmed')) AS seats_held
    FROM rides r JOIN users u ON u.id = r.driver_id WHERE r.status != 'cancelled'
      AND (? IS NULL OR NOT EXISTS (SELECT 1 FROM blocks bl WHERE
        (bl.blocker_id = ? AND bl.blocked_id = r.driver_id) OR (bl.blocker_id = r.driver_id AND bl.blocked_id = ?)))
    ORDER BY r.departure_at`, viewerId, viewerId, viewerId)
    .map(ride => ({ ...ride, seats_left: Math.max(0, ride.seats_offered - ride.seats_held), reliability: reliabilitySummary(ride.reliability_user_id) }));
}

function getRide(rideId) {
  const ride = queryRow(`SELECT r.*, u.id AS reliability_user_id, u.name AS driver_name, u.hometown AS driver_hometown,
    (SELECT COUNT(*) FROM bookings b WHERE b.ride_id = r.id AND b.status IN ('accepted','advance_claimed','confirmed')) AS seats_held
    FROM rides r JOIN users u ON u.id = r.driver_id WHERE r.id = ?`, rideId);
  if (!ride) return null;
  return { ...ride, seats_left: Math.max(0, ride.seats_offered - ride.seats_held), reliability: reliabilitySummary(ride.reliability_user_id) };
}

function getBooking(bookingId) {
  const booking = queryRow(`SELECT b.*, r.origin, r.destination, r.departure_at, r.expected_arrival_at, r.car, r.driver_id,
    d.name AS driver_name, p.name AS passenger_name, p.hometown AS passenger_hometown,
    (SELECT status FROM payment_records WHERE booking_id = b.id AND kind = 'refund' ORDER BY created_at DESC LIMIT 1) AS refund_status,
    (SELECT due_at FROM payment_records WHERE booking_id = b.id AND kind = 'refund' ORDER BY created_at DESC LIMIT 1) AS refund_due_at
    FROM bookings b JOIN rides r ON r.id = b.ride_id
    JOIN users d ON d.id = r.driver_id JOIN users p ON p.id = b.passenger_id
    WHERE b.id = ?`, bookingId);
  if (!booking) return null;
  return withNoShow(withRequestExpiry({ ...booking, trip_confirmations: tripConfirmations(bookingId), reconfirmations: bookingReconfirmations(bookingId) }));
}

function withRequestExpiry(booking) {
  const requestExpiresAt = booking.request_expires_at || new Date(Math.min(
    new Date(booking.created_at).getTime() + 12 * 3600000,
    new Date(booking.departure_at).getTime() - 12 * 3600000
  )).toISOString();
  return { ...booking, request_expires_at: requestExpiresAt, request_expired: booking.status === 'requested' && new Date(requestExpiresAt).getTime() <= Date.now() };
}

function withNoShow(booking) {
  const record = queryRow('SELECT status, marked_at, disputed_at FROM no_show_cases WHERE booking_id = ?', booking.id);
  if (!record) return { ...booking, no_show_case: null };
  const disputeUntil = new Date(new Date(record.marked_at).getTime() + 24 * 3600000).toISOString();
  const status = record.status === 'pending' && new Date(disputeUntil).getTime() <= Date.now() ? 'confirmed' : record.status;
  return { ...booking, no_show_case: { ...record, status, dispute_until: disputeUntil } };
}

function bookingsForRide(rideId) {
  return queryRows(`SELECT b.*, r.origin, r.destination, r.departure_at, r.expected_arrival_at, r.car, r.driver_id,
    d.name AS driver_name, p.name AS passenger_name, p.hometown AS passenger_hometown,
    (SELECT status FROM payment_records WHERE booking_id = b.id AND kind = 'refund' ORDER BY created_at DESC LIMIT 1) AS refund_status,
    (SELECT due_at FROM payment_records WHERE booking_id = b.id AND kind = 'refund' ORDER BY created_at DESC LIMIT 1) AS refund_due_at
    FROM bookings b JOIN rides r ON r.id = b.ride_id JOIN users d ON d.id = r.driver_id
    JOIN users p ON p.id = b.passenger_id WHERE b.ride_id = ? ORDER BY b.created_at`, rideId)
    .map(booking => withNoShow(withRequestExpiry({ ...booking, passenger_reliability: reliabilitySummary(booking.passenger_id), trip_confirmations: tripConfirmations(booking.id), reconfirmations: bookingReconfirmations(booking.id) })));
}

function waitlistForRide(rideId) {
  return queryRows(`SELECT w.*, u.name AS passenger_name, u.hometown AS passenger_hometown
    FROM waitlist_entries w JOIN users u ON u.id = w.passenger_id
    WHERE w.ride_id = ? ORDER BY w.created_at`, rideId);
}

function bookingsForUser(userId) {
  return queryRows(`SELECT b.*, r.origin, r.destination, r.departure_at, r.expected_arrival_at, r.car,
    d.name AS driver_name, p.name AS passenger_name,
    (SELECT status FROM payment_records WHERE booking_id = b.id AND kind = 'refund' ORDER BY created_at DESC LIMIT 1) AS refund_status,
    (SELECT due_at FROM payment_records WHERE booking_id = b.id AND kind = 'refund' ORDER BY created_at DESC LIMIT 1) AS refund_due_at
    FROM bookings b JOIN rides r ON r.id = b.ride_id
    JOIN users d ON d.id = r.driver_id JOIN users p ON p.id = b.passenger_id
    WHERE b.passenger_id = ? OR r.driver_id = ? ORDER BY b.created_at DESC`, userId, userId)
    .map(booking => withNoShow(withRequestExpiry({ ...booking, passenger_reliability: reliabilitySummary(booking.passenger_id), trip_confirmations: tripConfirmations(booking.id), reconfirmations: bookingReconfirmations(booking.id) })));
}

function bookingReconfirmations(bookingId) {
  return queryRows(`SELECT rc.booking_id, rc.stage_hours, rc.user_id, rc.coming, rc.responded_at, u.name AS user_name
    FROM booking_reconfirmations rc JOIN users u ON u.id = rc.user_id WHERE rc.booking_id = ? ORDER BY rc.stage_hours DESC, rc.responded_at`, bookingId);
}

function reconfirmBooking(bookingId, userId, stageHours, coming) {
  const booking = getBooking(bookingId);
  if (!booking || ![booking.driver_id, booking.passenger_id].includes(userId)) throw new Error('Only a traveler on this booking can reconfirm.');
  if (booking.status !== 'confirmed') throw new Error('Only a confirmed booking can be reconfirmed.');
  if (![72, 48, 12].includes(Number(stageHours))) throw new Error('Choose a valid trip check-in.');
  if (typeof coming !== 'boolean') throw new Error('Choose whether you are still coming.');
  const hoursUntilDeparture = (new Date(booking.departure_at).getTime() - Date.now()) / 3600000;
  if (hoursUntilDeparture < 0 || hoursUntilDeparture > Number(stageHours)) throw new Error('This check-in opens when departure is within its scheduled window.');
  if (Number(stageHours) === 72 && userId !== booking.passenger_id) throw new Error('The 72-hour check-in is for the passenger.');
  if (queryRow('SELECT 1 FROM booking_reconfirmations WHERE booking_id = ? AND stage_hours = ? AND user_id = ?', bookingId, Number(stageHours), userId)) throw new Error('You already answered this check-in.');
  db.prepare('INSERT INTO booking_reconfirmations (booking_id, stage_hours, user_id, coming, responded_at) VALUES (?, ?, ?, ?, ?)')
    .run(bookingId, Number(stageHours), userId, coming ? 1 : 0, nowIso());
  return getBooking(bookingId);
}

function tripConfirmations(bookingId) {
  return queryRows(`SELECT t.booking_id, t.user_id, t.happened, t.responded_at, u.name AS user_name
    FROM trip_confirmations t JOIN users u ON u.id = t.user_id WHERE t.booking_id = ? ORDER BY t.responded_at`, bookingId);
}

function confirmTrip(bookingId, userId, happened) {
  const booking = getBooking(bookingId);
  if (!booking || ![booking.driver_id, booking.passenger_id].includes(userId)) throw new Error('Only a confirmed traveler can answer this check.');
  if (booking.status !== 'confirmed') throw new Error('Only confirmed trips can be checked.');
  if (booking.no_show_case) throw new Error('A no-show report is open for this booking; resolve it before recording a trip confirmation.');
  if (new Date(booking.expected_arrival_at).getTime() > Date.now()) throw new Error('Trip confirmation opens after the estimated arrival time.');
  if (typeof happened !== 'boolean') throw new Error('Choose whether the trip happened.');
  if (queryRow('SELECT 1 FROM trip_confirmations WHERE booking_id = ? AND user_id = ?', bookingId, userId)) {
    throw new Error('You already answered this trip check.');
  }
  db.prepare('INSERT INTO trip_confirmations (booking_id, user_id, happened, responded_at) VALUES (?, ?, ?, ?)')
    .run(bookingId, userId, happened ? 1 : 0, nowIso());
  return getBooking(bookingId);
}

function markNoShow(bookingId, driverId) {
  const booking = getBooking(bookingId);
  if (!booking || booking.driver_id !== driverId) throw new Error('Only this ride’s driver can report a passenger no-show.');
  if (booking.status !== 'confirmed') throw new Error('Only a confirmed booking can be marked as a no-show.');
  if (Date.now() < new Date(booking.departure_at).getTime() + 30 * 60000) throw new Error('A no-show can be reported 30 minutes after scheduled departure.');
  if (queryRow('SELECT 1 FROM trip_confirmations WHERE booking_id = ? AND happened = 1 LIMIT 1', bookingId)) throw new Error('A traveler has confirmed the trip happened, so it cannot be marked as a no-show.');
  if (booking.no_show_case) throw new Error('A no-show report already exists for this booking.');
  db.prepare(`INSERT INTO no_show_cases (booking_id, passenger_id, driver_id, status, marked_at)
    VALUES (?, ?, ?, 'pending', ?)`)
    .run(bookingId, booking.passenger_id, driverId, nowIso());
  return getBooking(bookingId);
}

function disputeNoShow(bookingId, passengerId) {
  const booking = getBooking(bookingId);
  if (!booking || booking.passenger_id !== passengerId) throw new Error('Only the passenger can dispute this no-show report.');
  const record = queryRow('SELECT status, marked_at FROM no_show_cases WHERE booking_id = ?', bookingId);
  if (!record || record.status !== 'pending') throw new Error('There is no open no-show report to dispute.');
  if (Date.now() >= new Date(record.marked_at).getTime() + 24 * 3600000) throw new Error('The 24-hour dispute window has closed.');
  db.prepare("UPDATE no_show_cases SET status = 'disputed', disputed_at = ? WHERE booking_id = ?").run(nowIso(), bookingId);
  return getBooking(bookingId);
}

function simulateArrival(rideId, driverId) {
  const ride = getRide(rideId);
  if (!ride || ride.driver_id !== driverId) throw new Error('Only this ride’s driver can use the demo arrival control.');
  if (ride.status === 'cancelled') throw new Error('A cancelled ride cannot be marked as arrived.');
  const confirmed = queryRow("SELECT COUNT(*) AS n FROM bookings WHERE ride_id = ? AND status = 'confirmed'", rideId).n;
  if (confirmed < 1) throw new Error('Confirm at least one passenger before simulating arrival.');
  const current = new Date();
  const localNow = new Date(current.getTime() - current.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  db.prepare('UPDATE rides SET expected_arrival_at = ? WHERE id = ?').run(localNow, rideId);
  return getRide(rideId);
}

function confirmRefundReceived(bookingId, passengerId) {
  const booking = getBooking(bookingId);
  if (!booking || booking.passenger_id !== passengerId) throw new Error('Only the passenger can confirm the refund.');
  const payment = queryRow("SELECT id, status FROM payment_records WHERE booking_id = ? AND kind = 'refund' ORDER BY created_at DESC LIMIT 1", bookingId);
  if (!payment || payment.status !== 'due') throw new Error('There is no refund awaiting confirmation.');
  db.prepare("UPDATE payment_records SET status = 'confirmed', confirmed_at = ? WHERE id = ?")
    .run(nowIso(), payment.id);
  return getBooking(bookingId);
}

function reportsForUser(userId) {
  if (!user(userId)) throw new Error('Choose a valid demo profile.');
  return queryRows(`SELECT r.id, r.booking_id, r.reason, r.details, r.status, r.created_at,
      target.name AS reported_name, ride.origin, ride.destination
    FROM reports r JOIN users target ON target.id = r.reported_id
    JOIN bookings b ON b.id = r.booking_id JOIN rides ride ON ride.id = b.ride_id
    WHERE r.reporter_id = ? ORDER BY r.created_at DESC`, userId);
}

function reportUser(bookingId, reporterId, reason, details = '') {
  const allowed = new Set(['unsafe_driving', 'harassment', 'misleading_ride', 'payment_dispute', 'no_show', 'other']);
  const booking = getBooking(bookingId);
  if (!booking || ![booking.driver_id, booking.passenger_id].includes(reporterId)) throw new Error('Only someone on this booking can report a participant.');
  if (!allowed.has(reason)) throw new Error('Choose a report reason from the list.');
  const reportedId = reporterId === booking.driver_id ? booking.passenger_id : booking.driver_id;
  const text = String(details || '').trim();
  if (text.length > 1000) throw new Error('Report details must be 1,000 characters or fewer.');
  const reportId = id('report');
  db.prepare(`INSERT INTO reports (id, reporter_id, reported_id, booking_id, reason, details, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, 'open', ?)`)
    .run(reportId, reporterId, reportedId, bookingId, reason, text, nowIso());
  return queryRow('SELECT id, booking_id, reason, details, status, created_at FROM reports WHERE id = ?', reportId);
}

function blockBookingParticipant(bookingId, blockerId) {
  const booking = getBooking(bookingId);
  if (!booking || ![booking.driver_id, booking.passenger_id].includes(blockerId)) throw new Error('Only someone on this booking can block a participant.');
  const blockedId = blockerId === booking.driver_id ? booking.passenger_id : booking.driver_id;
  db.prepare('INSERT OR IGNORE INTO blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, ?)')
    .run(blockerId, blockedId, nowIso());
  return { blocked_user: user(blockedId) };
}

function createRide(driverId, input) {
  if (driverId !== 'driver-aditi') throw new Error('Choose the demo driver account to post a ride.');
  const origin = String(input.origin || '').trim();
  const destination = String(input.destination || '').trim();
  const car = String(input.car || '').trim();
  const departure = new Date(input.departure_at);
  const seats = Number(input.seats_offered);
  const fare = Number(input.fare_inr);
  const requestedAdvance = Number(input.advance_inr);
  const durationHours = Number(input.duration_hours || 14);
  if (!origin || !destination || origin === destination) throw new Error('Choose two different cities.');
  if (!car) throw new Error('Add the car details.');
  if (Number.isNaN(departure.getTime()) || departure.getTime() < Date.now() + 6 * 60 * 60 * 1000) throw new Error('Departure must be at least 6 hours from now.');
  if (!Number.isInteger(seats) || seats < 1 || seats > 7) throw new Error('Seats must be between 1 and 7.');
  if (!Number.isInteger(durationHours) || durationHours < 1 || durationHours > 24) throw new Error('Estimated duration must be between 1 and 24 hours.');
  if (!Number.isInteger(fare) || fare < 0 || !Number.isInteger(requestedAdvance) || requestedAdvance < 0 || requestedAdvance > fare) throw new Error('Enter a valid fare and advance.');
  const advance = Math.min(1000, Math.max(300, Math.round((fare * 0.3) / 50) * 50));
  const arrival = new Date(departure.getTime() + durationHours * 3600000);
  const expectedArrival = new Date(arrival.getTime() - arrival.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  const rideId = id('ride');
  db.prepare(`INSERT INTO rides
    (id, driver_id, origin, destination, departure_at, expected_arrival_at, seats_offered, fare_inr, advance_inr, car, women_only, notes, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)`)
    .run(rideId, driverId, origin, destination, input.departure_at, expectedArrival, seats, fare, advance, car,
      input.women_only ? 1 : 0, String(input.notes || '').trim(), nowIso());
  return getRide(rideId);
}

function requestSeat(rideId, passengerId, note) {
  if (user(passengerId)?.role !== 'passenger') throw new Error('Choose a demo passenger account to request a seat.');
  const ride = getRide(rideId);
  if (!ride || ride.status === 'cancelled') throw new Error('This ride is no longer available.');
  if (isBlockedBetween(passengerId, ride.driver_id)) throw new Error('This ride is unavailable between blocked members.');
  if (ride.driver_id === passengerId) throw new Error('You cannot request your own ride.');
  if (new Date(ride.departure_at).getTime() - Date.now() <= 12 * 3600000) throw new Error('Seat requests close 12 hours before departure.');
  if (ride.seats_left < 1) throw new Error('This ride has no available seats.');
  const existing = queryRow('SELECT id FROM bookings WHERE ride_id = ? AND passenger_id = ?', rideId, passengerId);
  if (existing) throw new Error('You already have a booking record for this ride.');
  const bookingId = id('booking');
  const createdAt = nowIso();
  const requestExpiresAt = new Date(Math.min(Date.now() + 12 * 3600000, new Date(ride.departure_at).getTime() - 12 * 3600000)).toISOString();
  db.prepare(`INSERT INTO bookings
    (id, ride_id, passenger_id, note, status, fare_inr, advance_inr, free_cancel_until, full_penalty_from, request_expires_at, created_at)
    VALUES (?, ?, ?, ?, 'requested', ?, ?, ?, ?, ?, ?)`)
    .run(bookingId, rideId, passengerId, String(note || '').trim(), ride.fare_inr, ride.advance_inr,
      new Date(new Date(ride.departure_at).getTime() - 48 * 3600000).toISOString(),
      new Date(new Date(ride.departure_at).getTime() - 12 * 3600000).toISOString(), requestExpiresAt, createdAt);
  return getBooking(bookingId);
}

function offerNextWaitlist(rideId) {
  const current = queryRow("SELECT id FROM waitlist_entries WHERE ride_id = ? AND status = 'offered' AND offer_expires_at > ?", rideId, nowIso());
  if (current) return current.id;
  db.prepare("UPDATE waitlist_entries SET status = 'expired' WHERE ride_id = ? AND status = 'offered' AND offer_expires_at <= ?")
    .run(rideId, nowIso());
  const next = queryRow("SELECT * FROM waitlist_entries WHERE ride_id = ? AND status = 'waiting' ORDER BY created_at LIMIT 1", rideId);
  const ride = getRide(rideId);
  if (!next || !ride || ride.seats_left < 1) return null;
  const source = queryRow(`SELECT id FROM bookings WHERE ride_id = ? AND status = 'cancelled_passenger'
    AND refilled_by_booking_id IS NULL ORDER BY cancelled_at LIMIT 1`, rideId);
  const duration = new Date(ride.departure_at).getTime() - Date.now() < 12 * 3600000 ? 30 * 60000 : 2 * 3600000;
  db.prepare("UPDATE waitlist_entries SET status = 'offered', offered_at = ?, offer_expires_at = ?, source_booking_id = ? WHERE id = ?")
    .run(nowIso(), new Date(Date.now() + duration).toISOString(), source?.id || null, next.id);
  return next.id;
}

function joinWaitlist(rideId, passengerId) {
  if (user(passengerId)?.role !== 'passenger') throw new Error('Choose a demo passenger account to join the waitlist.');
  const ride = getRide(rideId);
  if (!ride || ride.status === 'cancelled') throw new Error('This ride is no longer available.');
  if (isBlockedBetween(passengerId, ride.driver_id)) throw new Error('This ride is unavailable between blocked members.');
  if (ride.driver_id === passengerId) throw new Error('You cannot join your own ride waitlist.');
  if (ride.seats_left > 0) throw new Error('There is still a seat available. Request it directly.');
  if (queryRow('SELECT id FROM waitlist_entries WHERE ride_id = ? AND passenger_id = ?', rideId, passengerId)) throw new Error('You already joined this ride’s waitlist.');
  const entryId = id('wait');
  db.prepare("INSERT INTO waitlist_entries (id, ride_id, passenger_id, status, created_at) VALUES (?, ?, ?, 'waiting', ?)")
    .run(entryId, rideId, passengerId, nowIso());
  return queryRow('SELECT * FROM waitlist_entries WHERE id = ?', entryId);
}

function acceptWaitlistOffer(entryId, passengerId) {
  const entry = queryRow('SELECT * FROM waitlist_entries WHERE id = ?', entryId);
  if (!entry || entry.passenger_id !== passengerId) throw new Error('Only this passenger can accept the offer.');
  if (entry.status !== 'offered') throw new Error('There is no active seat offer for this entry.');
  if (new Date(entry.offer_expires_at).getTime() <= Date.now()) {
    db.prepare("UPDATE waitlist_entries SET status = 'expired' WHERE id = ?").run(entryId);
    offerNextWaitlist(entry.ride_id);
    throw new Error('This offer expired. The next person in line has been offered the seat.');
  }
  const ride = getRide(entry.ride_id);
  if (!ride || ride.seats_left < 1) throw new Error('That seat is no longer available.');
  if (isBlockedBetween(passengerId, ride.driver_id)) throw new Error('This ride is unavailable between blocked members.');
  const bookingId = id('booking');
  const departure = new Date(ride.departure_at).getTime();
  transaction(() => {
    db.prepare(`INSERT INTO bookings
      (id, ride_id, passenger_id, note, status, fare_inr, advance_inr, free_cancel_until, full_penalty_from, waitlist_entry_id, created_at)
      VALUES (?, ?, ?, 'Accepted from waitlist offer', 'accepted', ?, ?, ?, ?, ?, ?)`)
      .run(bookingId, ride.id, passengerId, ride.fare_inr, ride.advance_inr,
        new Date(departure - 48 * 3600000).toISOString(), new Date(departure - 12 * 3600000).toISOString(), entryId, nowIso());
    db.prepare("UPDATE waitlist_entries SET status = 'accepted' WHERE id = ?").run(entryId);
  });
  return getBooking(bookingId);
}

function acceptBooking(bookingId, driverId) {
  const booking = getBooking(bookingId);
  if (!booking || booking.driver_id !== driverId) throw new Error('Only this ride’s driver can accept the request.');
  if (booking.status !== 'requested') throw new Error('This request is no longer waiting for a decision.');
  if (booking.request_expired) throw new Error('This request expired and can no longer be accepted.');
  const held = queryRow(`SELECT COUNT(*) AS n FROM bookings WHERE ride_id = ? AND status IN ('accepted','advance_claimed','confirmed')`, booking.ride_id).n;
  const ride = getRide(booking.ride_id);
  if (held >= ride.seats_offered) throw new Error('No seat is available to accept.');
  db.prepare("UPDATE bookings SET status = 'accepted', accepted_at = ? WHERE id = ?").run(nowIso(), bookingId);
  return getBooking(bookingId);
}

function claimAdvance(bookingId, passengerId) {
  const booking = getBooking(bookingId);
  if (!booking || booking.passenger_id !== passengerId) throw new Error('Only this passenger can record the advance claim.');
  if (booking.status !== 'accepted') throw new Error('The driver must accept before the advance is recorded.');
  const paymentId = id('payment');
  transaction(() => {
    db.prepare("UPDATE bookings SET status = 'advance_claimed' WHERE id = ?").run(bookingId);
    db.prepare(`INSERT INTO payment_records (id, booking_id, kind, amount_inr, status, created_at)
      VALUES (?, ?, 'advance', ?, 'claimed', ?)`)
      .run(paymentId, bookingId, booking.advance_inr, nowIso());
  });
  return getBooking(bookingId);
}

function confirmAdvance(bookingId, driverId) {
  const booking = getBooking(bookingId);
  if (!booking || booking.driver_id !== driverId) throw new Error('Only this ride’s driver can confirm the advance.');
  if (booking.status !== 'advance_claimed') throw new Error('The passenger has not recorded an advance claim.');
  transaction(() => {
    db.prepare("UPDATE bookings SET status = 'confirmed', confirmed_at = ? WHERE id = ?").run(nowIso(), bookingId);
    db.prepare("UPDATE payment_records SET status = 'confirmed', confirmed_at = ? WHERE booking_id = ? AND kind = 'advance'")
      .run(nowIso(), bookingId);
    if (booking.waitlist_entry_id) {
      const source = queryRow(`SELECT b.id, b.advance_inr, b.refund_outcome FROM bookings b
        JOIN waitlist_entries w ON w.source_booking_id = b.id WHERE w.id = ?`, booking.waitlist_entry_id);
      if (source) {
        db.prepare("UPDATE bookings SET refilled_by_booking_id = ?, refund_outcome = 'full', refund_inr = advance_inr WHERE id = ?")
          .run(bookingId, source.id);
        const refund = queryRow("SELECT id FROM payment_records WHERE booking_id = ? AND kind = 'refund'", source.id);
        if (refund) {
          db.prepare("UPDATE payment_records SET amount_inr = ?, status = 'due', due_at = ?, confirmed_at = NULL WHERE id = ?")
            .run(source.advance_inr, refundDueAt(), refund.id);
        } else {
          db.prepare(`INSERT INTO payment_records (id, booking_id, kind, amount_inr, status, due_at, created_at)
            VALUES (?, ?, 'refund', ?, 'due', ?, ?)`)
            .run(id('payment'), source.id, source.advance_inr, refundDueAt(), nowIso());
        }
        db.prepare('UPDATE waitlist_entries SET refills_booking_id = ? WHERE id = ?')
          .run(source.id, booking.waitlist_entry_id);
      }
    }
  });
  return getBooking(bookingId);
}

function cancelBooking(bookingId, passengerId) {
  const booking = getBooking(bookingId);
  if (!booking || booking.passenger_id !== passengerId) throw new Error('Only this passenger can cancel the booking.');
  if (!['accepted', 'advance_claimed', 'confirmed'].includes(booking.status)) throw new Error('This booking cannot be cancelled now.');
  if (booking.status !== 'confirmed') throw new Error('Confirm the advance before using the cancellation flow.');
  const hoursLeft = (new Date(booking.departure_at).getTime() - Date.now()) / 3600000;
  if (hoursLeft < 0) throw new Error('The scheduled departure has passed.');
  let refundInr = 0;
  let outcome = 'pending_refill';
  if (hoursLeft > 48) {
    refundInr = booking.advance_inr;
    outcome = 'full';
  }
  const cancelledAt = nowIso();
  transaction(() => {
    db.prepare(`UPDATE bookings SET status = 'cancelled_passenger', cancelled_at = ?, refund_outcome = ?, refund_inr = ? WHERE id = ?`)
      .run(cancelledAt, outcome, refundInr, bookingId);
    if (refundInr > 0) {
      db.prepare(`INSERT INTO payment_records (id, booking_id, kind, amount_inr, status, due_at, created_at)
        VALUES (?, ?, 'refund', ?, 'due', ?, ?)`)
        .run(id('payment'), bookingId, refundInr, refundDueAt(), cancelledAt);
    }
    const ride = getRide(booking.ride_id);
    const remaining = queryRow(`SELECT COUNT(*) AS n FROM bookings WHERE ride_id = ? AND status IN ('accepted','advance_claimed','confirmed')`, booking.ride_id).n;
    db.prepare('UPDATE rides SET status = ? WHERE id = ?').run(remaining >= ride.seats_offered ? 'full' : 'open', booking.ride_id);
  });
  offerNextWaitlist(booking.ride_id);
  return { booking: getBooking(bookingId), outcome, refund_inr: refundInr };
}

function cancelRide(rideId, driverId) {
  const ride = getRide(rideId);
  if (!ride || ride.driver_id !== driverId) throw new Error('Only this ride’s driver can cancel it.');
  if (ride.status === 'cancelled') throw new Error('This ride is already cancelled.');
  const hoursBeforeDeparture = (new Date(ride.departure_at).getTime() - Date.now()) / 3600000;
  if (hoursBeforeDeparture < 0) throw new Error('The scheduled departure has passed.');
  const kind = hoursBeforeDeparture < 48 ? 'late_cancel' : 'early_cancel';
  transaction(() => {
    db.prepare("UPDATE rides SET status = 'cancelled', cancelled_at = ? WHERE id = ?").run(nowIso(), rideId);
    const bookings = queryRows(`SELECT * FROM bookings WHERE ride_id = ?
      AND status IN ('requested','accepted','advance_claimed','confirmed')`, rideId);
    for (const booking of bookings) {
      db.prepare("UPDATE bookings SET status = 'cancelled_passenger', cancelled_at = ?, cancelled_by_role = 'driver', refund_outcome = 'full', refund_inr = ? WHERE id = ?")
        .run(nowIso(), booking.status === 'advance_claimed' || booking.status === 'confirmed' ? booking.advance_inr : 0, booking.id);
      if (booking.status === 'advance_claimed' || booking.status === 'confirmed') {
        db.prepare(`INSERT INTO payment_records (id, booking_id, kind, amount_inr, status, due_at, created_at)
          VALUES (?, ?, 'refund', ?, 'due', ?, ?)`)
          .run(id('payment'), booking.id, booking.advance_inr, refundDueAt(), nowIso());
      }
    }
    db.prepare("UPDATE waitlist_entries SET status = 'expired' WHERE ride_id = ? AND status IN ('waiting','offered')").run(rideId);
    db.prepare(`INSERT INTO reliability_events (id, user_id, ride_id, kind, hours_before_departure, created_at)
      VALUES (?, ?, ?, ?, ?, ?)`)
      .run(id('event'), driverId, rideId, kind, hoursBeforeDeparture, nowIso());
  });
  return { ride: getRide(rideId), affected_bookings: bookingsForRide(rideId), kind };
}

module.exports = { user, listRides, getRide, canViewRide, getBooking, bookingsForRide, waitlistForRide, bookingsForUser, reportsForUser, reportUser, blockBookingParticipant, reliabilitySummary, createRide, requestSeat, joinWaitlist, acceptWaitlistOffer, acceptBooking, claimAdvance, confirmAdvance, cancelBooking, cancelRide, confirmTrip, simulateArrival, confirmRefundReceived, reconfirmBooking, markNoShow, disputeNoShow };
