const state = { userId: null, users: [], rides: [], selectedDate: '', selectedOrigin: 'Pune', selectedDestination: 'Nagpur', view: 'find', activeRideId: null, lastBookingId: null };
const app = document.querySelector('#app');
const userSwitch = document.querySelector('#user-switch');

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
const formatMoney = value => `₹${Number(value || 0).toLocaleString('en-IN')}`;
const user = () => state.users.find(item => item.id === state.userId);
const isDriver = () => user()?.role === 'driver';
const initials = name => String(name || '').split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase();
const localDateTime = value => {
  const d = new Date(value);
  return new Intl.DateTimeFormat('en-IN', { timeZone: 'Asia/Kolkata', weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', hour12: true }).format(d);
};
const inputDateTime = value => {
  const d = new Date(value);
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
};
const exactCutoff = (departure, hours) => {
  const date = new Date(new Date(departure).getTime() - hours * 3600000);
  return new Intl.DateTimeFormat('en-IN', { timeZone:'Asia/Kolkata', weekday:'short', day:'numeric', month:'short', hour:'numeric', minute:'2-digit', hour12:true }).format(date) + ' IST';
};
const shortDate = value => new Intl.DateTimeFormat('en-IN', { timeZone:'Asia/Kolkata', weekday:'short', day:'numeric', month:'short' }).format(new Date(value));
const advanceLabel = amount => amount ? formatMoney(amount) : 'No advance';
const suggestedAdvance = fare => Math.min(1000, Math.max(300, Math.round((Number(fare || 0) * 0.3) / 50) * 50));
const trustSummary = ride => {
  const record = ride.reliability || {};
  if (!record.early_cancellations && !record.late_cancellations && !record.completed_trips && !record.no_shows && !record.open_refund_disputes) return 'New member · no recorded rides';
  const bits = [];
  if (record.completed_trips) bits.push(`${record.completed_trips} completed trip${record.completed_trips === 1 ? '' : 's'}`);
  if (record.no_shows) bits.push(`${record.no_shows} no-show${record.no_shows === 1 ? '' : 's'}`);
  const total = record.early_cancellations + record.late_cancellations;
  if (total) bits.push(`${total} cancellation${total === 1 ? '' : 's'}${record.late_cancellations ? ` · ${record.late_cancellations} late` : ''}`);
  if (record.open_refund_disputes) bits.push(`${record.open_refund_disputes} open refund dispute${record.open_refund_disputes === 1 ? '' : 's'}`);
  const timing = record.latest_cancel_hours_before == null ? '' : ` · latest ${Math.round(record.latest_cancel_hours_before)}h before departure`;
  return `${bits.join(' · ')}${timing}`;
};

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Something went wrong.');
  return payload;
}
const post = (path, data) => api(path, { method: 'POST', body: JSON.stringify(data) });
function toast(message) {
  const el = document.querySelector('#toast');
  el.textContent = message;
  el.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove('show'), 3200);
}
async function refresh() {
  const data = await api(`/api/bootstrap?userId=${encodeURIComponent(state.userId || 'passenger-rahul')}`);
  state.users = data.users;
  state.rides = data.rides;
  if (!state.userId) state.userId = state.users.find(item => item.role === 'passenger').id;
  userSwitch.innerHTML = state.users.map(item => `<option value="${esc(item.id)}">${esc(item.role === 'driver' ? 'Driver' : 'Passenger')} · ${esc(item.name.split(' ')[0])}</option>`).join('');
  userSwitch.value = state.userId;
  render();
}
function setView(view) {
  state.view = view;
  state.activeRideId = null;
  document.querySelectorAll('.nav-link').forEach(button => button.classList.toggle('active', button.dataset.view === view));
  render();
}
function baseHero(eyebrow, title, copy) {
  return `<div class="hero-row"><div><p class="eyebrow">${eyebrow}</p><h1 class="hero-title">${title}</h1><p class="hero-copy">${copy}</p></div><div class="hero-note">✳ &nbsp; Clear plans. Better journeys.</div></div>`;
}
function rideCard(ride) {
  const mine = ride.driver_id === state.userId;
  const requestWindowOpen = new Date(ride.departure_at).getTime() - Date.now() > 12 * 3600000;
  const shareUrl = `${location.origin}/?ride=${encodeURIComponent(ride.id)}`;
  const seatsLabel = ride.seats_left > 0 ? `${ride.seats_left} seat${ride.seats_left === 1 ? '' : 's'} left` : 'Full';
  return `<article class="ride-card">
    <div class="ride-card-top"><span class="ride-kicker">${ride.women_only ? 'Women-only ride' : 'Pune · Vidarbha'}</span><span class="seat-badge">${seatsLabel}</span></div>
    <div class="route-line"><div class="city-block"><div class="city-name">${esc(ride.origin)}</div><div class="city-label">Pickup city</div></div><div class="route-dots"></div><div class="city-block"><div class="city-name">${esc(ride.destination)}</div><div class="city-label">Destination</div></div></div>
    <div class="ride-meta"><span class="meta-item"><span class="meta-icon">◷</span>${esc(localDateTime(ride.departure_at))}</span><span class="meta-item"><span class="meta-icon">⌁</span>${esc(ride.car)}</span></div>
    <div class="driver-row"><div class="driver-info"><span class="avatar ${mine ? 'avatar-green' : ''}">${esc(initials(ride.driver_name))}</span><span><div class="driver-name">${esc(ride.driver_name)} ${mine ? '· You' : ''}</div><div class="driver-sub">${esc(ride.driver_hometown)} · ${esc(trustSummary(ride))}</div></span></div><div class="fare">${formatMoney(ride.fare_inr)}<small>per seat · ${advanceLabel(ride.advance_inr)} advance</small></div></div>
    <div class="card-actions">${mine ? `<button class="outline-btn" data-open-ride="${esc(ride.id)}">Manage ride</button>` : ride.seats_left > 0 ? requestWindowOpen ? `<button class="primary-btn" data-request="${esc(ride.id)}">Request a seat</button>` : `<button class="outline-btn" disabled>Request window closed</button>` : `<button class="primary-btn" data-waitlist="${esc(ride.id)}">Join waitlist</button>`}<a class="outline-btn" target="_blank" rel="noreferrer" href="https://wa.me/?text=${encodeURIComponent(`Seat Lock ride: ${ride.origin} → ${ride.destination}, ${shortDate(ride.departure_at)}. See details: ${shareUrl}`)}">Share ride ↗</a></div>
  </article>`;
}
function renderFind() {
  app.dataset.page = 'find';
  const requestedRideId = new URLSearchParams(location.search).get('ride');
  let rides = state.rides.filter(ride => ride.status !== 'cancelled');
  if (state.selectedOrigin) rides = rides.filter(ride => ride.origin.toLowerCase() === state.selectedOrigin.toLowerCase());
  if (state.selectedDestination) rides = rides.filter(ride => ride.destination.toLowerCase() === state.selectedDestination.toLowerCase());
  if (state.selectedDate) rides = rides.filter(ride => new Date(ride.departure_at).toLocaleDateString('en-CA', { timeZone:'Asia/Kolkata' }) === state.selectedDate);
  if (requestedRideId) rides.sort((a, b) => a.id === requestedRideId ? -1 : b.id === requestedRideId ? 1 : 0);
  app.innerHTML = `${baseHero('PUNE TO VIDARBHA · FESTIVE SEASON', 'The road home, <em>together.</em>', 'Find a seat with a clear plan. Every ride has its fare, advance and cancellation rules up front.')}
    <form class="search-panel" id="search-form"><label class="search-field"><span class="field-label">Leaving from</span><select name="origin"><option ${state.selectedOrigin === 'Pune' ? 'selected' : ''}>Pune</option><option ${state.selectedOrigin === 'Nagpur' ? 'selected' : ''}>Nagpur</option><option ${state.selectedOrigin === 'Wardha' ? 'selected' : ''}>Wardha</option><option ${state.selectedOrigin === 'Chandrapur' ? 'selected' : ''}>Chandrapur</option></select></label><label class="search-field"><span class="field-label">Going to</span><select name="destination"><option ${state.selectedDestination === 'Nagpur' ? 'selected' : ''}>Nagpur</option><option ${state.selectedDestination === 'Wardha' ? 'selected' : ''}>Wardha</option><option ${state.selectedDestination === 'Chandrapur' ? 'selected' : ''}>Chandrapur</option><option ${state.selectedDestination === 'Pune' ? 'selected' : ''}>Pune</option></select></label><label class="search-field"><span class="field-label">Travel date</span><input type="date" name="date" value="${esc(state.selectedDate)}"></label><button class="search-btn" type="submit">Find a seat&nbsp; →</button></form>
    <div class="section-heading"><h2>${state.selectedDate ? `Rides for ${shortDate(`${state.selectedDate}T12:00:00`)}` : 'Upcoming rides'}</h2><span class="count-pill">${rides.length} ride${rides.length === 1 ? '' : 's'} on this route</span></div>
    <div class="ride-list">${rides.length ? rides.map(rideCard).join('') : `<div class="empty-state"><strong>No rides found on this route yet</strong>Try another date or check back soon.</div>`}</div>`;
}
function renderOffer() {
  app.dataset.page = 'offer';
  if (!isDriver()) {
    app.innerHTML = `${baseHero('DRIVER SPACE', 'Your ride, <em>your rules.</em>', 'Post the seats you have and let passengers find their way home.')}<div class="empty-state"><strong>Switch to the driver demo profile to post a ride</strong>Choose “Driver · Aditi” from the profile menu in the header.</div>`;
    return;
  }
  const defaultDate = new Date(Date.now() + 5 * 86400000);
  defaultDate.setHours(21, 0, 0, 0);
  app.innerHTML = `${baseHero('DRIVER SPACE', 'Offer a seat. <em>Share the ride.</em>', 'A few details help the right passengers find you. Your policy cutoffs are calculated from departure time.')}
    <form class="form-card" id="ride-form"><h2 class="form-heading">Ride details</h2><p class="form-intro">Start with the basics. You can share the ride after posting.</p>
      <div class="form-grid"><div class="form-field"><label for="origin">Leaving from</label><select id="origin" name="origin"><option>Pune</option><option>Nagpur</option><option>Wardha</option><option>Chandrapur</option></select></div><div class="form-field"><label for="destination">Going to</label><select id="destination" name="destination"><option>Nagpur</option><option>Wardha</option><option>Chandrapur</option><option>Pune</option></select></div>
      <div class="form-field"><label for="departure">Departure date and time</label><input id="departure" name="departure_at" type="datetime-local" min="${inputDateTime(new Date(Date.now() + 6 * 3600000))}" value="${inputDateTime(defaultDate)}" required><span class="helper">Times and policy cutoffs are shown in India Standard Time.</span></div><div class="form-field"><label for="duration">Estimated trip duration · hours</label><input id="duration" name="duration_hours" type="number" min="1" max="24" value="14" required><span class="helper">Both travelers can confirm the trip after this estimate.</span></div><div class="form-field full"><label for="car">Your car</label><input id="car" name="car" value="Blue Hyundai i20 · MH 31 demo" required></div>
      <div class="form-field"><label for="seats">Seats offered</label><input id="seats" name="seats_offered" type="number" min="1" max="7" value="2" required></div><div class="inline-fields"><div class="form-field"><label for="fare">Fare per seat (₹)</label><input id="fare" name="fare_inr" type="number" min="0" step="50" value="2200" required></div><div class="form-field"><label for="advance">Advance · 30% (₹)</label><input id="advance" name="advance_inr" type="number" value="650" readonly><span class="helper">Rounded to ₹50 · min ₹300 · max ₹1,000</span></div></div>
      <div class="form-field full"><label for="notes">A note for passengers · optional</label><textarea id="notes" name="notes" placeholder="Pickup point, luggage, planned stops…"></textarea></div><label class="check-row form-field full"><input type="checkbox" name="women_only"> Women-only ride</label></div>
      <div class="form-bottom"><span class="policy-mini">Fare is entered by the driver for this demo. Cost-sharing inputs and the legal fare cap are not validated yet.</span><button class="primary-btn" type="submit">Post this ride&nbsp; →</button></div>
    </form>`;
}
function statusTitle(booking) {
  if (booking.request_expired) return 'Request expired';
  if (booking.status === 'cancelled_passenger' && booking.cancelled_by_role === 'driver') return 'Cancelled by driver';
  return ({ requested:'Awaiting driver', accepted:'Accepted · advance next', advance_claimed:'Advance claimed', confirmed:'Seat locked', cancelled_passenger:'Cancelled' })[booking.status] || booking.status;
}
function bookingCard(booking) {
  const ownDriver = booking.driver_id === state.userId;
  const isPassenger = booking.passenger_id === state.userId;
  const peerId = ownDriver ? booking.passenger_id : booking.driver_id;
  const peerName = ownDriver ? booking.passenger_name : booking.driver_name;
  let actions = '';
  if (ownDriver && booking.status === 'requested' && !booking.request_expired) actions = `<button class="primary-btn" data-accept="${esc(booking.id)}">Accept request</button>`;
  if (ownDriver && booking.status === 'advance_claimed') actions = `<button class="primary-btn" data-confirm-advance="${esc(booking.id)}">Advance received</button>`;
  if (isPassenger && booking.status === 'accepted') actions = `<button class="primary-btn" data-claim-advance="${esc(booking.id)}">I’ve paid the advance</button>`;
  if (isPassenger && booking.status === 'confirmed') actions = `<button class="outline-btn danger-btn" data-cancel="${esc(booking.id)}">Cancel booking</button>`;
  if (isPassenger && booking.refund_status === 'due') actions += `<button class="primary-btn" data-refund-received="${esc(booking.id)}">Refund received</button>`;
  const relevantName = ownDriver ? booking.passenger_name : booking.driver_name;
  const sub = ownDriver ? `Passenger · from ${booking.passenger_hometown || 'Vidarbha'}` : 'Driver · confirmed contact shown in person for this demo';
  const passengerTrust = ownDriver ? `<div class="booking-note">Passenger record · ${esc(trustSummary({ reliability: booking.passenger_reliability || {} }))}</div>` : '';
  const cancellation = booking.status === 'cancelled_passenger' ? `<div class="${booking.refund_inr ? 'success-box' : 'notice'}">${booking.cancelled_by_role === 'driver' ? (booking.refund_inr ? `Driver cancelled this ride. ${formatMoney(booking.refund_inr)} full refund ${booking.refund_status === 'confirmed' ? 'marked received' : 'recorded as due'}.` : 'Driver cancelled before an advance was recorded.') : booking.refund_inr ? `Policy outcome: ${formatMoney(booking.refund_inr)} full refund ${booking.refund_status === 'confirmed' ? 'marked received' : 'due'} under this cancellation timing.` : booking.refund_outcome === 'pending_refill' ? 'Policy outcome: refund depends on whether the seat is refilled. If it is not refilled, the outcome settles at departure.' : 'Policy outcome: no refund due for this cancellation timing.'}</div>` : '';
  const expiredRequest = booking.request_expired ? `<div class="notice"><strong>Request window closed.</strong> This request expired ${booking.request_expires_at ? `at ${esc(localDateTime(booking.request_expires_at))}` : 'before driver acceptance'} and can no longer be accepted.</div>` : '';
  const refundInfo = booking.refund_status ? refundStatusCard(booking) : '';
  const extra = booking.status === 'confirmed' || booking.status === 'accepted' ? `<div class="policy-box"><h3>Cancellation policy · agreed for this booking</h3><div class="cutoff-row"><span>Free cancellation until</span><strong>${exactCutoff(booking.departure_at, 48)}</strong></div><div class="cutoff-row"><span>Half the advance at stake after</span><strong>${exactCutoff(booking.departure_at, 48)}</strong></div><div class="cutoff-row"><span>Full advance at stake after</span><strong>${exactCutoff(booking.departure_at, 12)}</strong></div><div class="cutoff-row"><span>Advance recorded</span><strong>${advanceLabel(booking.advance_inr)}</strong></div></div>` : '';
  const moneyMessage = booking.status === 'accepted' && isPassenger ? `<div class="notice">Demo payment only. A production build would open the driver’s UPI app; this demo does not transfer or verify money.</div>` : '';
  const safetyActions = (ownDriver || isPassenger) ? `<div class="safety-actions"><button class="tiny-btn" data-report-booking="${esc(booking.id)}">Report ${esc(peerName.split(' ')[0])}</button><button class="tiny-btn" data-block-booking="${esc(booking.id)}">Block ${esc(peerName.split(' ')[0])}</button></div>` : '';
  const reconfirmation = reconfirmationCard(booking, ownDriver, isPassenger);
  const noShow = noShowCard(booking, ownDriver, isPassenger);
  const tripCheck = tripCheckCard(booking);
  return `<article class="booking-card"><div class="booking-top"><div><div class="booking-route">${esc(booking.origin)} <span class="muted">→</span> ${esc(booking.destination)}</div><div class="booking-date">${esc(localDateTime(booking.departure_at))} · ${esc(booking.car)}</div></div><span class="status-chip ${booking.request_expired ? 'status-request-expired' : `status-${esc(booking.status)}`}" >${esc(statusTitle(booking))}</span></div>
    <div class="booking-details"><span>${ownDriver ? 'Passenger' : 'Driver'}: <strong>${esc(relevantName)}</strong></span><span>Fare: <strong>${formatMoney(booking.fare_inr)}</strong></span><span>Advance: <strong>${formatMoney(booking.advance_inr)}</strong></span><span>Est. arrival: <strong>${esc(localDateTime(booking.expected_arrival_at))}</strong></span></div>
    ${booking.note ? `<div class="booking-note">“${esc(booking.note)}”</div>` : ''}${passengerTrust}${extra}${moneyMessage}${expiredRequest}${cancellation}${refundInfo}${reconfirmation}${noShow}${tripCheck}${actions ? `<div class="booking-actions">${actions}</div>` : ''}${safetyActions}</article>`;
}

