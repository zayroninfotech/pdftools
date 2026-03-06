import time
import hashlib
from collections import defaultdict
from django.http import JsonResponse
from django.conf import settings


# ─── RATE LIMIT MIDDLEWARE ──────────────────────────────────────────────────

class RateLimitMiddleware:
    """
    IP-based rate limiting middleware.
    Limits requests per IP to prevent abuse.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.requests = defaultdict(list)
        self.max_requests = getattr(settings, 'RATE_LIMIT_REQUESTS', 100)
        self.window = getattr(settings, 'RATE_LIMIT_WINDOW', 60)

    def __call__(self, request):
        ip = self._get_client_ip(request)
        now = time.time()

        # Clean old entries
        self.requests[ip] = [
            t for t in self.requests[ip]
            if now - t < self.window
        ]

        if len(self.requests[ip]) >= self.max_requests:
            return JsonResponse({
                'error': 'Too many requests. Please wait and try again.',
                'retry_after': self.window,
            }, status=429)

        self.requests[ip].append(now)
        response = self.get_response(request)
        return response

    @staticmethod
    def _get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '0.0.0.0')


# ─── SECURITY HEADERS MIDDLEWARE (VAPT) ─────────────────────────────────────

class SecurityHeadersMiddleware:
    """
    Adds security headers for VAPT compliance.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Prevent MIME type sniffing
        response['X-Content-Type-Options'] = 'nosniff'

        # XSS Protection
        response['X-XSS-Protection'] = '1; mode=block'

        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Permissions Policy (restrict browser features)
        response['Permissions-Policy'] = (
            'camera=(), microphone=(), geolocation=(), '
            'payment=(), usb=(), magnetometer=()'
        )

        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' "
            "https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' "
            "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com "
            "https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com "
            "https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self';"
        )

        # Cache Control for sensitive pages
        if request.path.startswith(('/login', '/profile', '/users', '/doc-signer')):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response['Pragma'] = 'no-cache'

        return response


# ─── AUDIT MIDDLEWARE ────────────────────────────────────────────────────────

class AuditMiddleware:
    """
    Middleware that logs authentication events to the audit trail.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response
