from django.contrib import admin
from django.http import JsonResponse
from django.conf import settings
from django.db import connection
from django.core.cache import cache
from uuid import uuid4
from django.http import Http404
import os
from django.urls import include, path

from apps.accounts import api as accounts
from apps.bookings import api as bookings
from apps.notifications import api as notifications
from apps.routes import api as routes
from apps.trust import api as trust

admin.site.site_header = "Seat Lock ops"
admin.site.site_title = "Seat Lock ops"


def loadtest_guard(request):
    if not (settings.DEBUG and os.environ.get('SEATLOCK_LOADTEST_MODE') == 'yes' and
            connection.vendor == 'postgresql' and connection.settings_dict['NAME'] == 'seatlock_loadtest'):
        raise Http404
    return JsonResponse({'synthetic_load_test': True})


def readiness(request):
    key = f'readiness:{uuid4().hex}'
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        cache.set(key, 'ok', timeout=10)
        if cache.get(key) != 'ok':
            raise RuntimeError('Cache probe failed')
        cache.delete(key)
    except Exception:
        return JsonResponse({'ready': False}, status=503)
    return JsonResponse({'ready': True})

api = [
    path("auth/otp/request", accounts.OTPRequestView.as_view()),
    path("auth/otp/verify", accounts.OTPVerifyView.as_view()),
    path("auth/logout", accounts.LogoutView.as_view()),
    path("me", accounts.MeView.as_view()),
    path("me/vehicles", accounts.VehicleListView.as_view()),
    path("me/vehicles/<int:pk>", accounts.VehicleDetailView.as_view()),
    path("me/rides", bookings.MyRidesView.as_view()),
    path("me/bookings", bookings.MyBookingsView.as_view()),
    path("me/waitlist", bookings.MyWaitlistView.as_view()),
    path("me/seat-wanted", trust.MySeatWantedView.as_view()),
    path("seat-wanted", trust.MySeatWantedView.as_view()),
    path("me/notifications", notifications.InboxView.as_view()),
    path("push/key", accounts.PushKeyView.as_view()),
    path("push/subscriptions", accounts.PushSubscriptionView.as_view()),
    path("users/<uuid:pk>", accounts.PublicProfileView.as_view()),
    path("users/<uuid:pk>/vouch", trust.UserVouchView.as_view()),
    path("seat-wanted/<int:pk>", trust.SeatWantedDetailView.as_view()),
    path("city-pairs", bookings.CityPairsView.as_view()),
    path("places", routes.PlacesView.as_view()),
    path("places/search", routes.PlaceSearchView.as_view()),
    path("routes", routes.RoutesView.as_view()),
    path("route-quote", routes.RouteQuoteView.as_view()),
    path("fare-quote", bookings.FareQuoteView.as_view()),
    path("policy", bookings.PolicyView.as_view()),
    path("rides", bookings.RideListView.as_view()),
    path("rides/<str:code>", bookings.RideDetailView.as_view()),
    path("rides/<str:code>/bookings", bookings.RideBookingsView.as_view()),
    path("rides/<str:code>/<str:action>", bookings.RideActionView.as_view()),
    path("bookings/<str:code>", bookings.BookingDetailView.as_view()),
    path("bookings/<str:code>/trip-share", bookings.BookingTripShareView.as_view()),
    path("bookings/<str:code>/<str:action>", bookings.BookingActionView.as_view()),
    path("trip-shares/<str:token>", bookings.PublicTripShareView.as_view()),
    path("waitlist/<int:pk>/<str:action>", bookings.WaitlistActionView.as_view()),
]
if settings.ADMIN_DASHBOARD_ENABLED:
    api.insert(0, path("admin/", include("apps.admin_dashboard.urls")))

urlpatterns = [
    path("healthz", lambda request: JsonResponse({"ok": True})),
    path("readyz", readiness),
    path("internal/loadtest-guard", loadtest_guard),
    path("api/v1/", include(api)),
]
if settings.LEGACY_ADMIN_ENABLED:
    urlpatterns.insert(0, path("admin/", admin.site.urls))
