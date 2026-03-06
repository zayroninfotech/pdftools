import os
import mimetypes
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import FileResponse, Http404, JsonResponse
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.utils import timezone
from . import utils
from .models import (
    CustomUser, UsageLog, AuditTrail, SignatureRecord, AnonymousSession
)
from . import mongodb as mdb


# ─── TOOLS CONFIGURATION ────────────────────────────────────────────────────

TOOLS = [
    {
        'name': 'Merge PDF',
        'slug': 'merge',
        'url_name': 'converter:merge',
        'icon': 'fa-object-group',
        'color': '#00bcd4',
        'description': 'Combine multiple PDF files into a single document.',
        'accept': '.pdf',
        'multiple': True,
    },
    {
        'name': 'Split PDF',
        'slug': 'split',
        'url_name': 'converter:split',
        'icon': 'fa-scissors',
        'color': '#ef6c00',
        'description': 'Separate PDF pages into individual files.',
        'accept': '.pdf',
        'multiple': False,
    },
    {
        'name': 'Compress PDF',
        'slug': 'compress',
        'url_name': 'converter:compress',
        'icon': 'fa-compress',
        'color': '#2e7d32',
        'description': 'Reduce the file size of your PDF.',
        'accept': '.pdf',
        'multiple': False,
    },
    {
        'name': 'PDF to Word',
        'slug': 'pdf_to_word',
        'url_name': 'converter:pdf_to_word',
        'icon': 'fa-file-word',
        'color': '#1565c0',
        'description': 'Convert PDF documents to editable Word files.',
        'accept': '.pdf',
        'multiple': False,
    },
    {
        'name': 'Word to PDF',
        'slug': 'word_to_pdf',
        'url_name': 'converter:word_to_pdf',
        'icon': 'fa-file-pdf',
        'color': '#c62828',
        'description': 'Convert Word documents to PDF format.',
        'accept': '.docx,.doc',
        'multiple': False,
    },
    {
        'name': 'PDF to JPG',
        'slug': 'pdf_to_jpg',
        'url_name': 'converter:pdf_to_jpg',
        'icon': 'fa-file-image',
        'color': '#f9a825',
        'description': 'Extract images from PDF or convert pages to JPG.',
        'accept': '.pdf',
        'multiple': False,
    },
    {
        'name': 'JPG to PDF',
        'slug': 'jpg_to_pdf',
        'url_name': 'converter:jpg_to_pdf',
        'icon': 'fa-images',
        'color': '#00897b',
        'description': 'Convert JPG images into a PDF document.',
        'accept': '.jpg,.jpeg,.png,.bmp,.gif,.webp',
        'multiple': True,
    },
    {
        'name': 'Rotate PDF',
        'slug': 'rotate',
        'url_name': 'converter:rotate',
        'icon': 'fa-rotate',
        'color': '#039be5',
        'description': 'Rotate PDF pages to the angle you need.',
        'accept': '.pdf',
        'multiple': False,
    },
    {
        'name': 'Add Watermark',
        'slug': 'watermark',
        'url_name': 'converter:watermark',
        'icon': 'fa-droplet',
        'color': '#7b1fa2',
        'description': 'Add a text watermark over your PDF pages.',
        'accept': '.pdf',
        'multiple': False,
    },
    {
        'name': 'Protect PDF',
        'slug': 'protect',
        'url_name': 'converter:protect',
        'icon': 'fa-lock',
        'color': '#d84315',
        'description': 'Protect your PDF with a password.',
        'accept': '.pdf',
        'multiple': False,
    },
    {
        'name': 'Unlock PDF',
        'slug': 'unlock',
        'url_name': 'converter:unlock',
        'icon': 'fa-lock-open',
        'color': '#00c853',
        'description': 'Remove password protection from a PDF.',
        'accept': '.pdf',
        'multiple': False,
    },
    {
        'name': 'Page Numbers',
        'slug': 'page_numbers',
        'url_name': 'converter:page_numbers',
        'icon': 'fa-list-ol',
        'color': '#37474f',
        'description': 'Add page numbers to your PDF document.',
        'accept': '.pdf',
        'multiple': False,
    },
    {
        'name': 'Document Signer',
        'slug': 'doc_signer',
        'url_name': 'converter:doc_signer',
        'icon': 'fa-file-signature',
        'color': '#6a1b9a',
        'description': '21 CFR Part 11 compliant electronic document signing.',
        'accept': '.pdf,.docx,.doc',
        'multiple': False,
    },
    {
        'name': 'Data Extractor',
        'slug': 'data_extractor',
        'url_name': 'converter:data_extractor',
        'icon': 'fa-database',
        'color': '#e65200',
        'description': 'OCR-powered PDF data extraction. Download as Excel or JSON.',
        'accept': '.pdf',
        'multiple': False,
    },
]