function noShowCard(booking, ownDriver, isPassenger) {
  if (booking.status !== 'confirmed') return '';
  const record = booking.no_show_case;
  if (record?.status === 'confirmed') return `<div class="notice"><strong>No-show confirmed.</strong> It is now included on the passenger’s reliability record.</div>`;
  if (record?.status === 'disputed') return `<div class="notice"><strong>No-show disputed.</strong> This case remains off the reliability record pending manual review.</div>`;
  if (record?.status === 'pending') {
    return `<div class="notice"><strong>Passenger no-show reported.</strong> The passenger may dispute this by ${esc(localDateTime(record.dispute_until))}. It will only affect their record if no dispute is filed within 24 hours.${isPassenger ? `<div class="booking-actions"><button class="outline-btn" data-dispute-no-show="${esc(booking.id)}">Dispute this report</button></div>` : ''}</div>`;
  }
  const eligibleAt = new Date(new Date(booking.departure_at).getTime() + 30 * 60000);
  if (ownDriver && Date.now() >= eligibleAt.getTime()) return `<div class="no-show-action"><span>Passenger did not arrive? A report opens a 24-hour dispute window.</span><button class="outline-btn danger-btn" data-no-show="${esc(booking.id)}">Report no-show</button></div>`;
  if (isPassenger) return `<div class="arrival-note">No-show reports can be made 30 minutes after departure. Any report includes a 24-hour dispute window.</div>`;
  return '';
}

