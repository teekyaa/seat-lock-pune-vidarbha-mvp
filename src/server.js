const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const domain = require('./domain');
require('./store');

const root = path.join(__dirname, '..', 'public');
const port = Number(process.env.PORT || 3001);
const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml' };

function sendJson(res, status, payload) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(payload));
}

async function readJson(req) {
  let body = '';
  for await (const part of req) {
    body += part;
    if (body.length > 64_000) throw new Error('Request is too large.');
  }
  return body ? JSON.parse(body) : {};
}

async function handleApi(req, res, url) {
  try {
    if (req.method === 'GET' && url.pathname === '/api/bootstrap') {
      const viewerId = url.searchParams.get('userId');
      return sendJson(res, 200, { users: [domain.user('driver-aditi'), domain.user('passenger-rahul'), domain.user('passenger-neha')], rides: domain.listRides(viewerId) });
    }
    if (req.method === 'GET' && url.pathname.startsWith('/api/rides/')) {
      const ride = domain.getRide(decodeURIComponent(url.pathname.split('/').pop()));
      if (!ride) return sendJson(res, 404, { error: 'Ride not found.' });
      if (!domain.canViewRide(ride.id, url.searchParams.get('userId'))) return sendJson(res, 404, { error: 'Ride not found.' });
      return sendJson(res, 200, { ride, bookings: domain.bookingsForRide(ride.id), waitlist: domain.waitlistForRide(ride.id) });
    }
    if (req.method === 'GET' && url.pathname === '/api/bookings') {
      return sendJson(res, 200, { bookings: domain.bookingsForUser(url.searchParams.get('userId')) });
    }
    const getBookingMatch = url.pathname.match(/^\/api\/bookings\/([^/]+)$/);
    if (req.method === 'GET' && getBookingMatch) {
      const booking = domain.getBooking(getBookingMatch[1]);
      const viewerId = url.searchParams.get('userId');
      if (!booking || ![booking.driver_id, booking.passenger_id].includes(viewerId)) return sendJson(res, 404, { error: 'Booking not found.' });
      return sendJson(res, 200, { booking });
    }
    if (req.method === 'GET' && url.pathname === '/api/reports') {
      return sendJson(res, 200, { reports: domain.reportsForUser(url.searchParams.get('userId')) });
    }
    const body = await readJson(req);
    if (req.method === 'POST' && url.pathname === '/api/rides') return sendJson(res, 201, { ride: domain.createRide(body.userId, body) });
    const simulateArrivalMatch = url.pathname.match(/^\/api\/rides\/([^/]+)\/simulate-arrival$/);
    if (req.method === 'POST' && simulateArrivalMatch) return sendJson(res, 200, { ride: domain.simulateArrival(simulateArrivalMatch[1], body.userId) });
    if (req.method === 'POST' && url.pathname === '/api/reports') return sendJson(res, 201, { report: domain.reportUser(body.bookingId, body.userId, body.reason, body.details) });
    if (req.method === 'POST' && url.pathname === '/api/blocks') return sendJson(res, 201, domain.blockBookingParticipant(body.bookingId, body.userId));
    const cancelRideMatch = url.pathname.match(/^\/api\/rides\/([^/]+)\/cancel$/);
    if (req.method === 'POST' && cancelRideMatch) return sendJson(res, 200, domain.cancelRide(cancelRideMatch[1], body.userId));
    if (req.method === 'POST' && url.pathname.endsWith('/requests')) return sendJson(res, 201, { booking: domain.requestSeat(url.pathname.split('/')[3], body.userId, body.note) });
    if (req.method === 'POST' && url.pathname.endsWith('/waitlist')) return sendJson(res, 201, { entry: domain.joinWaitlist(url.pathname.split('/')[3], body.userId) });
    const waitlistMatch = url.pathname.match(/^\/api\/waitlist\/([^/]+)\/accept$/);
    if (req.method === 'POST' && waitlistMatch) return sendJson(res, 200, { booking: domain.acceptWaitlistOffer(waitlistMatch[1], body.userId) });
    const reconfirmMatch = url.pathname.match(/^\/api\/bookings\/([^/]+)\/reconfirm$/);
    if (req.method === 'POST' && reconfirmMatch) return sendJson(res, 200, { booking: domain.reconfirmBooking(reconfirmMatch[1], body.userId, body.stageHours, body.coming) });
    const noShowMatch = url.pathname.match(/^\/api\/bookings\/([^/]+)\/(no-show|dispute-no-show)$/);
    if (req.method === 'POST' && noShowMatch) {
      const [, bookingId, action] = noShowMatch;
      const booking = action === 'no-show' ? domain.markNoShow(bookingId, body.userId) : domain.disputeNoShow(bookingId, body.userId);
      return sendJson(res, 200, { booking });
    }
    const match = url.pathname.match(/^\/api\/bookings\/([^/]+)\/(accept|claim-advance|confirm-advance|cancel|confirm-trip|refund-received)$/);
    if (req.method === 'POST' && match) {
      const [, bookingId, action] = match;
      const result = action === 'accept' ? domain.acceptBooking(bookingId, body.userId)
        : action === 'claim-advance' ? domain.claimAdvance(bookingId, body.userId)
          : action === 'confirm-advance' ? domain.confirmAdvance(bookingId, body.userId)
              : action === 'confirm-trip' ? domain.confirmTrip(bookingId, body.userId, body.happened)
                : action === 'refund-received' ? domain.confirmRefundReceived(bookingId, body.userId)
                  : domain.cancelBooking(bookingId, body.userId);
      return sendJson(res, 200, action === 'cancel' ? result : { booking: result });
    }
    return sendJson(res, 404, { error: 'API route not found.' });
  } catch (error) {
    const message = error instanceof SyntaxError ? 'Invalid request body.' : error.message;
    return sendJson(res, 400, { error: message || 'Request could not be completed.' });
  }
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  if (url.pathname.startsWith('/api/')) return void handleApi(req, res, url);
  const requested = url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname.slice(1));
  const file = path.resolve(root, requested);
  if (!file.startsWith(`${root}${path.sep}`) && file !== path.join(root, 'index.html')) {
    res.writeHead(403); return res.end('Forbidden');
  }
  fs.readFile(file, (error, content) => {
    if (error) { res.writeHead(404); return res.end('Not found'); }
    res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'X-Content-Type-Options': 'nosniff' });
    res.end(content);
  });
});

server.listen(port, '127.0.0.1', () => console.log(`Seat Lock demo running at http://localhost:${port}`));