# ─── HELPER FUNCTIONS ────────────────────────────────────────────────────────

def _get_tool(slug):
    for t in TOOLS:
        if t['slug'] == slug:
            return t
    return None


def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _check_email_provided(request):
    """
    Check if anonymous user has submitted their email.
    All tools are free — no usage limits.
    Returns (has_email: bool)
    """
    if request.user.is_authenticated:
        return True
    email = request.session.get('anonymous_email', '')
    return bool(email)


def _log_usage(request, tool_name, filename='', file_size=0, success=True):
    """Log a tool usage. Syncs to MongoDB. Free access — no limits."""
    email = ''
    user = None
    session_key = request.session.session_key or ''
    ip_address = _get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

    if request.user.is_authenticated:
        user = request.user
        email = user.email
    else:
        email = request.session.get('anonymous_email', '')

    UsageLog.objects.create(
        user=user,
        session_key=session_key,
        email=email,
        tool_name=tool_name,
        filename=filename,
        file_size=file_size,
        ip_address=ip_address,
        user_agent=user_agent,
        success=success,
    )

    # MongoDB sync: usage log
    mdb.log_usage(
        user=user, session_key=session_key, email=email,
        tool_name=tool_name, filename=filename, file_size=file_size,
        ip_address=ip_address, user_agent=user_agent, success=success,
    )

    # Audit trail
    if success:
        audit = AuditTrail.log(
            action='tool_use',
            request=request,
            email=email,
            detail=f'Used tool: {tool_name}',
            document_name=filename,
        )
        # MongoDB sync: audit trail
        if audit:
            mdb.log_audit(
                audit_id=audit.id, user=audit.user, email=audit.email,
                username=audit.username, action=audit.action,
                detail=audit.detail, document_name=audit.document_name,
                ip_address=str(audit.ip_address) if audit.ip_address else None,
                user_agent=audit.user_agent, timestamp=audit.timestamp,
                checksum=audit.checksum,
            )


def _get_user_info(request):
    """Get user info dict for templates. Free access — no limits."""
    if request.user.is_authenticated:
        user = request.user
        return {
            'is_authenticated': True,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'role_display': user.get_role_display(),
            'is_admin_role': user.is_admin_role,
        }
    else:
        email = request.session.get('anonymous_email', '')
        return {
            'is_authenticated': False,
            'email': email,
            'role': 'anonymous',
        }


# ─── HOME VIEW ──────────────────────────────────────────────────────────────

def home(request):
    utils.cleanup_old_files()
    context = {
        'tools': TOOLS,
        'user_info': _get_user_info(request),
    }
    return render(request, 'converter/home.html', context)


# ─── DOWNLOAD VIEW ──────────────────────────────────────────────────────────