function reconfirmationCard(booking, ownDriver, isPassenger) {
  if (booking.status !== 'confirmed') return '';
  const hoursLeft = (new Date(booking.departure_at).getTime() - Date.now()) / 3600000;
  if (hoursLeft < 0) return '';
  const responses = booking.reconfirmations || [];
  const responseFor = (stage, id) => responses.find(row => row.stage_hours === stage && row.user_id === id);
  const passenger48 = responseFor(48, booking.passenger_id);
  const atRisk = hoursLeft <= 42 && (!passenger48 || !passenger48.coming);
  const visibleStages = isPassenger ? [72, 48, 12] : [48, 12];
  const rows = visibleStages.map(stage => {
    const open = hoursLeft <= stage;
    const mine = responseFor(stage, state.userId);
    const passenger = responseFor(stage, booking.passenger_id);
    const driver = responseFor(stage, booking.driver_id);
    const other = ownDriver ? passenger : driver;
    const label = stage === 72 ? '72-hour check-in' : stage === 48 ? '48-hour reconfirmation' : '12-hour final check';
    const instruction = stage === 12 ? `Pickup details: ${booking.car}${booking.note ? ` · ${booking.note}` : ''}` : 'Please confirm your plans for this ride.';
    if (!open) return `<div class="reconfirm-row"><span><strong>${label}</strong><small>Opens ${stage} hours before departure</small></span><span class="reconfirm-state">Upcoming</span></div>`;
    if (mine) return `<div class="reconfirm-row"><span><strong>${label}</strong><small>You ${mine.coming ? 'confirmed you are coming' : 'said your plans changed'}${other ? ` · ${esc(other.user_name)} ${other.coming ? 'confirmed' : 'reported a change'}` : ''}</small></span><span class="reconfirm-state">${mine.coming ? 'Confirmed' : 'Follow up'}</span></div>`;
    if (!isPassenger && stage === 72) return '';
    if (other && !ownDriver) return `<div class="reconfirm-row"><span><strong>${label}</strong><small>${esc(other.user_name)} ${other.coming ? 'confirmed' : 'reported a change'} · waiting for you</small></span><span class="reconfirm-state">Your reply needed</span><div class="reconfirm-actions"><button class="primary-btn" data-reconfirm="${esc(booking.id)}" data-stage="${stage}" data-coming="true">Still coming</button><button class="tiny-btn" data-reconfirm="${esc(booking.id)}" data-stage="${stage}" data-coming="false">Plans changed</button></div></div>`;
    const peerStatus = other ? ` · Passenger ${other.coming ? 'confirmed they are coming' : 'reported a plan change'}` : '';
    return `<div class="reconfirm-row"><span><strong>${label}</strong><small>${instruction}${ownDriver ? peerStatus : other ? ` · ${esc(other.user_name)} has replied` : ''}</small></span><span class="reconfirm-state">Check-in open</span><div class="reconfirm-actions"><button class="primary-btn" data-reconfirm="${esc(booking.id)}" data-stage="${stage}" data-coming="true">Still coming</button><button class="tiny-btn" data-reconfirm="${esc(booking.id)}" data-stage="${stage}" data-coming="false">Plans changed</button></div></div>`;
  }).filter(Boolean).join('');
  if (!rows && !atRisk) return '';
  const riskCopy = passenger48 ? 'Seat at risk · passenger reported a change' : 'Seat at risk · no 48-hour confirmation';
  return `<div class="reconfirm-card"><div class="reconfirm-heading"><strong>Before departure</strong>${atRisk && ownDriver ? `<span class="risk-pill">${riskCopy}</span>` : ''}</div>${rows}${atRisk && isPassenger && !passenger48 ? '<div class="notice">Your 48-hour check-in is overdue. Please confirm or contact the driver. No booking is cancelled automatically.</div>' : ''}<small class="reconfirm-footnote">In-app check-ins only. No scheduled messages are sent in this demo. “Plans changed” records an answer; it does not cancel the booking.</small></div>`;
}

