"""Domain exceptions and a single, consistent error response format."""
import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ServiceError(APIException):
    """Raised when a business rule / service operation cannot be completed."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The operation could not be completed."
    default_code = "service_error"


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "A conflicting resource already exists."
    default_code = "conflict"


class PermissionDeniedError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "You do not have permission to perform this action."
    default_code = "permission_denied"


def custom_exception_handler(exc, context):
    """Normalise every DRF error into::

        {"success": false, "error": {"code": ..., "message": ..., "details": ...}}

    Unknown (unhandled) exceptions are logged and returned as a generic 500 so
    that stack traces, SQL or secrets are never leaked to API consumers.
    """
    response = exception_handler(exc, context)

    if response is None:
        logger.exception("Unhandled API exception", exc_info=exc)
        return Response(
            {
                "success": False,
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred. Please try again later.",
                    "details": None,
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    code = getattr(exc, "default_code", None) or "error"
    code = str(code)

    detail = response.data
    if isinstance(detail, dict) and set(detail.keys()) == {"detail"}:
        message = str(detail["detail"])
        details = None
    elif isinstance(detail, list) and len(detail) == 1 and isinstance(detail[0], str):
        message = detail[0]
        details = None
    elif response.status_code == status.HTTP_400_BAD_REQUEST:
        message = "Validation failed. Please check the submitted data."
        details = detail
    else:
        message = "The request could not be completed."
        details = detail

    response.data = {
        "success": False,
        "error": {"code": code, "message": message, "details": details},
    }
    return response
