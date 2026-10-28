const fs = require('node:fs');
const path = require('node:path');
const { DatabaseSync } = require('node:sqlite');

const dataDir = path.join(__dirname, '..', 'data');
fs.mkdirSync(dataDir, { recursive: true });
const configuredDbPath = process.env.SEATLOCK_DB_PATH;
const dbPath = configuredDbPath === ':memory:' ? ':memory:' : path.resolve(configuredDbPath || path.join(dataDir, 'seat-lock-prototype.sqlite'));
const db = new DatabaseSync(dbPath);

db.exec(`
  PRAGMA foreign_keys = ON;
  CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('driver', 'passenger')),
    hometown TEXT NOT NULL,
    phone TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS rides (
    id TEXT PRIMARY KEY,
    driver_id TEXT NOT NULL REFERENCES users(id),
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departure_at TEXT NOT NULL,
    expected_arrival_at TEXT,
    seats_offered INTEGER NOT NULL CHECK (seats_offered BETWEEN 1 AND 7),
    fare_inr INTEGER NOT NULL CHECK (fare_inr >= 0),
    advance_inr INTEGER NOT NULL CHECK (advance_inr >= 0),
    car TEXT NOT NULL,
    women_only INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'full', 'cancelled')),
    created_at TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS bookings (
    id TEXT PRIMARY KEY,
    ride_id TEXT NOT NULL REFERENCES rides(id),
    passenger_id TEXT NOT NULL REFERENCES users(id),
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('requested', 'accepted', 'advance_claimed', 'confirmed', 'cancelled_passenger')),
    fare_inr INTEGER NOT NULL,
    advance_inr INTEGER NOT NULL,
    free_cancel_until TEXT NOT NULL,
    full_penalty_from TEXT NOT NULL,
    request_expires_at TEXT,
    accepted_at TEXT,
    confirmed_at TEXT,
    cancelled_at TEXT,
    refund_outcome TEXT,
    refund_inr INTEGER,
    refilled_by_booking_id TEXT REFERENCES bookings(id),
    waitlist_entry_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (id)
  );
  CREATE TABLE IF NOT EXISTS payment_records (
    id TEXT PRIMARY KEY,
    booking_id TEXT NOT NULL REFERENCES bookings(id),
    kind TEXT NOT NULL CHECK (kind IN ('advance', 'refund')),
    amount_inr INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('claimed', 'confirmed', 'due')),
    due_at TEXT,
    created_at TEXT NOT NULL,
    confirmed_at TEXT
  );
  CREATE TABLE IF NOT EXISTS waitlist_entries (
    id TEXT PRIMARY KEY,
    ride_id TEXT NOT NULL REFERENCES rides(id),
    passenger_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL CHECK (status IN ('waiting', 'offered', 'accepted', 'expired', 'withdrawn')),
    offered_at TEXT,
    offer_expires_at TEXT,
    source_booking_id TEXT REFERENCES bookings(id),
    refills_booking_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (ride_id, passenger_id)
  );
  CREATE TABLE IF NOT EXISTS reliability_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    ride_id TEXT NOT NULL REFERENCES rides(id),
    kind TEXT NOT NULL CHECK (kind IN ('early_cancel', 'late_cancel')),
    hours_before_departure REAL NOT NULL,
    created_at TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    reporter_id TEXT NOT NULL REFERENCES users(id),
    reported_id TEXT NOT NULL REFERENCES users(id),
    booking_id TEXT NOT NULL REFERENCES bookings(id),
    reason TEXT NOT NULL CHECK (reason IN ('unsafe_driving','harassment','misleading_ride','payment_dispute','no_show','other')),
    details TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','actioned','dismissed')),
    created_at TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS blocks (
    blocker_id TEXT NOT NULL REFERENCES users(id),
    blocked_id TEXT NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (blocker_id, blocked_id),
    CHECK (blocker_id != blocked_id)
  );
  CREATE TABLE IF NOT EXISTS trip_confirmations (
    booking_id TEXT NOT NULL REFERENCES bookings(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    happened INTEGER NOT NULL CHECK (happened IN (0, 1)),
    responded_at TEXT NOT NULL,
    PRIMARY KEY (booking_id, user_id)
  );
  CREATE TABLE IF NOT EXISTS booking_reconfirmations (
    booking_id TEXT NOT NULL REFERENCES bookings(id),
    stage_hours INTEGER NOT NULL CHECK (stage_hours IN (72, 48, 12)),
    user_id TEXT NOT NULL REFERENCES users(id),
    coming INTEGER NOT NULL CHECK (coming IN (0, 1)),
    responded_at TEXT NOT NULL,
    PRIMARY KEY (booking_id, stage_hours, user_id)
  );
  CREATE TABLE IF NOT EXISTS no_show_cases (
    booking_id TEXT PRIMARY KEY REFERENCES bookings(id),
    passenger_id TEXT NOT NULL REFERENCES users(id),
    driver_id TEXT NOT NULL REFERENCES users(id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'disputed')),
    marked_at TEXT NOT NULL,
    disputed_at TEXT
  );
`);