def download_file(request, filename):
    filepath = os.path.join(settings.MEDIA_ROOT, 'outputs', filename)
    if not os.path.exists(filepath):
        raise Http404("File not found")
    content_type, _ = mimetypes.guess_type(filepath)
    response = FileResponse(
        open(filepath, 'rb'),
        content_type=content_type or 'application/octet-stream'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─── TOOL VIEW HELPERS ──────────────────────────────────────────────────────

def _tool_context(slug, extra=None):
    ctx = {'tool': _get_tool(slug), 'tools': TOOLS}
    if extra:
        ctx.update(extra)
    return ctx


@csrf_exempt
def _process_and_respond(request, slug, process_fn):
    """
    Unified tool view handler. Free access — no usage limits.
    Only requires anonymous users to provide their email first.
    CSRF exempted for file upload processing.
    """
    if request.method == 'POST':
        # Check if anonymous user has email set
        if not _check_email_provided(request):
            return JsonResponse({
                'success': False,
                'need_email': True,
                'error': 'Please provide your email to continue.'
            }, status=400)

        try:
            result_path = process_fn(request)
            filename = os.path.basename(result_path)

            # Get file info for logging
            file_size = 0
            uploaded_file = request.FILES.get('files')
            if uploaded_file:
                file_size = uploaded_file.size
            elif request.FILES.getlist('files'):
                file_size = sum(f.size for f in request.FILES.getlist('files'))

            # Log successful usage
            _log_usage(
                request, slug,
                filename=filename,
                file_size=file_size,
                success=True
            )

            return JsonResponse({
                'success': True,
                'download_url': f'/download/{filename}/',
                'filename': filename,
            })
        except Exception as e:
            _log_usage(request, slug, success=False)
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    context = _tool_context(slug)
    context['user_info'] = _get_user_info(request)
    return render(request, 'converter/tool.html', context)


# ─── AUTHENTICATION VIEWS ───────────────────────────────────────────────────

@csrf_protect
def login_view(request):
    if request.user.is_authenticated:
        return redirect('converter:home')

    error = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                audit = AuditTrail.log(
                    action='login',
                    request=request,
                    user=user,
                    detail=f'User logged in successfully. Role: {user.role}',
                )
                # MongoDB sync: login audit
                if audit:
                    mdb.log_audit(
                        audit_id=audit.id, user=audit.user, email=audit.email,
                        username=audit.username, action=audit.action,
                        detail=audit.detail, ip_address=str(audit.ip_address) if audit.ip_address else None,
                        user_agent=audit.user_agent, timestamp=audit.timestamp,
                        checksum=audit.checksum,
                    )
                next_url = request.GET.get('next', '/')
                return redirect(next_url)
            else:
                error = 'Your account has been deactivated. Contact admin.'
                audit = AuditTrail.log(
                    action='login_failed',
                    request=request,
                    email=username,
                    detail='Login failed: Account deactivated',
                )
                if audit:
                    mdb.log_audit(
                        audit_id=audit.id, email=audit.email, username=audit.username,
                        action=audit.action, detail=audit.detail,
                        ip_address=str(audit.ip_address) if audit.ip_address else None,
                        user_agent=audit.user_agent, timestamp=audit.timestamp,
                        checksum=audit.checksum,
                    )
        else:
            error = 'Invalid username or password.'
            audit = AuditTrail.log(
                action='login_failed',
                request=request,
                email=username,
                detail='Login failed: Invalid credentials',
            )
            if audit:
                mdb.log_audit(
                    audit_id=audit.id, email=audit.email, username=audit.username,
                    action=audit.action, detail=audit.detail,
                    ip_address=str(audit.ip_address) if audit.ip_address else None,
                    user_agent=audit.user_agent, timestamp=audit.timestamp,
                    checksum=audit.checksum,
                )

    return render(request, 'converter/login.html', {
        'error': error,
        'tools': TOOLS,
    })


def logout_view(request):
    if request.user.is_authenticated:
        AuditTrail.log(
            action='logout',
            request=request,
            detail='User logged out',
        )
    logout(request)
    return redirect('converter:home')


# ─── PROFILE VIEW ───────────────────────────────────────────────────────────

@login_required
def profile_view(request):
    user = request.user
    today = timezone.now().date()

    # Get today's usage
    today_usage = UsageLog.objects.filter(
        user=user, created_at__date=today, success=True
    ).count()

    # Get recent usage
    recent_logs = UsageLog.objects.filter(
        user=user, success=True
    ).order_by('-created_at')[:20]

    context = {
        'tools': TOOLS,
        'user_info': _get_user_info(request),
        'today_usage': today_usage,
        'recent_logs': recent_logs,
    }
    return render(request, 'converter/profile.html', context)


# ─── USER MANAGEMENT VIEWS ──────────────────────────────────────────────────

@login_required
def user_management_view(request):
    if not request.user.is_admin_role:
        return redirect('converter:home')

    users = CustomUser.objects.all().order_by('-created_at')

    # Filtering
    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(role=role_filter)

    search = request.GET.get('search', '')
    if search:
        from django.db.models import Q
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )

    context = {
        'tools': TOOLS,
        'user_info': _get_user_info(request),
        'users': users,
        'role_filter': role_filter,
        'search': search,
        'role_choices': CustomUser.ROLE_CHOICES,
    }
    return render(request, 'converter/user_management.html', context)