function refundStatusCard(booking) {
  if (booking.refund_status === 'confirmed') return `<div class="success-box">You marked the ${formatMoney(booking.refund_inr)} refund as received. This confirmation is self-reported in the demo.</div>`;
  if (booking.refund_status !== 'due') return '';
  const dueAt = booking.refund_due_at ? new Date(booking.refund_due_at) : null;
  const overdue = dueAt && Date.now() >= dueAt.getTime() + 24 * 3600000;
  if (overdue) return `<div class="notice"><strong>Open refund dispute.</strong> The ${formatMoney(booking.refund_inr)} refund is still unconfirmed more than 24 hours after its due time.</div>`;
  return `<div class="success-box">${formatMoney(booking.refund_inr)} refund marked due${dueAt ? ` by ${esc(localDateTime(dueAt))}` : ''}. No money moves in this demo.</div>`;
}

function tripCheckCard(booking) {
  if (booking.status !== 'confirmed') return '';
  if (booking.no_show_case) return '';
  const arrivalPassed = new Date(booking.expected_arrival_at).getTime() <= Date.now();
  const responses = booking.trip_confirmations || [];
  const mine = responses.find(response => response.user_id === state.userId);
  if (!arrivalPassed) return `<div class="arrival-note">Trip check opens after estimated arrival · ${esc(localDateTime(booking.expected_arrival_at))}</div>`;
  if (responses.length >= 2) {
    if (responses.every(response => Boolean(response.happened))) return `<div class="success-box trip-result"><strong>Trip confirmed by both travelers.</strong> It now counts on both reliability records.</div>`;
    if (responses.some(response => Boolean(response.happened)) && responses.some(response => !response.happened)) return `<div class="notice trip-result"><strong>Answers differ.</strong> This trip is flagged for review and stays off both public records.</div>`;
    return `<div class="arrival-note trip-result">Both travelers said the trip did not happen. It is not added to either record.</div>`;
  }
  if (mine) return `<div class="arrival-note trip-result">You answered <strong>${mine.happened ? 'Yes' : 'No'}</strong>. Waiting for the other traveler.</div>`;
  const other = responses[0];
  return `<div class="trip-check"><div><strong>Did this trip happen?</strong><span>${other ? `${esc(other.user_name)} has answered.` : 'Your answer helps keep member records accurate.'}</span></div><div class="trip-buttons"><button class="outline-btn" data-trip-answer="false" data-trip-booking="${esc(booking.id)}">No</button><button class="primary-btn" data-trip-answer="true" data-trip-booking="${esc(booking.id)}">Yes, we travelled</button></div></div>`;
}
function waitlistCard(entry, mine) {
  const status = entry.status === 'offered' ? 'Seat offered' : entry.status === 'accepted' ? 'Offer accepted' : entry.status === 'waiting' ? 'Waiting' : entry.status;
  const cutoff = entry.offer_expires_at ? new Intl.DateTimeFormat('en-IN', { timeZone:'Asia/Kolkata', weekday:'short', day:'numeric', month:'short', hour:'numeric', minute:'2-digit', hour12:true }).format(new Date(entry.offer_expires_at)) + ' IST' : '';
  return `<div class="booking-card"><div class="booking-top"><div><div class="booking-route">${esc(entry.passenger_name)}${mine ? ' · You' : ''}</div><div class="booking-date">${mine ? `Queue status${cutoff ? ` · offer expires ${cutoff}` : ''}` : `From ${esc(entry.passenger_hometown)}`}</div></div><span class="status-chip status-${entry.status === 'offered' ? 'accepted' : 'requested'}">${esc(status)}</span></div>${mine && entry.status === 'offered' ? `<div class="booking-actions"><button class="primary-btn" data-accept-waitlist="${esc(entry.id)}">Accept seat offer</button></div>` : ''}${entry.refills_booking_id ? `<div class="success-box">This waitlist seat refilled a cancelled booking. The original passenger’s full refund is due in the demo record.</div>` : ''}</div>`;
}
async function openReportModal(bookingId) {
  const { booking } = await api(`/api/bookings/${encodeURIComponent(bookingId)}?userId=${encodeURIComponent(state.userId)}`);
  const peerName = booking.driver_id === state.userId ? booking.passenger_name : booking.driver_name;
  const modal = document.createElement('div');
  modal.className = 'modal-backdrop';
  modal.id = 'report-modal';
  modal.innerHTML = `<section class="modal" role="dialog" aria-modal="true" aria-labelledby="report-title"><div class="modal-top"><div><p class="eyebrow">SAFETY & COMMUNITY</p><h2 id="report-title">Report ${esc(peerName)}</h2></div><button class="close-modal" data-close-report aria-label="Close report form">×</button></div><p>Tell us what happened on this booking. Your report stays private and is saved as open. This demo does not notify a moderator.</p><form id="report-form"><input type="hidden" name="bookingId" value="${esc(bookingId)}"><div class="form-field"><label for="report-reason">Reason</label><select id="report-reason" name="reason" required><option value="">Choose a reason</option><option value="unsafe_driving">Unsafe driving</option><option value="harassment">Harassment or threatening behavior</option><option value="misleading_ride">Misleading ride details</option><option value="payment_dispute">Payment or refund issue</option><option value="no_show">No-show</option><option value="other">Something else</option></select></div><div class="form-field" style="margin-top:13px"><label for="report-details">Details · optional</label><textarea id="report-details" name="details" maxlength="1000" placeholder="Add context for a future manual review."></textarea></div><div class="modal-actions"><button class="outline-btn" type="button" data-close-report>Cancel</button><button class="primary-btn" type="submit">Submit report</button></div></form></section>`;
  document.body.append(modal);
  modal.querySelector('select').focus();
}
function openRequestModal(rideId) {
  const ride = state.rides.find(item => item.id === rideId);
  if (!ride) return toast('This ride is no longer available. Refresh and try again.');
  const modal = document.createElement('div');
  modal.className = 'modal-backdrop';
  modal.id = 'request-modal';
  modal.innerHTML = `<section class="modal" role="dialog" aria-modal="true" aria-labelledby="request-title"><div class="modal-top"><div><p class="eyebrow">REQUEST A SEAT</p><h2 id="request-title">${esc(ride.origin)} to ${esc(ride.destination)}</h2></div><button class="close-modal" type="button" data-close-request aria-label="Close request form">×</button></div><p>${esc(localDateTime(ride.departure_at))} · ${formatMoney(ride.fare_inr)} per seat · ${formatMoney(ride.advance_inr)} advance. Add a short note for the driver if you’d like.</p><form id="request-form"><input type="hidden" name="rideId" value="${esc(ride.id)}"><div class="form-field"><label for="request-note">Note · optional</label><textarea id="request-note" name="note" maxlength="280" placeholder="Pickup preferences, luggage, or a quick introduction."></textarea></div><div class="modal-actions"><button class="outline-btn" type="button" data-close-request>Cancel</button><button class="primary-btn" type="submit">Send seat request</button></div></form></section>`;
  document.body.append(modal);
  modal.querySelector('textarea').focus();
}
async function renderBookings() {
  app.dataset.page = 'bookings';
  const [data, reportsData] = await Promise.all([
    api(`/api/bookings?userId=${encodeURIComponent(state.userId)}`),
    api(`/api/reports?userId=${encodeURIComponent(state.userId)}`),
  ]);
  const bookings = data.bookings;
  const reports = reportsData.reports;
  app.innerHTML = `${baseHero('YOUR TRIP DESK', 'A little clarity goes <em>a long way.</em>', 'Keep track of your requests, confirmed seats and the agreed rules in one place.')}
    <div class="section-heading"><h2>${isDriver() ? 'Passenger requests & bookings' : 'Your seat requests'}</h2><span class="count-pill">${bookings.length} booking${bookings.length === 1 ? '' : 's'}</span></div>
    <div class="stack">${bookings.length ? bookings.map(bookingCard).join('') : `<div class="empty-state"><strong>No bookings yet</strong>Find a ride and request a seat to get started.</div>`}</div>
    <div class="divider"></div><div class="section-heading"><h2>Reports you’ve sent</h2><span class="count-pill">${reports.length} report${reports.length === 1 ? '' : 's'}</span></div>
    <div class="stack">${reports.length ? reports.map(report => `<article class="report-card"><div><strong>${esc(report.reported_name)}</strong><span>${esc(report.origin)} → ${esc(report.destination)}</span></div><span class="status-chip status-requested">Open record</span></article>`).join('') : `<div class="booking-note">Reports are private to you and remain open in this demo.</div>`}</div>`;
}
async function renderRideDetail(rideId) {
  app.dataset.page = 'ride';
  const data = await api(`/api/rides/${encodeURIComponent(rideId)}?userId=${encodeURIComponent(state.userId)}`);
  const ride = data.ride;
  const mine = ride.driver_id === state.userId;
  const requestWindowOpen = new Date(ride.departure_at).getTime() - Date.now() > 12 * 3600000;
  const shareUrl = `${location.origin}/?ride=${encodeURIComponent(ride.id)}`;
  const bookings = data.bookings;
  const confirmedCount = bookings.filter(booking => booking.status === 'confirmed').length;
  app.innerHTML = `${baseHero('RIDE DETAILS', `${esc(ride.origin)} to <em>${esc(ride.destination)}.</em>`, 'See who has requested a seat and keep the plan clear from the first tap.')}
    <div class="detail-card"><div class="seat-lock-heading"><span class="lock-icon">⌑</span><div><div class="form-heading">${esc(ride.driver_name)}’s ride</div><div class="form-intro" style="margin:4px 0 0">${esc(localDateTime(ride.departure_at))} · ${esc(ride.car)}</div><div class="trust-line">Trust record · ${esc(trustSummary(ride))}</div></div><span class="count-pill" style="margin-left:auto">${ride.status === 'cancelled' ? 'Cancelled' : `${ride.seats_left} seat${ride.seats_left === 1 ? '' : 's'} left`}</span></div>
      <div class="rule-grid"><div class="rule-card"><span>Fare per seat</span><strong>${formatMoney(ride.fare_inr)}</strong></div><div class="rule-card"><span>Advance to driver</span><strong>${formatMoney(ride.advance_inr)}</strong></div><div class="rule-card"><span>Driver profile</span><strong>${esc(ride.driver_hometown)}</strong></div></div>
      <div class="arrival-note">Estimated arrival · <strong>${esc(localDateTime(ride.expected_arrival_at))}</strong>. Both travelers can confirm the trip after this time.</div>
      ${mine && ride.status !== 'cancelled' && confirmedCount > 0 && new Date(ride.expected_arrival_at).getTime() > Date.now() ? `<div class="demo-control"><span>Preview the post-trip check without waiting for the scheduled arrival.</span><button class="tiny-btn" data-simulate-arrival="${esc(ride.id)}">Simulate arrival now</button></div>` : ''}
      ${ride.notes ? `<p class="booking-note">${esc(ride.notes)}</p>` : ''}
      ${mine ? `<div class="share-box"><span class="share-url">${esc(shareUrl)}</span><div class="share-actions"><button class="tiny-btn" data-copy="${esc(shareUrl)}">Copy link</button><a class="tiny-btn" target="_blank" rel="noreferrer" href="https://wa.me/?text=${encodeURIComponent(`Seat Lock ride: ${ride.origin} → ${ride.destination}, ${shortDate(ride.departure_at)}. ${shareUrl}`)}">WhatsApp ↗</a></div></div>${ride.status !== 'cancelled' ? `<button class="outline-btn danger-btn" style="margin-top:12px" data-cancel-ride="${esc(ride.id)}">Cancel this ride</button>` : `<div class="notice">This ride has been cancelled.</div>`}` : `<div class="policy-box"><h3>Before you request</h3><div class="cutoff-row"><span>Free cancellation until</span><strong>${exactCutoff(ride.departure_at, 48)}</strong></div><div class="cutoff-row"><span>Half advance at stake after</span><strong>${exactCutoff(ride.departure_at, 48)}</strong></div><div class="cutoff-row"><span>Full advance at stake after</span><strong>${exactCutoff(ride.departure_at, 12)}</strong></div></div><div class="notice">No payment is due until the driver accepts your request. This demo uses simulated payment records.</div>${ride.status === 'cancelled' ? `<div class="notice">The driver cancelled this ride.</div>` : ride.seats_left > 0 ? requestWindowOpen ? `<button class="primary-btn" style="margin-top:14px" data-request="${esc(ride.id)}">Request a seat&nbsp; →</button>` : `<div class="notice">Seat requests close 12 hours before departure.</div>` : `<button class="primary-btn" style="margin-top:14px" data-waitlist="${esc(ride.id)}">Join waitlist</button>`}`}
      <div class="divider"></div><h3 class="subheading">${mine ? 'Passenger requests' : 'Your booking on this ride'}</h3><div class="stack">${bookings.filter(b => mine || b.passenger_id === state.userId).length ? bookings.filter(b => mine || b.passenger_id === state.userId).map(bookingCard).join('') : `<div class="empty-state"><strong>${mine ? 'No requests yet' : 'You haven’t requested this seat'}</strong>${mine ? 'Share this ride with your group to find passengers.' : 'Request a seat to get started.'}</div>`}</div>
      <div class="divider"></div><h3 class="subheading">${mine ? `Waitlist · ${data.waitlist.length}` : 'Your waitlist status'}</h3><div class="stack">${data.waitlist.filter(entry => mine || entry.passenger_id === state.userId).length ? data.waitlist.filter(entry => mine || entry.passenger_id === state.userId).map(entry => waitlistCard(entry, entry.passenger_id === state.userId)).join('') : `<div class="booking-note">${mine ? 'No one is waiting for a seat yet.' : 'You are not on this ride’s waitlist.'}</div>`}</div>
    </div>`;
}
async function render() {
  app.dataset.page = state.view;
  if (state.view === 'find') return renderFind();
  if (state.view === 'offer') return renderOffer();
  if (state.view === 'bookings') return renderBookings();
  if (state.view === 'ride') {
    try { await renderRideDetail(state.activeRideId); } catch (error) { toast(error.message); setView('find'); }
  }
}

