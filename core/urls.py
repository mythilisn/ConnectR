from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
# connectR/urls.py (Project-level)
from core import views as core_views # Assuming your views are in the core app
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Import your core app views for the AJAX endpoints


urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Existing path for the view_note_details page
    path('notes/<int:note_id>/details/', core_views.view_note_details, name='view_note_details'),
    
    # NEW: Endpoint for the AI Chatbot AJAX (as defined in previous step)
    path('chat/ask/', core_views.ask_chatbot_api, name='ask_chatbot'),
    
    # NEW: Endpoint for the Exam Generator
    path('notes/<int:note_id>/generate_exam/', core_views.generate_exam_view, name='generate_exam'),

    
    # Existing path for the view_note_details page
    path('notes/<int:note_id>/details/', core_views.view_note_details, name='view_note_details'),
    
    # NEW: Endpoint for the AI Chatbot AJAX
    path('chat/ask/', core_views.ask_chatbot_api, name='ask_chatbot'),
    
    # NEW: Endpoint for the Exam Generator
    path('notes/<int:note_id>/generate_exam/', core_views.generate_exam_view, name='generate_exam'),
    
    # Example path for viewing the generated exam
# /    path('exams/<int:note_id>/', core_views.view_generated_exam, name='view_exam'),
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('upload/', views.upload_note, name='upload'),
    path('delete/<int:file_id>/', views.delete_file, name='delete_file'),
    path('explore-notes/', views.explore_notes, name='explore_notes'),

    path('note/<int:note_id>/', views.note_detail, name='note_detail'),
    path('note/<int:note_id>/retag/', views.regenerate_tags, name='regenerate_tags'),
    path('note/<int:note_id>/resummary/', views.regenerate_summary, name='regenerate_summary'),

    path('report-note/<int:note_id>/', views.report_note, name='report_note'),
    path('rate/<int:note_id>/', views.rate_note, name='rate_note'),

    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    path('download/<int:note_id>/', views.download_note, name='download_note'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Password Reset URLs
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='password_reset_form.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='password_reset_complete.html'), name='password_reset_complete'),
    path('note/<int:note_id>/chatbot/', views.chatbot_api, name='chatbot_api'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
