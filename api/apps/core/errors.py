from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(Exception):
    """A rule was broken. The message is shown to the user as is, so keep it plain."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message, code="invalid"):
        super().__init__(message)
        self.message = message
        self.code = code


class Forbidden(DomainError):
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, message="You can't do that on this booking.", code="forbidden"):
        super().__init__(message, code)


class Conflict(DomainError):
    status_code = status.HTTP_409_CONFLICT


def exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response({"detail": exc.message, "code": exc.code}, status=exc.status_code)
    return drf_exception_handler(exc, context)