@login_required
def create_user_view(request):
    if not request.user.is_admin_role:
        return redirect('converter:home')

    error = ''
    success = ''

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', 'viewer')
        phone = request.POST.get('phone', '').strip()
        company = request.POST.get('company', '').strip()

        # Validate
        if not username or not email or not password:
            error = 'Username, email, and password are required.'
        elif CustomUser.objects.filter(username=username).exists():
            error = f'Username "{username}" already exists.'
        elif CustomUser.objects.filter(email=email).exists():
            error = f'Email "{email}" already exists.'
        else:
            # Restrict role assignment based on current user's role
            if request.user.role == 'admin' and role == 'superadmin':
                error = 'Only superadmins can create superadmin users.'
            else:
                try:
                    new_user = CustomUser.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        first_name=first_name,
                        last_name=last_name,
                        role=role,
                        phone=phone,
                        company=company,
                        is_staff=(role in ('superadmin', 'admin')),
                    )
                    # Sync to MongoDB
                    mdb.sync_user(new_user)

                    AuditTrail.log(
                        action='create_user',
                        request=request,
                        detail=f'Created user: {username} with role: {role}',
                    )
                    success = f'User "{username}" created successfully!'
                except Exception as e:
                    error = f'Error creating user: {str(e)}'

    # Determine available roles based on current user
    if request.user.is_superadmin:
        available_roles = CustomUser.ROLE_CHOICES
    else:
        available_roles = [r for r in CustomUser.ROLE_CHOICES if r[0] != 'superadmin']

    context = {
        'tools': TOOLS,
        'user_info': _get_user_info(request),
        'error': error,
        'success': success,
        'available_roles': available_roles,
    }
    return render(request, 'converter/create_user.html', context)


@login_required
def edit_user_view(request, pk):
    if not request.user.is_admin_role:
        return redirect('converter:home')

    edit_user = get_object_or_404(CustomUser, pk=pk)
    error = ''
    success = ''

    # Prevent non-superadmins from editing superadmins
    if edit_user.is_superadmin and not request.user.is_superadmin:
        return redirect('converter:user_management')

    if request.method == 'POST':
        edit_user.email = request.POST.get('email', edit_user.email).strip()
        edit_user.first_name = request.POST.get('first_name', '').strip()
        edit_user.last_name = request.POST.get('last_name', '').strip()
        edit_user.phone = request.POST.get('phone', '').strip()
        edit_user.company = request.POST.get('company', '').strip()
        edit_user.is_active = request.POST.get('is_active') == 'on'

        new_role = request.POST.get('role', edit_user.role)
        if request.user.role == 'admin' and new_role == 'superadmin':
            error = 'Only superadmins can assign superadmin role.'
        else:
            edit_user.role = new_role
            edit_user.is_staff = (new_role in ('superadmin', 'admin'))

        new_password = request.POST.get('password', '').strip()
        if new_password:
            edit_user.set_password(new_password)

        if not error:
            edit_user.save()
            # Sync to MongoDB
            mdb.sync_user(edit_user)

            AuditTrail.log(
                action='edit_user',
                request=request,
                detail=f'Edited user: {edit_user.username}',
            )
            success = f'User "{edit_user.username}" updated successfully!'

    if request.user.is_superadmin:
        available_roles = CustomUser.ROLE_CHOICES
    else:
        available_roles = [r for r in CustomUser.ROLE_CHOICES if r[0] != 'superadmin']

    context = {
        'tools': TOOLS,
        'user_info': _get_user_info(request),
        'edit_user': edit_user,
        'error': error,
        'success': success,
        'available_roles': available_roles,
    }
    return render(request, 'converter/edit_user.html', context)


