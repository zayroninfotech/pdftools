import uuid
import hashlib
import json
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


# ─── CUSTOM USER MODEL ──────────────────────────────────────────────────────

class CustomUser(AbstractUser):
    """
    Extended User model with role-based access control.
    Roles: superadmin, admin, user, viewer
    """
    ROLE_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('admin', 'Admin'),
        ('user', 'User'),
        ('viewer', 'Viewer'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    phone = models.CharField(max_length=20, blank=True, default='')
    company = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_superadmin(self):
        return self.role == 'superadmin'

    @property
    def is_admin_role(self):
        return self.role in ('superadmin', 'admin')

    @property
    def is_user_role(self):
        return self.role == 'user'

    @property
    def is_viewer_role(self):
        return self.role == 'viewer'

    @property
    def has_unlimited_access(self):
        return self.role in ('superadmin', 'admin')

    def get_daily_limit(self):
        """Returns the daily usage limit for this user's role."""
        from django.conf import settings
        limits = getattr(settings, 'USAGE_LIMITS', {})
        return limits.get(self.role, 5)

    def get_today_usage_count(self):
        """Returns how many tools the user has used today."""
        today = timezone.now().date()
        return UsageLog.objects.filter(
            user=self,
            created_at__date=today,
            success=True
        ).count()

    def can_use_tool(self):
        """Check if user can still use tools today."""
        if self.has_unlimited_access:
            return True
        limit = self.get_daily_limit()
        if limit is None:
            return True
        return self.get_today_usage_count() < limit

    def remaining_uses(self):
        """Returns remaining tool uses for today."""
        if self.has_unlimited_access:
            return -1  # Unlimited
        limit = self.get_daily_limit()
        if limit is None:
            return -1
        return max(0, limit - self.get_today_usage_count())


# ─── USAGE LOG ──────────────────────────────────────────────────────────────

class UsageLog(models.Model):
    """
    Tracks every tool usage for rate limiting and analytics.
    Supports both authenticated and anonymous users.
    """
    user = models.ForeignKey(
        CustomUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='usage_logs'
    )
    session_key = models.CharField(max_length=255, blank=True, default='')
    email = models.CharField(max_length=255, blank=True, default='')
    tool_name = models.CharField(max_length=100)
    filename = models.CharField(max_length=500, blank=True, default='')
    file_size = models.BigIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)

    class Meta:
        db_table = 'usage_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['session_key', 'email']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        who = self.user.username if self.user else (self.email or 'anonymous')
        return f"{who} - {self.tool_name} @ {self.created_at}"


# ─── ANONYMOUS SESSION TRACKING ─────────────────────────────────────────────

class AnonymousSession(models.Model):
    """
    Tracks anonymous user sessions by email + session key.
    Used for enforcing usage limits on non-authenticated users.
    """
    email = models.CharField(max_length=255, db_index=True)
    session_key = models.CharField(max_length=255, db_index=True)
    usage_count = models.IntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'anonymous_sessions'
        unique_together = ('email', 'session_key')

    def __str__(self):
        return f"{self.email} (uses: {self.usage_count})"

    def can_use_tool(self):
        """Check if anonymous user can still use tools in this session."""
        from django.conf import settings
        limit = getattr(settings, 'USAGE_LIMITS', {}).get('anonymous', 2)
        return self.usage_count < limit

    def remaining_uses(self):
        """Returns remaining tool uses for this session."""
        from django.conf import settings
        limit = getattr(settings, 'USAGE_LIMITS', {}).get('anonymous', 2)
        return max(0, limit - self.usage_count)

    def increment_usage(self):
        """Increment usage count by 1."""
        self.usage_count += 1
        self.save(update_fields=['usage_count', 'last_used'])


# ─── AUDIT TRAIL (21 CFR Part 11 Compliance) ────────────────────────────────

