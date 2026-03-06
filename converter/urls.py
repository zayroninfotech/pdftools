from django.urls import path
from . import views

app_name = 'converter'

urlpatterns = [
    # Home
    path('', views.home, name='home'),

    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),

    # User Management (Admin/Superadmin only)
    path('users/', views.user_management_view, name='user_management'),
    path('users/create/', views.create_user_view, name='create_user'),
    path('users/<int:pk>/edit/', views.edit_user_view, name='edit_user'),
    path('users/<int:pk>/delete/', views.delete_user_view, name='delete_user'),

    # Audit Log (Admin/Superadmin only)
    path('audit-log/', views.audit_log_view, name='audit_log'),

    # Anonymous email check
    path('api/check-email/', views.check_email_view, name='check_email'),

    # PDF Tools
    path('merge/', views.merge_view, name='merge'),
    path('split/', views.split_view, name='split'),
    path('compress/', views.compress_view, name='compress'),
    path('pdf-to-word/', views.pdf_to_word_view, name='pdf_to_word'),
    path('word-to-pdf/', views.word_to_pdf_view, name='word_to_pdf'),
    path('pdf-to-jpg/', views.pdf_to_jpg_view, name='pdf_to_jpg'),
    path('jpg-to-pdf/', views.jpg_to_pdf_view, name='jpg_to_pdf'),
    path('rotate/', views.rotate_view, name='rotate'),
    path('watermark/', views.watermark_view, name='watermark'),
    path('protect/', views.protect_view, name='protect'),
    path('unlock/', views.unlock_view, name='unlock'),
    path('page-numbers/', views.page_numbers_view, name='page_numbers'),

    # Document Signer (21 CFR Part 11)
    path('doc-signer/', views.doc_signer_view, name='doc_signer'),
    path('doc-signer/preview/', views.signer_preview_view, name='signer_preview'),
    path('doc-signer/sign/', views.sign_document_view, name='sign_document'),
    path('doc-signer/verify/<str:record_id>/', views.verify_signature_view, name='verify_signature'),

    # PDF Data Extractor (OCR-based)
    path('data-extractor/', views.data_extractor_view, name='data_extractor'),
    path('extract-data/', views.extract_data_view, name='extract_data'),

    # File download
    path('download/<str:filename>/', views.download_file, name='download'),
]
