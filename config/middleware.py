"""Lightweight CORS and development header middleware for API and mobile clients."""

from django.conf import settings
from django.http import HttpResponse


class CorsMiddleware:
    """Adds Cross-Origin Resource Sharing (CORS) headers to responses.

    Ensures React Native apps, Expo Go, and browser web previews can communicate
    with the Django REST API without CORS or preflight issues.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Handle CORS preflight OPTIONS request
        if request.method == "OPTIONS" and (request.path.startswith("/api/") or settings.DEBUG):
            response = HttpResponse()
            self._apply_cors_headers(response)
            return response

        response = self.get_response(request)

        if request.path.startswith("/api/") or settings.DEBUG:
            self._apply_cors_headers(response)

        return response

    @staticmethod
    def _apply_cors_headers(response):
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept"
