"""Answers /healthz with 200 before any other middleware runs.

Azure's health probes call the container by its internal IP, which is not in
ALLOWED_HOSTS and does not come in over HTTPS — so the check has to happen
before host validation and the HTTPS redirect.
"""
from django.http import HttpResponse

HEALTH_PATH = '/healthz'


class HealthCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH:
            return HttpResponse('ok', content_type='text/plain')
        return self.get_response(request)