class AuditTrail(models.Model):
    """
    Immutable audit trail for 21 CFR Part 11 compliance.
    Records all significant system actions with tamper-detection checksums.
    These records must NEVER be modified or deleted.
    """
    ACTION_CHOICES = [
        ('sign', 'Document Signed'),
        ('login', 'User Login'),
        ('login_failed', 'Login Failed'),
        ('logout', 'User Logout'),
        ('create_user', 'User Created'),
        ('edit_user', 'User Edited'),
        ('delete_user', 'User Deleted'),
        ('tool_use', 'Tool Used'),
        ('download', 'File Downloaded'),
        ('password_change', 'Password Changed'),
        ('session_start', 'Session Started'),
        ('limit_reached', 'Usage Limit Reached'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_trails'
    )
    email = models.CharField(max_length=255, blank=True, default='')
    username = models.CharField(max_length=255, blank=True, default='')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    detail = models.TextField(blank=True, default='')
    document_name = models.CharField(max_length=500, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)
    checksum = models.CharField(max_length=128, blank=True, default='')

    class Meta:
        db_table = 'audit_trail'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        who = self.username or self.email or 'system'
        return f"[{self.timestamp}] {who}: {self.get_action_display()}"

    def save(self, *args, **kwargs):
        """Override save to compute tamper-detection checksum."""
        if not self.checksum:
            self.checksum = self._compute_checksum()
        super().save(*args, **kwargs)

    def _compute_checksum(self):
        """Compute SHA-512 checksum from audit data for tamper detection."""
        data = json.dumps({
            'user_id': str(self.user_id) if self.user_id else '',
            'email': self.email,
            'username': self.username,
            'action': self.action,
            'detail': self.detail,
            'document_name': self.document_name,
            'ip_address': str(self.ip_address) if self.ip_address else '',
            'timestamp': str(self.timestamp) if self.timestamp else str(timezone.now()),
        }, sort_keys=True)
        return hashlib.sha512(data.encode('utf-8')).hexdigest()

    def verify_integrity(self):
        """Verify this audit record has not been tampered with."""
        return self.checksum == self._compute_checksum()

    @classmethod
    def log(cls, action, request=None, user=None, email='', detail='',
            document_name=''):
        """
        Convenience method to create an audit trail entry.
        """
        ip_address = None
        user_agent = ''
        username = ''

        if request:
            ip_address = cls._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
            if not user and hasattr(request, 'user') and request.user.is_authenticated:
                user = request.user

        if user:
            email = email or user.email
            username = user.username

        return cls.objects.create(
            user=user,
            email=email,
            username=username,
            action=action,
            detail=detail,
            document_name=document_name,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request, handling proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')


# ─── SIGNATURE RECORD (21 CFR Part 11 Electronic Signatures) ────────────────

class SignatureRecord(models.Model):
    """
    Electronic signature record for 21 CFR Part 11 compliance.
    Each record represents a legally binding electronic signature applied to a document.

    Per 21 CFR Part 11 requirements:
    - Linked to signer identity (name, email, user account)
    - Includes meaning of signature (approved, reviewed, etc.)
    - Timestamped with date and time
    - Document integrity verified via SHA-512 hashes
    - Signer authentication status recorded
    - Unique signature ID for verification
    """
    MEANING_CHOICES = [
        ('approved', 'Approved'),
        ('reviewed', 'Reviewed'),
        ('authored', 'Authored'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
        ('acknowledged', 'Acknowledged'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        CustomUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='signatures'
    )

    # Signer identity
    signer_name = models.CharField(max_length=255)
    signer_email = models.CharField(max_length=255)
    meaning = models.CharField(max_length=50, choices=MEANING_CHOICES)

    # Document information
    document_name = models.CharField(max_length=500)
    document_hash_before = models.CharField(max_length=128)  # SHA-512 of original
    document_hash_after = models.CharField(max_length=128)   # SHA-512 of signed
    output_file = models.CharField(max_length=500, blank=True, default='')

    # Signature placement
    position_x = models.FloatField(default=0)
    position_y = models.FloatField(default=0)
    page_number = models.IntegerField(default=1)

    # Authentication & security
    is_authenticated = models.BooleanField(default=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')

    # Timestamps
    signed_at = models.DateTimeField(auto_now_add=True)

    # Verification checksum
    record_checksum = models.CharField(max_length=128, blank=True, default='')

    class Meta:
        db_table = 'signature_records'
        ordering = ['-signed_at']
        indexes = [
            models.Index(fields=['signer_email', 'signed_at']),
            models.Index(fields=['document_name']),
        ]

    def __str__(self):
        return (f"Sig:{self.id} | {self.signer_name} | "
                f"{self.get_meaning_display()} | {self.signed_at}")

    def save(self, *args, **kwargs):
        """Compute record checksum on save."""
        if not self.record_checksum:
            self.record_checksum = self._compute_checksum()
        super().save(*args, **kwargs)

    def _compute_checksum(self):
        """SHA-512 checksum of the signature record for tamper detection."""
        data = json.dumps({
            'signer_name': self.signer_name,
            'signer_email': self.signer_email,
            'meaning': self.meaning,
            'document_name': self.document_name,
            'document_hash_before': self.document_hash_before,
            'document_hash_after': self.document_hash_after,
            'position_x': self.position_x,
            'position_y': self.position_y,
            'page_number': self.page_number,
            'signed_at': str(self.signed_at) if self.signed_at else str(timezone.now()),
        }, sort_keys=True)
        return hashlib.sha512(data.encode('utf-8')).hexdigest()

    def verify_integrity(self):
        """Verify this signature record has not been tampered with."""
        return self.record_checksum == self._compute_checksum()

    def get_signature_manifest(self):
        """
        Returns the signature manifestation text per 21 CFR Part 11.
        This is what appears on the signed document.
        """
        return {
            'signature_id': str(self.id),
            'signer_name': self.signer_name,
            'signer_email': self.signer_email,
            'meaning': self.get_meaning_display(),
            'signed_at': self.signed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if self.signed_at else '',
            'authenticated': self.is_authenticated,
        }