@login_required
@require_POST
def delete_user_view(request, pk):
    if not request.user.is_admin_role:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    delete_user = get_object_or_404(CustomUser, pk=pk)

    # Prevent deleting self or superadmin by non-superadmin
    if delete_user == request.user:
        return JsonResponse({'error': 'Cannot delete yourself'}, status=400)
    if delete_user.is_superadmin and not request.user.is_superadmin:
        return JsonResponse({'error': 'Only superadmins can delete superadmins'}, status=403)

    username = delete_user.username
    delete_user.is_active = False  # Soft delete
    delete_user.save()

    # Sync to MongoDB
    mdb.sync_user_deletion(delete_user)

    AuditTrail.log(
        action='delete_user',
        request=request,
        detail=f'Deactivated user: {username}',
    )
    return JsonResponse({'success': True, 'message': f'User "{username}" deactivated.'})


# ─── ANONYMOUS EMAIL CHECK ──────────────────────────────────────────────────

@csrf_exempt
@require_POST
def check_email_view(request):
    """
    Store anonymous user's email in session and MongoDB.
    Auto-creates the 'email_submissions' collection in MongoDB.
    """
    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip()
    except (json.JSONDecodeError, AttributeError):
        email = request.POST.get('email', '').strip()

    if not email or '@' not in email:
        return JsonResponse({'error': 'Please enter a valid email address.'}, status=400)

    try:
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()

        session_key = request.session.session_key
        ip_address = _get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]

        # Store email in Django session
        request.session['anonymous_email'] = email

        # Store email in MongoDB (auto-creates collection)
        mdb.store_email(
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            session_key=session_key,
        )

        # Audit trail
        try:
            audit = AuditTrail.log(
                action='session_start',
                request=request,
                email=email,
                detail=f'Email submitted: {email}',
            )
            if audit:
                mdb.log_audit(
                    audit_id=audit.id, email=audit.email, username=audit.username,
                    action=audit.action, detail=audit.detail,
                    ip_address=str(audit.ip_address) if audit.ip_address else None,
                    user_agent=audit.user_agent, timestamp=audit.timestamp,
                    checksum=audit.checksum,
                )
        except Exception as audit_err:
            # Log audit error but don't fail the request
            import logging as log
            log.getLogger(__name__).error(f"Audit logging failed: {audit_err}")

        return JsonResponse({
            'success': True,
            'message': 'Email registered. Enjoy unlimited free access!',
        })
    except Exception as e:
        import logging as log
        log.getLogger(__name__).error(f"Email check failed: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': 'Failed to process email. Please try again.',
            'detail': str(e) if settings.DEBUG else None,
        }, status=500)


# ─── AUDIT LOG VIEW (Admin only) ────────────────────────────────────────────

@login_required
def audit_log_view(request):
    if not request.user.is_admin_role:
        return redirect('converter:home')

    logs = AuditTrail.objects.all().order_by('-timestamp')[:200]

    # Filtering
    action_filter = request.GET.get('action', '')
    if action_filter:
        logs = AuditTrail.objects.filter(action=action_filter).order_by('-timestamp')[:200]

    context = {
        'tools': TOOLS,
        'user_info': _get_user_info(request),
        'logs': logs,
        'action_filter': action_filter,
        'action_choices': AuditTrail.ACTION_CHOICES,
    }
    return render(request, 'converter/audit_log.html', context)


