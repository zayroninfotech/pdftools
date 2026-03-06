from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, UsageLog, AuditTrail, SignatureRecord, AnonymousSession


# ─── CUSTOM USER ADMIN ──────────────────────────────────────────────────────

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'created_at')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-created_at',)

    fieldsets = UserAdmin.fieldsets + (
        ('Role & Company', {
            'fields': ('role', 'phone', 'company'),
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Company', {
            'fields': ('role', 'email', 'first_name', 'last_name', 'phone', 'company'),
        }),
    )


# ─── USAGE LOG ADMIN ────────────────────────────────────────────────────────

@admin.register(UsageLog)
class UsageLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'tool_name', 'success', 'ip_address', 'created_at')
    list_filter = ('tool_name', 'success', 'created_at')
    search_fields = ('email', 'tool_name', 'user__username')
    ordering = ('-created_at',)
    readonly_fields = ('user', 'session_key', 'email', 'tool_name', 'filename',
                       'file_size', 'ip_address', 'user_agent', 'created_at', 'success')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ─── AUDIT TRAIL ADMIN (Read-Only - 21 CFR Part 11) ─────────────────────────

@admin.register(AuditTrail)
class AuditTrailAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'username', 'email', 'action', 'document_name', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('username', 'email', 'detail', 'document_name')
    ordering = ('-timestamp',)
    readonly_fields = ('id', 'user', 'email', 'username', 'action', 'detail',
                       'document_name', 'ip_address', 'user_agent', 'timestamp', 'checksum')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # 21 CFR Part 11: Audit trails are immutable


# ─── SIGNATURE RECORD ADMIN (Read-Only - 21 CFR Part 11) ────────────────────

@admin.register(SignatureRecord)
class SignatureRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'signer_name', 'signer_email', 'meaning',
                    'document_name', 'is_authenticated', 'signed_at')
    list_filter = ('meaning', 'is_authenticated', 'signed_at')
    search_fields = ('signer_name', 'signer_email', 'document_name')
    ordering = ('-signed_at',)
    readonly_fields = ('id', 'user', 'signer_name', 'signer_email', 'meaning',
                       'document_name', 'document_hash_before', 'document_hash_after',
                       'output_file', 'position_x', 'position_y', 'page_number',
                       'is_authenticated', 'ip_address', 'user_agent', 'signed_at',
                       'record_checksum')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False  # 21 CFR Part 11: Signature records are immutable


# ─── ANONYMOUS SESSION ADMIN ────────────────────────────────────────────────

@admin.register(AnonymousSession)
class AnonymousSessionAdmin(admin.ModelAdmin):
    list_display = ('email', 'usage_count', 'ip_address', 'created_at', 'last_used')
    list_filter = ('created_at',)
    search_fields = ('email',)
    ordering = ('-last_used',)
    readonly_fields = ('email', 'session_key', 'usage_count', 'ip_address',
                       'created_at', 'last_used')