const bookingColumns = new Set(db.prepare('PRAGMA table_info(bookings)').all().map(column => column.name));
if (!bookingColumns.has('refilled_by_booking_id')) db.exec('ALTER TABLE bookings ADD COLUMN refilled_by_booking_id TEXT REFERENCES bookings(id)');
if (!bookingColumns.has('waitlist_entry_id')) db.exec('ALTER TABLE bookings ADD COLUMN waitlist_entry_id TEXT');
if (!bookingColumns.has('cancelled_by_role')) db.exec('ALTER TABLE bookings ADD COLUMN cancelled_by_role TEXT');
if (!bookingColumns.has('request_expires_at')) db.exec('ALTER TABLE bookings ADD COLUMN request_expires_at TEXT');
const waitlistColumns = new Set(db.prepare('PRAGMA table_info(waitlist_entries)').all().map(column => column.name));
if (!waitlistColumns.has('source_booking_id')) db.exec('ALTER TABLE waitlist_entries ADD COLUMN source_booking_id TEXT REFERENCES bookings(id)');
const rideColumns = new Set(db.prepare('PRAGMA table_info(rides)').all().map(column => column.name));
if (!rideColumns.has('cancelled_at')) db.exec('ALTER TABLE rides ADD COLUMN cancelled_at TEXT');
if (!rideColumns.has('expected_arrival_at')) db.exec('ALTER TABLE rides ADD COLUMN expected_arrival_at TEXT');
const estimateArrival = db.prepare('UPDATE rides SET expected_arrival_at = ? WHERE id = ?');
for (const ride of db.prepare('SELECT id, departure_at FROM rides WHERE expected_arrival_at IS NULL').all()) {
  const arrival = new Date(new Date(ride.departure_at).getTime() + 14 * 3600000);
  const localArrival = new Date(arrival.getTime() - arrival.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  estimateArrival.run(localArrival, ride.id);
}
const paymentColumns = new Set(db.prepare('PRAGMA table_info(payment_records)').all().map(column => column.name));
if (!paymentColumns.has('due_at')) db.exec('ALTER TABLE payment_records ADD COLUMN due_at TEXT');

const count = db.prepare('SELECT COUNT(*) AS count FROM users').get().count;
if (count === 0) {
  const seed = () => {
    const addUser = db.prepare('INSERT INTO users (id, name, role, hometown, phone) VALUES (?, ?, ?, ?, ?)');
    addUser.run('driver-aditi', 'Aditi Deshmukh', 'driver', 'Nagpur', '+91 90000 10001');
    addUser.run('passenger-rahul', 'Rahul Patil', 'passenger', 'Wardha', '+91 90000 10002');
    const departure = new Date();
    departure.setDate(departure.getDate() + 10);
    departure.setHours(21, 0, 0, 0);
    const localDeparture = new Date(departure.getTime() - departure.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
    const localArrival = new Date(new Date(localDeparture).getTime() + 14 * 3600000 - new Date(localDeparture).getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    db.prepare(`INSERT INTO rides
      (id, driver_id, origin, destination, departure_at, expected_arrival_at, seats_offered, fare_inr, advance_inr, car, notes, status, created_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)`)
      .run('ride-sample', 'driver-aditi', 'Pune', 'Nagpur', localDeparture, localArrival, 2, 2200, 650,
        'Blue Hyundai i20 · MH 31 demo', 'One stop near Amravati. Please travel light.', new Date().toISOString());
  };
  seed();
}

db.prepare(`INSERT OR IGNORE INTO users (id, name, role, hometown, phone)
  VALUES ('passenger-neha', 'Neha Kulkarni', 'passenger', 'Wardha', '+91 90000 10003')`).run();

function transaction(callback) {
  db.exec('BEGIN IMMEDIATE');
  try {
    const result = callback();
    db.exec('COMMIT');
    return result;
  } catch (error) {
    db.exec('ROLLBACK');
    throw error;
  }
}

module.exports = { db, transaction };