# ─── PDF TOOL VIEWS ─────────────────────────────────────────────────────────

@csrf_exempt
def merge_view(request):
    def process(req):
        files = req.FILES.getlist('files')
        if len(files) < 2:
            raise ValueError("Please upload at least 2 PDF files to merge.")
        paths = utils.save_uploaded_files(files)
        return utils.merge_pdfs(paths)
    return _process_and_respond(request, 'merge', process)


@csrf_exempt
def split_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a PDF file.")
        path = utils.save_uploaded_file(f)
        mode = req.POST.get('split_mode', 'all')
        ranges_str = req.POST.get('ranges', '')
        return utils.split_pdf(path, mode=mode, ranges_str=ranges_str)
    return _process_and_respond(request, 'split', process)


@csrf_exempt
def compress_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a PDF file.")
        path = utils.save_uploaded_file(f)
        return utils.compress_pdf(path)
    return _process_and_respond(request, 'compress', process)


@csrf_exempt
def pdf_to_word_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a PDF file.")
        path = utils.save_uploaded_file(f)
        return utils.pdf_to_word(path)
    return _process_and_respond(request, 'pdf_to_word', process)


@csrf_exempt
def word_to_pdf_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a Word document.")
        path = utils.save_uploaded_file(f)
        return utils.word_to_pdf(path)
    return _process_and_respond(request, 'word_to_pdf', process)


@csrf_exempt
def pdf_to_jpg_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a PDF file.")
        path = utils.save_uploaded_file(f)
        return utils.pdf_to_jpg(path)
    return _process_and_respond(request, 'pdf_to_jpg', process)


@csrf_exempt
def jpg_to_pdf_view(request):
    def process(req):
        files = req.FILES.getlist('files')
        if not files:
            raise ValueError("Please upload at least one image.")
        paths = utils.save_uploaded_files(files)
        return utils.jpg_to_pdf(paths)
    return _process_and_respond(request, 'jpg_to_pdf', process)


@csrf_exempt
def rotate_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a PDF file.")
        path = utils.save_uploaded_file(f)
        degrees = req.POST.get('degrees', '90')
        return utils.rotate_pdf(path, degrees=degrees)
    return _process_and_respond(request, 'rotate', process)


@csrf_exempt
def watermark_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a PDF file.")
        path = utils.save_uploaded_file(f)
        text = req.POST.get('watermark_text', 'WATERMARK')
        opacity = req.POST.get('opacity', '0.3')
        font_size = req.POST.get('font_size', '60')
        return utils.add_watermark(path, text=text, opacity=opacity, font_size=font_size)
    return _process_and_respond(request, 'watermark', process)


@csrf_exempt
def protect_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a PDF file.")
        password = req.POST.get('password', '')
        if not password:
            raise ValueError("Please enter a password.")
        path = utils.save_uploaded_file(f)
        return utils.protect_pdf(path, password)
    return _process_and_respond(request, 'protect', process)


@csrf_exempt
def unlock_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a PDF file.")
        password = req.POST.get('password', '')
        if not password:
            raise ValueError("Please enter the PDF password.")
        path = utils.save_uploaded_file(f)
        return utils.unlock_pdf(path, password)
    return _process_and_respond(request, 'unlock', process)


@csrf_exempt
def page_numbers_view(request):
    def process(req):
        f = req.FILES.get('files')
        if not f:
            raise ValueError("Please upload a PDF file.")
        path = utils.save_uploaded_file(f)
        position = req.POST.get('position', 'bottom-center')
        start_num = req.POST.get('start_num', '1')
        return utils.add_page_numbers(path, position=position, start_num=start_num)
    return _process_and_respond(request, 'page_numbers', process)


# ─── DOCUMENT SIGNER VIEWS (21 CFR Part 11) ─────────────────────────────────

