from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.errors import DomainError
from apps.core.models import CityPair

from . import services
from .models import SeatWanted


def _seat_wanted_json(wanted):
    return {
        "id": wanted.pk,
        "city_pair_id": wanted.city_pair_id,
        "origin": wanted.city_pair.origin,
        "destination": wanted.city_pair.destination,
        "travel_date": wanted.travel_date.isoformat(),
        "seats": wanted.seats,
        "flex_days": wanted.flex_days,
        "created_at": wanted.created_at.isoformat(),
    }


class UserVouchView(APIView):
    def post(self, request, pk):
        vouchee = get_object_or_404(User, pk=pk, is_active=True)
        vouch = services.vouch_for(request.user, vouchee)
        return Response({"active": True, "created_at": vouch.created_at.isoformat()}, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        vouchee = get_object_or_404(User, pk=pk)
        services.withdraw_vouch(request.user, vouchee)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MySeatWantedView(APIView):
    def get(self, request):
        requests = SeatWanted.objects.filter(passenger=request.user, closed_at__isnull=True).select_related(
            "city_pair"
        ).order_by("travel_date", "created_at")
        return Response([_seat_wanted_json(wanted) for wanted in requests])

    def post(self, request):
        try:
            city_pair_id = int(request.data.get("city_pair"))
            seats = int(request.data.get("seats", 1))
            flex_days = int(request.data.get("flex_days", 0))
        except (TypeError, ValueError):
            raise DomainError("Choose a route, number of seats, and date flexibility.")
        city_pair = get_object_or_404(CityPair, pk=city_pair_id, active=True)
        travel_date = parse_date(str(request.data.get("travel_date", "")))
        if travel_date is None:
            raise DomainError("Choose a valid travel date.")
        wanted = services.create_seat_wanted(request.user, city_pair, travel_date, seats, flex_days)
        wanted = SeatWanted.objects.select_related("city_pair").get(pk=wanted.pk)
        return Response(_seat_wanted_json(wanted), status=status.HTTP_201_CREATED)


class SeatWantedDetailView(APIView):
    def delete(self, request, pk):
        wanted = get_object_or_404(SeatWanted, pk=pk)
        services.close_seat_wanted(wanted, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
