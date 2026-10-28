from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.timefmt import ist

from .models import Notification


class InboxView(APIView):
    def get(self, request):
        rows = Notification.objects.filter(user=request.user, status=Notification.Status.SENT).exclude(title="")[:50]
        return Response({
            "unread": Notification.objects.filter(user=request.user, status="sent", read_at__isnull=True)
            .exclude(title="").count(),
            "items": [
                {"id": n.pk, "kind": n.kind, "title": n.title, "body": n.body, "url": n.url,
                 "sent_at": {"utc": n.sent_at.isoformat(), "ist": ist(n.sent_at)}, "read": bool(n.read_at)}
                for n in rows
            ],
        })

    def post(self, request):
        Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=timezone.now())
        return Response({"unread": 0})
