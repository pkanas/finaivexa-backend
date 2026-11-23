"""Consistent API response helpers."""
from rest_framework.response import Response


def api_success(data=None, message=None, status=200, **extra):
    """Return a uniformly shaped successful response.

    Shape: ``{"success": true, "message": ..., "data": ...}``
    """
    payload = {"success": True}
    if message:
        payload["message"] = message
    payload["data"] = {} if data is None else data
    payload.update(extra)
    return Response(payload, status=status)


def api_error(message, code="error", details=None, status=400):
    """Return a uniformly shaped error response (rarely needed directly;
    the custom exception handler builds this automatically)."""
    return Response(
        {
            "success": False,
            "error": {"code": code, "message": message, "details": details},
        },
        status=status,
    )