@csrf_exempt
def doc_signer_view(request):
    """
    Document Signer tool page - renders the signing interface.
    """
    context = _tool_context('doc_signer')
    context['user_info'] = _get_user_info(request)
    context['meaning_choices'] = SignatureRecord.MEANING_CHOICES
    return render(request, 'converter/doc_signer.html', context)


@require_POST
@csrf_exempt
def signer_preview_view(request):
    """
    Upload a document and return page preview images for the signer interface.
    """
    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'No file uploaded'}, status=400)

    path = utils.save_uploaded_file(f)
    try:
        preview_data = utils.generate_document_preview(path, f.name)
        return JsonResponse({
            'success': True,
            'pages': preview_data['pages'],
            'total_pages': preview_data['total_pages'],
            'file_path': path,
            'original_name': f.name,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_POST
def sign_document_view(request):
    """
    Apply electronic signature to document (21 CFR Part 11 compliant).
    Free access — no usage limits.
    """
    # Check if anonymous user has email set
    if not _check_email_provided(request):
        return JsonResponse({
            'success': False,
            'need_email': True,
            'error': 'Please provide your email to continue.'
        }, status=400)

    # Extract signature data
    file_path = request.POST.get('file_path', '')
    signer_name = request.POST.get('signer_name', '').strip()
    signer_email = request.POST.get('signer_email', '').strip()
    meaning = request.POST.get('meaning', 'approved')
    password = request.POST.get('password', '')
    position_x = float(request.POST.get('position_x', 0))
    position_y = float(request.POST.get('position_y', 0))
    page_number = int(request.POST.get('page_number', 1))
    original_name = request.POST.get('original_name', 'document.pdf')

    # Validate required fields
    if not signer_name:
        return JsonResponse({'error': 'Signer name is required.'}, status=400)
    if not signer_email or '@' not in signer_email:
        return JsonResponse({'error': 'Valid signer email is required.'}, status=400)
    if not file_path or not os.path.exists(file_path):
        return JsonResponse({'error': 'Document not found. Please re-upload.'}, status=400)

    # 21 CFR Part 11: Signer Authentication
    is_authenticated = False
    if request.user.is_authenticated:
        # Re-authenticate the logged-in user
        if not password:
            return JsonResponse({
                'error': 'Password required to authenticate signature (21 CFR Part 11).'
            }, status=400)
        auth_user = authenticate(
            request, username=request.user.username, password=password
        )
        if auth_user is None:
            AuditTrail.log(
                action='sign',
                request=request,
                detail=f'Signature authentication FAILED for: {original_name}',
                document_name=original_name,
            )
            return JsonResponse({
                'error': 'Authentication failed. Incorrect password.'
            }, status=401)
        is_authenticated = True

    try:
        # Sign the document
        result = utils.sign_document(
            file_path=file_path,
            signer_name=signer_name,
            signer_email=signer_email,
            meaning=meaning,
            position_x=position_x,
            position_y=position_y,
            page_number=page_number,
        )

        # Create signature record
        sig_record = SignatureRecord.objects.create(
            user=request.user if request.user.is_authenticated else None,
            signer_name=signer_name,
            signer_email=signer_email,
            meaning=meaning,
            document_name=original_name,
            document_hash_before=result['hash_before'],
            document_hash_after=result['hash_after'],
            output_file=result['output_path'],
            position_x=position_x,
            position_y=position_y,
            page_number=page_number,
            is_authenticated=is_authenticated,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )

        # Sync signature to MongoDB
        mdb.log_signature(sig_record)

        # Audit trail entry
        AuditTrail.log(
            action='sign',
            request=request,
            email=signer_email,
            detail=(
                f'Document signed. Meaning: {meaning}. '
                f'Signature ID: {sig_record.id}. '
                f'Authenticated: {is_authenticated}. '
                f'Page: {page_number}, Position: ({position_x}, {position_y})'
            ),
            document_name=original_name,
        )

        # Log usage
        _log_usage(request, 'doc_signer', filename=original_name, success=True)

        filename = os.path.basename(result['output_path'])
        return JsonResponse({
            'success': True,
            'download_url': f'/download/{filename}/',
            'filename': filename,
            'signature_id': str(sig_record.id),
            'verify_url': f'/doc-signer/verify/{sig_record.id}/',
        })

    except Exception as e:
        _log_usage(request, 'doc_signer', filename=original_name, success=False)
        return JsonResponse({'error': str(e)}, status=400)


def verify_signature_view(request, record_id):
    """
    Public verification page for checking signature authenticity.
    21 CFR Part 11: Ability to verify signatures.
    """
    try:
        sig = SignatureRecord.objects.get(id=record_id)
        integrity_ok = sig.verify_integrity()
    except SignatureRecord.DoesNotExist:
        sig = None
        integrity_ok = False

    context = {
        'tools': TOOLS,
        'signature': sig,
        'integrity_ok': integrity_ok,
        'user_info': _get_user_info(request),
    }
    return render(request, 'converter/verify_signature.html', context)


# ─── PDF DATA EXTRACTOR VIEWS ───────────────────────────────────────────────

@csrf_exempt
def data_extractor_view(request):
    """
    Data Extractor tool page — OCR-powered PDF data extraction.
    Download results as Excel or JSON.
    """
    context = _tool_context('data_extractor')
    context['user_info'] = _get_user_info(request)
    return render(request, 'converter/doc_extractor.html', context)


@require_POST
def extract_data_view(request):
    """
    Process PDF and extract data using text extraction + OCR.
    Returns JSON with preview data and download URL.
    """
    # Check email
    if not _check_email_provided(request):
        return JsonResponse({
            'success': False,
            'need_email': True,
            'error': 'Please provide your email to continue.'
        }, status=400)

    f = request.FILES.get('file')
    if not f:
        return JsonResponse({'error': 'No file uploaded.'}, status=400)

    output_format = request.POST.get('output_format', 'json')
    if output_format not in ('json', 'excel'):
        output_format = 'json'

    file_path = utils.save_uploaded_file(f)

    try:
        result_path = utils.extract_pdf_data(file_path, output_format=output_format)
        filename = os.path.basename(result_path)

        # Read the JSON for preview (even if exporting as Excel)
        preview = {}
        try:
            import json as json_mod
            if output_format == 'json':
                with open(result_path, 'r', encoding='utf-8') as rf:
                    preview_data = json_mod.load(rf)
                    preview = {
                        'total_pages': preview_data.get('document_info', {}).get('total_pages', 0),
                        'extraction_method': preview_data.get('document_info', {}).get('extraction_method', ''),
                        'total_characters': preview_data.get('document_info', {}).get('total_characters', 0),
                        'extracted_fields': preview_data.get('extracted_fields', {}),
                        'raw_text_preview': preview_data.get('raw_text', '')[:500],
                    }
            else:
                # For Excel, do a quick extraction to JSON for preview
                json_path = utils.extract_pdf_data(file_path, output_format='json')
                with open(json_path, 'r', encoding='utf-8') as rf:
                    preview_data = json_mod.load(rf)
                    preview = {
                        'total_pages': preview_data.get('document_info', {}).get('total_pages', 0),
                        'extraction_method': preview_data.get('document_info', {}).get('extraction_method', ''),
                        'total_characters': preview_data.get('document_info', {}).get('total_characters', 0),
                        'extracted_fields': preview_data.get('extracted_fields', {}),
                        'raw_text_preview': preview_data.get('raw_text', '')[:500],
                    }
                # Clean up temp JSON
                try:
                    os.remove(json_path)
                except OSError:
                    pass
        except Exception:
            pass

        # Log usage
        _log_usage(
            request, 'data_extractor',
            filename=f.name,
            file_size=f.size,
            success=True
        )

        return JsonResponse({
            'success': True,
            'download_url': f'/download/{filename}/',
            'filename': filename,
            'format': output_format,
            'preview': preview,
        })

    except Exception as e:
        _log_usage(request, 'data_extractor', filename=f.name, success=False)
        return JsonResponse({'error': str(e)}, status=400)
