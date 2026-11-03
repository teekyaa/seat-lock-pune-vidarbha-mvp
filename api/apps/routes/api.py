from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api import _rate_limit
from apps.core.errors import DomainError

from . import mappls
from . import services as routes
from .models import Place, Route

SEARCHES_PER_MINUTE = 30


def _int_param(params, name):
    try:
        return int(params.get(name, ""))
    except ValueError:
        raise DomainError(f"Choose a valid {name.replace('_', ' ')}.") from None


class PlacesView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response([
            {"id": p.pk, "name": p.name, "region": p.region,
             "aliases": [a.strip() for a in p.aliases.split(",") if a.strip()]}
            for p in Place.objects.all()
        ])


class RoutesView(APIView):
    """Routes that pass From and then To, for the via-route choice when posting."""
    permission_classes = [AllowAny]

    def get(self, request):
        a = get_object_or_404(Place, pk=_int_param(request.query_params, "from"))
        b = get_object_or_404(Place, pk=_int_param(request.query_params, "to"))
        if a.pk == b.pk:
            raise DomainError("Choose two different places.")
        return Response([routes.option_json(o) for o in routes.routes_between(a, b)])


class RouteQuoteView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params
        route = get_object_or_404(Route, pk=_int_param(q, "route"), active=True)
        a = get_object_or_404(Place, pk=_int_param(q, "from"))
        b = get_object_or_404(Place, pk=_int_param(q, "to"))
        seats = _int_param(q, "seats")
        if not 1 <= seats <= 7:
            raise DomainError("Seats must be between 1 and 7.")
        return Response(routes.quote(route, a, b, seats))


class PlaceSearchView(APIView):
    """Mappls place search for an exact pickup point. When Mappls is off, the app falls back to free text."""

    def get(self, request):
        if not mappls.configured():
            return Response({"available": False, "results": []})
        if not _rate_limit(f"mappls:user:{request.user.pk}", SEARCHES_PER_MINUTE, 60):
            return Response({"detail": "Too many searches. Type the place instead.", "code": "rate_limited"},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        near = None
        if request.query_params.get("near"):
            place = get_object_or_404(Place, pk=_int_param(request.query_params, "near"))
            near = (place.lat, place.lng)
        try:
            results = mappls.autosuggest(request.query_params.get("q", ""), near=near)
        except mappls.MapplsUnavailable:
            return Response({"available": False, "results": []})
        return Response({"available": True, "results": results})
