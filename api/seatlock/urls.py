from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path

from apps.accounts import api as accounts
from apps.bookings import api as bookings
from apps.notifications import api as notifications

admin.site.site_header = "Seat Lock ops"
admin.site.site_title = "Seat Lock ops"

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
    path("me/notifications", notifications.InboxView.as_view()),
    path("push/key", accounts.PushKeyView.as_view()),
    path("push/subscriptions", accounts.PushSubscriptionView.as_view()),
    path("users/<uuid:pk>", accounts.PublicProfileView.as_view()),
    path("city-pairs", bookings.CityPairsView.as_view()),
    path("fare-quote", bookings.FareQuoteView.as_view()),
    path("policy", bookings.PolicyView.as_view()),
    path("rides", bookings.RideListView.as_view()),
    path("rides/<str:code>", bookings.RideDetailView.as_view()),
    path("rides/<str:code>/bookings", bookings.RideBookingsView.as_view()),
    path("rides/<str:code>/<str:action>", bookings.RideActionView.as_view()),
    path("bookings/<str:code>", bookings.BookingDetailView.as_view()),
    path("bookings/<str:code>/<str:action>", bookings.BookingActionView.as_view()),
    path("waitlist/<int:pk>/<str:action>", bookings.WaitlistActionView.as_view()),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", lambda request: JsonResponse({"ok": True})),
    path("api/v1/", include(api)),
]