document.addEventListener('click', async event => {
  const target = event.target.closest('button');
  if (!target) return;
  try {
    if (target.dataset.view) return setView(target.dataset.view);
    if (target.dataset.openRide) { state.activeRideId = target.dataset.openRide; state.view = 'ride'; return render(); }
    if (target.dataset.request) {
      return openRequestModal(target.dataset.request);
    }
    if (target.dataset.waitlist) {
      await post(`/api/rides/${encodeURIComponent(target.dataset.waitlist)}/waitlist`, { userId: state.userId });
      toast('You joined the waitlist. We’ll show any seat offer here.');
      state.activeRideId = target.dataset.waitlist; state.view = 'ride'; return renderRideDetail(state.activeRideId);
    }
    if (target.dataset.acceptWaitlist) {
      await post(`/api/waitlist/${encodeURIComponent(target.dataset.acceptWaitlist)}/accept`, { userId: state.userId });
      toast('Seat offer accepted. Continue with the advance step.');
      state.view = 'bookings'; state.activeRideId = null; return renderBookings();
    }
    if (target.dataset.cancelRide) {
      const answer = window.confirm('Cancel this ride for everyone? Any recorded advances will be marked as full refunds due.');
      if (!answer) return;
      await post(`/api/rides/${encodeURIComponent(target.dataset.cancelRide)}/cancel`, { userId: state.userId });
      await refresh();
      state.view = 'ride'; state.activeRideId = target.dataset.cancelRide;
      document.querySelectorAll('.nav-link').forEach(button => button.classList.toggle('active', button.dataset.view === 'find'));
      toast('Ride cancelled. Full refund records created for passengers who recorded an advance.');
      return renderRideDetail(state.activeRideId);
    }
    if (target.dataset.simulateArrival) {
      await post(`/api/rides/${encodeURIComponent(target.dataset.simulateArrival)}/simulate-arrival`, { userId: state.userId });
      toast('Demo arrival time updated. Travelers can now answer the trip check.');
      return renderRideDetail(target.dataset.simulateArrival);
    }
    if (target.dataset.tripBooking) {
      const happened = target.dataset.tripAnswer === 'true';
      await post(`/api/bookings/${encodeURIComponent(target.dataset.tripBooking)}/confirm-trip`, { userId: state.userId, happened });
      toast(happened ? 'Trip answer recorded.' : 'Your answer was recorded.');
      return render();
    }
    if (target.dataset.reconfirm) {
      const coming = target.dataset.coming === 'true';
      await post(`/api/bookings/${encodeURIComponent(target.dataset.reconfirm)}/reconfirm`, {
        userId: state.userId, stageHours: Number(target.dataset.stage), coming
      });
      toast(coming ? 'Your check-in is recorded.' : 'Plan change recorded. Please contact the other traveler directly.');
      return render();
    }
    if (target.dataset.noShow) {
      await post(`/api/bookings/${encodeURIComponent(target.dataset.noShow)}/no-show`, { userId: state.userId });
      toast('No-show report saved. The passenger has 24 hours to dispute it.');
      return render();
    }
    if (target.dataset.disputeNoShow) {
      await post(`/api/bookings/${encodeURIComponent(target.dataset.disputeNoShow)}/dispute-no-show`, { userId: state.userId });
      toast('Dispute recorded. This case stays off the public record pending manual review.');
      return render();
    }
    if (target.dataset.refundReceived) {
      await post(`/api/bookings/${encodeURIComponent(target.dataset.refundReceived)}/refund-received`, { userId: state.userId });
      toast('Refund marked as received in the demo.');
      return render();
    }
    if (target.dataset.reportBooking) {
      await openReportModal(target.dataset.reportBooking);
      return;
    }
    if (target.dataset.closeReport || target.id === 'report-modal') {
      document.querySelector('#report-modal')?.remove();
      return;
    }
    if (target.dataset.closeRequest || target.id === 'request-modal') {
      document.querySelector('#request-modal')?.remove();
      return;
    }
    if (target.dataset.blockBooking) {
      const { booking } = await api(`/api/bookings/${encodeURIComponent(target.dataset.blockBooking)}?userId=${encodeURIComponent(state.userId)}`);
      const peerName = booking.driver_id === state.userId ? booking.passenger_name : booking.driver_name;
      if (!window.confirm(`Block ${peerName}? You’ll both stop seeing or requesting each other’s rides.`)) return;
      await post('/api/blocks', { userId: state.userId, bookingId: booking.id });
      toast(`${peerName} is blocked. Their rides are hidden from this profile.`);
      const leftRideDetail = state.view === 'ride';
      if (leftRideDetail) state.view = 'find';
      await refresh();
      if (leftRideDetail) document.querySelectorAll('.nav-link').forEach(button => button.classList.toggle('active', button.dataset.view === 'find'));
      return;
    }
    if (target.dataset.accept) await post(`/api/bookings/${encodeURIComponent(target.dataset.accept)}/accept`, { userId: state.userId });
    if (target.dataset.claimAdvance) await post(`/api/bookings/${encodeURIComponent(target.dataset.claimAdvance)}/claim-advance`, { userId: state.userId });
    if (target.dataset.confirmAdvance) await post(`/api/bookings/${encodeURIComponent(target.dataset.confirmAdvance)}/confirm-advance`, { userId: state.userId });
    if (target.dataset.cancel) {
      const answer = window.confirm('Cancel this confirmed booking? The policy will calculate the refund due based on the current time.');
      if (!answer) return;
      const result = await post(`/api/bookings/${encodeURIComponent(target.dataset.cancel)}/cancel`, { userId: state.userId });
      toast(result.refund_inr ? `${formatMoney(result.refund_inr)} refund marked due in the demo.` : 'Cancellation recorded under the policy.');
    }
    if (target.dataset.copy) {
      await navigator.clipboard.writeText(target.dataset.copy);
      return toast('Ride link copied.');
    }
    if (target.dataset.accept || target.dataset.claimAdvance || target.dataset.confirmAdvance) toast('Booking updated.');
    if (target.dataset.accept || target.dataset.claimAdvance || target.dataset.confirmAdvance || target.dataset.cancel) return render();
  } catch (error) { toast(error.message); }
});

