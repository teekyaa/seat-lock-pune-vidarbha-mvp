from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.errors import DomainError, Forbidden
from apps.core.models import CityPair, PolicyVersion
from apps.rides import services as rides
from apps.rides.models import Ride
from apps.trust.models import Report

from . import services
from .models import Booking, WaitlistEntry
from .presenters import _dt, booking_json, ride_json


def _int(data, name, default=None):
    value = data.get(name, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise DomainError(f"Enter a whole number for {name.replace('_', ' ')}.")


def _datetime(value):
    dt = parse_datetime(value or "")
    if dt is None or timezone.is_naive(dt):
        raise DomainError("Send the departure time with a timezone, for example 2026-11-06T21:00:00+05:30.")
    return dt


def _viewer(request):
    return request.user if request.user and request.user.is_authenticated else None


class CityPairsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        pairs = CityPair.objects.filter(active=True)
        return Response([
            {"id": p.pk, "origin": p.origin, "destination": p.destination, "distance_km": p.distance_km,
             "tolls_inr": p.tolls_inr, "typical_duration_hours": p.typical_duration_hours}
            for p in pairs
        ])


class FareQuoteView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        pair = get_object_or_404(CityPair, pk=_int(request.query_params, "city_pair"), active=True)
        seats = _int(request.query_params, "seats", 3)
        if not 1 <= seats <= 7:
            raise DomainError("Seats must be between 1 and 7.")
        return Response(rides.fare_quote(pair, seats))


class PolicyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        p = PolicyVersion.current()
        return Response({
            "label": p.label, "summary": p.summary, "advance_percent": p.advance_percent,
            "advance_min_inr": p.advance_min_inr, "advance_max_inr": p.advance_max_inr, "hold_hours": p.hold_hours,
            "full_refund_before_hours": p.full_refund_before_hours,
            "full_penalty_under_hours": p.full_penalty_under_hours, "refund_due_hours": p.refund_due_hours,
            "fare_cap_percent": p.fare_cap_percent,
        })


class RideListView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else super().get_permissions()

    def get(self, request):
        q = request.query_params
        date = parse_date(q.get("date", "")) if q.get("date") else None
        qs = rides.search(q.get("origin"), q.get("destination"), date, viewer=_viewer(request))[:50]
        return Response([ride_json(r, _viewer(request)) for r in qs])

    def post(self, request):
        d = request.data
        pair = get_object_or_404(CityPair, pk=_int(d, "city_pair"))
        vehicle = request.user.vehicles.filter(pk=_int(d, "vehicle")).first()
        if not vehicle:
            raise DomainError("Choose one of your saved cars.")
        ride = rides.create_ride(
            request.user, city_pair=pair, vehicle=vehicle, departure_at=_datetime(d.get("departure_at")),
            seats_offered=_int(d, "seats_offered"), fare_inr=_int(d, "fare_inr"),
            pickup_point=str(d.get("pickup_point", "")), dropoff_point=str(d.get("dropoff_point", "")),
            pickup_details=str(d.get("pickup_details", "")), notes=str(d.get("notes", ""))[:500],
            women_only=bool(d.get("women_only")), duration_hours=d.get("duration_hours") and _int(d, "duration_hours"),
            policy_ack=bool(d.get("policy_ack")),
        )
        return Response(ride_json(ride, request.user, detail=True), status=status.HTTP_201_CREATED)


class MyRidesView(APIView):
    def get(self, request):
        qs = rides.with_seat_counts(Ride.objects.filter(driver=request.user)).select_related(
            "driver", "vehicle", "city_pair").order_by("-departure_at")[:50]
        return Response([ride_json(r, request.user) for r in qs])


class RideDetailView(APIView):
    def get_permissions(self):
        return [AllowAny()] if self.request.method == "GET" else super().get_permissions()

    def get(self, request, code):
        ride = get_object_or_404(Ride.objects.select_related("driver", "vehicle", "city_pair", "policy_version"),
                                 code=code.upper())
        return Response(ride_json(ride, _viewer(request), detail=True))

    def patch(self, request, code):
        ride = get_object_or_404(Ride, code=code.upper())
        if ride.driver_id != request.user.pk:
            raise Forbidden("Only the driver can edit this ride.")
        if "departure_at" in request.data:
            ride = services.reschedule(ride, request.user, _datetime(request.data["departure_at"]))
        for field in ("notes", "pickup_details"):
            if field in request.data:
                setattr(ride, field, str(request.data[field])[:500])
        ride.save()
        return Response(ride_json(ride, request.user, detail=True))


class RideActionView(APIView):
    def post(self, request, code, action):
        ride = get_object_or_404(Ride, code=code.upper())
        if action == "request":
            b = services.request_seat(ride, request.user, note=str(request.data.get("note", "")),
                                      policy_ack=bool(request.data.get("policy_ack")))
            return Response(booking_json(b, request.user), status=status.HTTP_201_CREATED)
        if action == "waitlist":
            entry = services.join_waitlist(ride, request.user)
            return Response({"id": entry.pk, "status": entry.status}, status=status.HTTP_201_CREATED)
        if action == "cancel":
            ride = services.cancel_ride(ride, request.user)
            return Response(ride_json(ride, request.user, detail=True))
        return Response(status=status.HTTP_404_NOT_FOUND)


class RideBookingsView(APIView):
    def get(self, request, code):
        ride = get_object_or_404(Ride, code=code.upper())
        if ride.driver_id != request.user.pk:
            raise Forbidden("Only the driver can see this list.")
        bookings = ride.bookings.select_related("passenger", "ride", "policy_version").order_by("created_at")
        waitlist = ride.waitlist.select_related("passenger").exclude(status=WaitlistEntry.Status.WITHDRAWN)
        return Response({
            "bookings": [booking_json(b, request.user) for b in bookings],
            "waitlist": [{"id": w.pk, "passenger": w.passenger.name, "status": w.status,
                          "offer_expires_at": _dt(w.offer_expires_at)} for w in waitlist],
        })


class MyBookingsView(APIView):
    def get(self, request):
        qs = Booking.objects.filter(Q(passenger=request.user) | Q(ride__driver=request.user)).select_related(
            "ride", "ride__driver", "ride__city_pair", "ride__vehicle", "passenger", "policy_version"
        ).order_by("-ride__departure_at")[:100]
        return Response([booking_json(b, request.user) for b in qs])


def _booking_for(request, code):
    b = get_object_or_404(
        Booking.objects.select_related("ride", "ride__driver", "ride__city_pair", "passenger", "policy_version"),
        code=code.upper(),
    )
    if request.user.pk not in (b.passenger_id, b.ride.driver_id):
        raise Forbidden("This booking isn't yours.")
    return b


class BookingDetailView(APIView):
    def get(self, request, code):
        return Response(booking_json(_booking_for(request, code), request.user))


class BookingActionView(APIView):
    def post(self, request, code, action):
        b = _booking_for(request, code)
        u, d = request.user, request.data
        if action == "accept":
            services.accept(b, u)
        elif action == "decline":
            services.decline(b, u)
        elif action == "claim-advance":
            services.claim_advance(b, u, utr=str(d.get("utr", "")))
        elif action == "confirm-advance":
            services.confirm_advance(b, u)
        elif action == "cancel":
            services.cancel_by_passenger(b, u)
        elif action == "reconfirm":
            services.reconfirm(b, u, _int(d, "stage_hours"), bool(d.get("coming")))
        elif action == "trip-confirmation":
            services.confirm_trip(b, u, bool(d.get("happened")))
        elif action == "no-show":
            services.mark_no_show(b, u)
        elif action == "dispute-no-show":
            services.dispute_no_show(b, u, str(d.get("statement", "")))
        elif action == "refund-received":
            services.confirm_refund_received(b, u)
        elif action == "report":
            reason = d.get("reason")
            if reason not in Report.Reason.values:
                raise DomainError("Choose a reason for the report.")
            services.report_participant(b, u, reason, str(d.get("details", "")))
            return Response({"detail": "Thanks. Our team reviews every report within 24 hours."},
                            status=status.HTTP_201_CREATED)
        elif action == "block":
            blocked = services.block_participant(b, u)
            return Response({"detail": f"You won't see each other's rides again, {blocked.name} included."})
        else:
            return Response(status=status.HTTP_404_NOT_FOUND)
        b.refresh_from_db()
        return Response(booking_json(b, u))


class MyWaitlistView(APIView):
    def get(self, request):
        entries = request.user.waitlist_entries.select_related("ride", "ride__city_pair", "ride__driver",
                                                               "ride__vehicle").exclude(status="withdrawn")
        return Response([{"id": e.pk, "status": e.status, "offer_expires_at": _dt(e.offer_expires_at),
                          "ride": ride_json(e.ride, request.user)} for e in entries])


class WaitlistActionView(APIView):
    def post(self, request, pk, action):
        entry = get_object_or_404(WaitlistEntry, pk=pk)
        if action == "accept":
            b = services.accept_waitlist_offer(entry, request.user, policy_ack=bool(request.data.get("policy_ack")))
            return Response(booking_json(b, request.user), status=status.HTTP_201_CREATED)
        if action == "withdraw":
            services.withdraw_waitlist(entry, request.user)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_404_NOT_FOUND)
