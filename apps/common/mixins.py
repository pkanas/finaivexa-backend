"""View mixins used across all applications."""


class EnvelopeMixin:
    """Wraps successful viewset responses in the standard API envelope.

    Responses that are already enveloped (through ``api_success``) or error
    responses are left untouched.
    """

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        data = getattr(response, "data", None)
        if (
            response.status_code < 400
            and isinstance(data, (dict, list))
            and not (isinstance(data, dict) and "success" in data)
        ):
            response.data = {"success": True, "data": data}
        return response