document.addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  try {
    if (form.id === 'report-form') {
      const data = new FormData(form);
      const result = await post('/api/reports', {
        userId: state.userId, bookingId: data.get('bookingId'), reason: data.get('reason'), details: data.get('details')
      });
      document.querySelector('#report-modal')?.remove();
      toast('Report saved as open. This demo does not notify a moderator.');
      if (state.view === 'bookings') await renderBookings();
      return result;
    }
    if (form.id === 'request-form') {
      const data = new FormData(form);
      const result = await post(`/api/rides/${encodeURIComponent(data.get('rideId'))}/requests`, {
        userId: state.userId, note: data.get('note')
      });
      document.querySelector('#request-modal')?.remove();
      state.lastBookingId = result.booking.id;
      state.view = 'bookings'; state.activeRideId = null;
      document.querySelectorAll('.nav-link').forEach(button => button.classList.toggle('active', button.dataset.view === 'bookings'));
      toast('Seat request sent to the driver.');
      return renderBookings();
    }
    if (form.id === 'search-form') {
      const data = new FormData(form);
      state.selectedOrigin = data.get('origin');
      state.selectedDestination = data.get('destination');
      state.selectedDate = data.get('date');
      return renderFind();
    }
    if (form.id === 'ride-form') {
      const data = new FormData(form);
      const result = await post('/api/rides', {
        userId: state.userId, origin: data.get('origin'), destination: data.get('destination'), departure_at: data.get('departure_at'),
        duration_hours: data.get('duration_hours'), seats_offered: data.get('seats_offered'), fare_inr: data.get('fare_inr'), advance_inr: data.get('advance_inr'), car: data.get('car'),
        women_only: data.get('women_only') === 'on', notes: data.get('notes')
      });
      state.rides.unshift(result.ride);
      state.selectedOrigin = result.ride.origin;
      state.view = 'ride'; state.activeRideId = result.ride.id;
      document.querySelectorAll('.nav-link').forEach(button => button.classList.toggle('active', button.dataset.view === 'find'));
      toast('Ride posted. Share the link with your group.');
      return renderRideDetail(result.ride.id);
    }
  } catch (error) { toast(error.message); }
});

userSwitch.addEventListener('change', () => {
  state.userId = userSwitch.value;
  refresh().catch(error => toast(error.message));
});

document.addEventListener('input', event => {
  if (event.target.name === 'fare') {
    const advance = document.querySelector('#advance');
    if (advance) advance.value = suggestedAdvance(event.target.value);
  }
});

(async () => {
  try {
    await refresh();
    const rideId = new URLSearchParams(location.search).get('ride');
    if (rideId && state.rides.some(ride => ride.id === rideId)) {
      state.activeRideId = rideId; state.view = 'ride'; await renderRideDetail(rideId);
    }
  } catch (error) {
    app.innerHTML = `<div class="empty-state"><strong>The app could not start</strong>${esc(error.message)}</div>`;
  }
})();
