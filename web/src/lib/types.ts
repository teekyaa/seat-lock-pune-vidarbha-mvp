export type When = { utc: string; ist: string };

export type Reliability = {
  completed_trips: number;
  passenger_early_cancellations: number;
  passenger_late_cancellations: number;
  driver_early_cancellations: number;
  driver_late_cancellations: number;
  driver_changes: number;
  no_shows: number;
  open_refund_disputes: number;
};

export type PublicUser = {
  id: string;
  name: string;
  hometown: string;
  photo_url: string;
  member_since: string;
  id_verified: boolean;
  women_only_verified: boolean;
  reliability: Reliability;
};

export type Me = {
  id: string;
  phone: string;
  name: string;
  hometown: string;
  gender: "female" | "male" | "other" | "undisclosed";
  college_or_workplace: string;
  photo_url: string;
  email: string;
  upi_id: string;
  women_only_eligible: boolean;
  id_verified: boolean;
  terms_accepted_at: string | null;
  profile_complete: boolean;
};

export type Vehicle = { id: number; make_model: string; colour: string; registration: string; passenger_seats: number };

export type CityPair = {
  id: number;
  origin: string;
  destination: string;
  distance_km: number;
  tolls_inr: number;
  typical_duration_hours: number;
};

export type FareQuote = {
  suggested_fare_inr: number;
  max_fare_inr: number;
  advance_inr: number;
  distance_km: number;
  tolls_inr: number;
  fuel_cost_per_km: string;
  seats_offered: number;
  policy_version: string;
};

export type Policy = { label: string; summary: string; advance_percent: number; hold_hours: number; refund_due_hours: number };

export type Cutoffs = { full_refund_until: When; full_penalty_from: When };

export type Ride = {
  code: string;
  origin: string;
  destination: string;
  distance_km: number;
  departure_at: When;
  expected_arrival_at: When;
  pickup_point: string;
  dropoff_point: string;
  seats_offered: number;
  seats_left: number;
  fare_inr: number;
  suggested_fare_inr: number;
  advance_inr: number;
  women_only: boolean;
  notes: string;
  status: "open" | "cancelled" | "departed";
  driver: PublicUser;
  vehicle: { make_model: string; colour: string };
  policy?: Policy;
  cutoffs?: Cutoffs;
  requests_close_at?: When;
  viewer?: {
    is_driver: boolean;
    booking_code: string | null;
    waitlist: { id: number; status: string; offer_expires_at: When | null } | null;
  };
  private?: { driver_phone: string; registration: string; pickup_details: string };
};

export type Booking = {
  code: string;
  status: string;
  status_label: string;
  role: "driver" | "passenger";
  ride: Ride;
  ride_code: string;
  passenger: PublicUser;
  note: string;
  fare_inr: number;
  advance_inr: number;
  policy: Policy;
  cutoffs: Cutoffs | null;
  free_cancel_any_time: boolean;
  at_risk: boolean;
  request_expires_at: When | null;
  hold_expires_at: When | null;
  confirmed_at: When | null;
  cancelled_at: When | null;
  refund_outcome: "full" | "half" | "none" | "pending_refill" | null;
  penalty_tier: "half" | "all" | null;
  refund_inr: number | null;
  refund: { amount_inr: number; status: string; due_at: When; dispute_at: When; confirmed_at: When | null; overdue: boolean } | null;
  reconfirmations: { stage_hours: number; who: string; coming: boolean; at: When }[];
  trip_confirmations: { who: string; happened: boolean }[];
  no_show: { status: string; dispute_until: When } | null;
  actions: string[];
  pay?: { upi_link: string; amount_inr: number; pay_by: When };
  refund_pay?: { upi_link: string; amount_inr: number };
  contact?: { phone: string; registration?: string; pickup_details?: string };
};

export type InboxItem = { id: number; kind: string; title: string; body: string; url: string; sent_at: When; read: boolean };
