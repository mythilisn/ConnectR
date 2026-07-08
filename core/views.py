from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Note, Profile, Rating, Feedback
from .forms import CustomRegistrationForm, NoteForm
from django.http import FileResponse, Http404, JsonResponse
from django.db.models import Q, Count
import os
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
import json
from .ai import summarize_text, interpret_query
from connectR import settings

def home(request):
    notes = Note.objects.all().order_by('-uploaded_at')
    return render(request, 'core/home.html', {'notes': notes})




from .forms import CustomRegistrationForm

def register(request):
    if request.method == 'POST':
        form = CustomRegistrationForm(request.POST)
        if form.is_valid():
            form.save()  # Automatically validates and saves the user
            messages.success(request, 'Account created successfully. Please log in.')
            return redirect('login')
        else:
            # If the form is invalid, display the errors
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = CustomRegistrationForm()

    return render(request, 'core/register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password')
            return redirect('login')

    return render(request, 'core/login.html')

def user_logout(request):
    logout(request)
    return redirect('home')

from .forms import NoteForm
from .models import Note
from django.contrib.auth.decorators import login_required



@login_required
def upload_note(request):
    if request.method == 'POST':
        form = NoteForm(request.POST, request.FILES)
        if form.is_valid():
            note = form.save(commit=False)
            note.uploaded_by = request.user
            # First save to ensure file is on disk
            note.save()
            # Generate AI summary from content (non-blocking style best-effort)
            try:
                file_text = note.extract_text_from_file()
                # Fallback to title + description if file text isn't available
                if not file_text or len((file_text or '').strip()) < 5:
                    base_text = f"{note.title or ''}. {note.description or ''}"
                else:
                    base_text = file_text
                summary = summarize_text(base_text)
                if summary:
                    note.summary = summary
                    note.save()
            except Exception as e:
                print(f"Summary generation failed: {e}")
            messages.success(request, 'Note uploaded successfully!')
            return redirect('upload')  # Redirect to the upload page
    else:
        form = NoteForm()

    # Fetch all notes to display
    # notes = Note.objects.all()
    notes = Note.objects.filter(uploaded_by=request.user)
    return render(request, 'core/upload.html', {'form': form, 'notes': notes})


from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from .models import Note  # Use the correct model name

def delete_file(request, file_id):
    note = get_object_or_404(Note, id=file_id)  # Use the Note model
    note.delete()
    return redirect(reverse('home'))  # Redirect to the home page or another page


from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

class CustomRegistrationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, validators=[validate_password])
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise ValidationError("Passwords do not match.")
        return cleaned_data
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])  # This hashes the password
        if commit:
            user.save()
            print("User is_active:", user.is_active)
        return user


from django.shortcuts import render
from django.db.models import Q

# Define semester-to-subject mapping
SEMESTER_SUBJECTS = {
    "1": ["maths", "C programming", "Physics", "introduction to cyber security", "introduction to design thinking", "electronics and communication"],
    "2": ["maths", "C++", "Chemistry", "CAED", "Engineering Exploration", "Electrical Engineering"],
    "3": ["maths", "DSA", "Operating System", "DDCO", "EDC", "Python", "Java", "SCR"],
    "4": ["maths", "DBMS", "Unix", "IIOT", "DAA", "FSD"],
   
    # Add more semesters and their corresponding subjects here
}

def explore_notes(request):
    notes = Note.objects.all()

    # Get filter values from the request
    semester = request.GET.get('semester')
    subject = request.GET.get('subject')
    file_type = request.GET.get('file_type')
    uploaded_by = request.GET.get('uploaded_by')
    query = request.GET.get('q')
    tag = request.GET.get('tag')

    # Filter notes based on the selected semester
    if semester:
        notes = notes.filter(semester=semester)

    # Filter subjects dynamically based on the selected semester
    if semester and semester in SEMESTER_SUBJECTS:
        subjects = SEMESTER_SUBJECTS[semester]
    else:
        # Default to all subjects if no semester is selected
        subjects = Note.objects.values_list('subject', flat=True).distinct()

    # Apply additional filters
    if subject:
        notes = notes.filter(subject=subject)
    if file_type:
        notes = notes.filter(file__iendswith=file_type)
    if uploaded_by:
        notes = notes.filter(uploaded_by__username=uploaded_by)
    if tag:
        # Treat 'all' as no tag filter
        if tag.lower() != 'all':
            notes = notes.filter(tags__icontains=tag)
    if query:
        # Use AI to interpret the natural language query
        interpreted_keywords = interpret_query(query)
        # Normalize keywords: prefer comma-separated; fallback to splitting on newlines/whitespace
        keyword_list = []
        if interpreted_keywords:
            raw = interpreted_keywords
            raw = raw.replace('\n', ',')
            for ch in ['•', '-', '*', ';']:
                raw = raw.replace(ch, ',')
            raw_chunks = [c for c in raw.split(',') if c.strip()]
            keyword_list = [c.strip().strip('.:').strip() for c in raw_chunks if c.strip()]
        if not keyword_list:
            keyword_list = [query]

        query_filter = Q()
        for kw in keyword_list:
            query_filter |= (
                Q(subject__icontains=kw) |
                Q(description__icontains=kw) |
                Q(title__icontains=kw) |
                Q(tags__icontains=kw) |
                Q(summary__icontains=kw)
            )
        notes = notes.filter(query_filter)

    # Get popular tags
    all_tags = []
    for n in Note.objects.all():
        if n.tags:
            all_tags.extend([t.strip() for t in n.tags.split(',') if t.strip()])

    # Count unique tags (case-insensitive)
    tag_counts = {}
    for tg in all_tags:
        key = tg.lower().strip()
        if len(key) > 1:
            tag_counts[key] = tag_counts.get(key, 0) + 1

    popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
    # Prepend virtual 'all' tag
    total_notes = Note.objects.count()
    popular_tags = [('all', total_notes)] + popular_tags[:20]

    # Define all semesters explicitly
    semesters = ["1", "2", "3", "4", "5", "6", "7", "8"]

    # Get unique users for filters
    users = Note.objects.values_list('uploaded_by__username', flat=True).distinct()

    context = {
        'notes': notes,
        'subjects': subjects,
        'semesters': semesters,
        'users': users,
        'popular_tags': popular_tags,
        'active_tag': tag.lower() if tag else 'all',
    }
    
    return render(request, 'core/explore_notes.html', context)

@login_required
def note_detail(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    
    # Increase view count
    note.views += 1
    note.save()

    # Calculate average rating
    ratings = Rating.objects.filter(note=note)
    average_rating = round(sum(r.stars for r in ratings) / ratings.count(), 1) if ratings.exists() else None

    # Get related notes by the same author (if author is stored)
    related_notes = Note.objects.filter(uploaded_by=note.uploaded_by).exclude(id=note.id)[:4]
    
    # Compute content-only tags for detail page (do NOT alter saved tags)
    try:
        file_text = note.extract_text_from_file()
        content_tags = note.extract_keywords(file_text, num_keywords=12)
    except Exception as e:
        print(f"content tag generation error: {e}")
        content_tags = []

    return render(request, 'core/view_note.html', {
        'note': note,
        'average_rating': average_rating,
        'content_tags': content_tags,
        'related_notes': related_notes,
    })

@login_required
@require_POST
def regenerate_tags(request, note_id):
    """Regenerate tags for a specific note (auto-tagging)."""
    note = get_object_or_404(Note, id=note_id, uploaded_by=request.user)
    note.tags = ""
    note.generate_tags()
    note.save()
    messages.success(request, 'Tags regenerated successfully.')
    next_url = request.POST.get('next') or os.path.join('/', 'note', str(note.id))
    return redirect(next_url)

@login_required
@require_POST
def regenerate_summary(request, note_id):
    note = get_object_or_404(Note, id=note_id, uploaded_by=request.user)
    try:
        text = note.extract_text_from_file()
        if not text or len((text or '').strip()) < 5:
            text = f"{note.title or ''}. {note.description or ''}"
        summary = summarize_text(text)
        note.summary = summary or ''
        note.save()
        messages.success(request, 'Summary regenerated successfully.')
    except Exception as e:
        messages.error(request, f'Failed to regenerate summary: {e}')
    next_url = request.POST.get('next') or os.path.join('/', 'note', str(note.id))
    return redirect(next_url)

def download_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    note.downloads += 1
    note.save()
    file_path = note.file.path
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True)
    else:
        raise Http404("File not found")
    # Then serve the file for download

from django.contrib.auth.decorators import login_required
from .models import Note, Feedback

@login_required
def user_dashboard(request):
    user = request.user
    notes = Note.objects.filter(uploaded_by=user)
    
    total_uploads = notes.count()
    total_downloads = sum(note.downloads for note in notes)
    total_views = sum(note.views for note in notes)
    
    top_notes = notes.order_by('-views')[:5]
    
    # Streak (example: uploads in the last 7 days)
    from datetime import timedelta
    from django.utils import timezone
    last_week = timezone.now() - timedelta(days=7)
    weekly_uploads = notes.filter(upload_date__gte=last_week).count()
    
    context = {
        'total_uploads': total_uploads,
        'total_downloads': total_downloads,
        'total_views': total_views,
        'top_notes': top_notes,
        'weekly_uploads': weekly_uploads,
    }
    return render(request, 'core/user_dashboard.html', context)

from django.http import HttpResponse

def report_note(request, note_id):
    return HttpResponse("Report feature coming soon!")

from .models import Note, Rating
from django.urls import reverse
@login_required
def rate_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    if request.method == 'POST':
        stars = int(request.POST.get('rating'))
        existing_rating = Rating.objects.filter(note=note, user=request.user).first()
        if existing_rating:
            existing_rating.stars = stars
            existing_rating.save()
        else:
            Rating.objects.create(note=note, user=request.user, stars=stars)
    return redirect('note_detail', note_id=note.pk)

def view_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    ratings = Rating.objects.filter(note=note)
    average_rating = round(sum(r.stars for r in ratings) / ratings.count(), 1) if ratings.exists() else None
    related_notes = Note.objects.filter(author=note.author).exclude(id=note.id)[:4]
    return render(request, 'view_note.html', {
        'note': note,
        'related_notes': related_notes,
        'average_rating': average_rating
    })

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .forms import ProfileForm

@login_required
def edit_profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('edit_profile')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'core/edit_profile.html', {'form': form})
from django.shortcuts import render
from django.http import JsonResponse
# In core/views.py (line 389)
from core.services.ai_services import AIService
# You'll need models for Note and Exam, but we'll focus on the AI call.

def view_note_details(request, note_id):
    """Renders the page with the 'Ask Chatbot' and 'Generate Exam' buttons."""
    # Logic to fetch Note details and its associated PDF path
    # e.g., note = Note.objects.get(id=note_id)
    # The PDF path is typically stored as a field on the Note model (e.g., note.pdf_file.path)
    context = {
        'note_id': note_id,
        'pdf_path': '/path/to/media/notes/your_note.pdf', # Placeholder path
        # ... other note details
    }
    return render(request, 'core/view_note.html', context)

# --- Feature 1: AJAX Endpoint for Chatbot ---
# core/views.py

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
import json

# IMPORTANT: Import your Note model and AIService
# ASSUMPTION: Note model is in core.models
from core.models import Note
# ASSUMPTION: AIService is in core.services.ai_services
from core.services.ai_services import AIService 


# core/views.py

from django.http import JsonResponse
import json
from django.shortcuts import get_object_or_404
from core.models import Note  # Assuming Note is here
from .services.ai_services import AIService # Import your service class

def chatbot_api(request, note_id):
    """
    Handles chat requests by fetching the note, initializing the AIService,  and calling the send_chat_message method."""
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message')
            
            if not user_message:
                return JsonResponse({'error': 'Message field is required.'}, status=400)
            
            # 1. Fetch the Note object
            # Use get_object_or_404 if you want Django to handle the 404 (if the note doesn't exist)
            note = get_object_or_404(Note, id=note_id) 

            # ASSUMPTION: The file field on your Note model is called 'pdf_file' or 'uploaded_file'.
            # CHECK YOUR MODEL AND ADJUST THIS LINE IF NEEDED.
            # Using the actual file path stored in the model field:
            pdf_path = note.file.path 


            # >>> TEMPORARY DEBUGGING STEP <<<
            import os
            print("-" * 50)
            print(f"Attempting to read file at path: {pdf_path}")
            print(f"File exists: {os.path.exists(pdf_path)}")
            print("-" * 50)
            # >>> END TEMPORARY DEBUGGING STEP <<<
            
            # 2. Instantiate the AIService with the required parameters
            ai_service = AIService(note_id=note_id, pdf_path=pdf_path) 
            
            # 3. Call the chat method
            ai_response = ai_service.send_chat_message(user_message=user_message)

            return JsonResponse({'response': ai_response})

        except ValueError as e:
            # Catch custom errors raised by AIService (e.g., APIError, file error)
            return JsonResponse({'error': str(e)}, status=500)
        
        except Exception as e:
            # Catch all unexpected errors (e.g., Note.DoesNotExist if not using get_object_or_404)
            print(f"Chatbot API Critical Error: {e}")
            return JsonResponse({'error': 'An unexpected server error occurred.'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method.'}, status=405)



#gerate Exam Endpoint ---
def generate_exam_view(request, note_id):
    # This should be a POST request to prevent accidental generation/billing
    if request.method == 'POST':
        try:
            # 1. Get the local path of the PDF
            pdf_path = f'/path/to/media/notes/{note_id}.pdf' # Fetch from DB
            
            # 2. Call the service layer
            ai_service = AIService(note_id)
            exam_json_string = ai_service.generate_exam(pdf_path)
            
            # 3. Save the result (You would save this to your Exam/Question models)
            # exam_data = json.loads(exam_json_string)
            # Exam.objects.create_from_json(exam_data, note_id) 
            
            return JsonResponse({'status': 'success', 'message': 'Exam generated and saved!', 'exam_data': exam_json_string})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    # Redirect the user to the exam page or return the initial view
    return render(request, 'core/view_note.html', {'note_id': note_id})
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.shortcuts import render
import json

# MOCK DATA/FUNCTION (Replace with your actual Django model logic)
def get_note_pdf_path(note_id):
    """Mocks fetching the PDF path from a Note model."""
    # TODO: Replace with: return Note.objects.get(id=note_id).pdf_file.path
    # This assumes your PDF files are stored in your project's MEDIA_ROOT.
    return os.path.join(settings.BASE_DIR, 'media', 'notes', f'note_{note_id}.pdf')

def save_exam_to_db(note_id, exam_data):
    """Mocks saving the generated exam structure to the database."""
    # TODO: Implement actual saving logic to your Exam/Question models.
    print(f"Successfully saved {len(exam_data)} questions for Note ID: {note_id}")
    # Example: Exam.objects.create(note_id=note_id, json_data=json.dumps(exam_data))
    pass
# END MOCK

def view_note_details(request, note_id):
    """Renders the page with the Chatbot/Exam buttons."""
    context = {
        'note_id': note_id,
        # ... other context data
    }
    return render(request, 'core/view_note.html', context)

# --- Feature 1: AI Chatbot API ---
@require_POST
def ask_chatbot_api(request):
    """Handles the AJAX chat messages."""
    note_id = request.POST.get('note_id')
    user_message = request.POST.get('message')

    if not all([note_id, user_message]):
        return JsonResponse({'error': 'Missing note ID or message.'}, status=400)

    try:
        pdf_path = get_note_pdf_path(note_id)
        
        # Instantiate the service
        ai_service = AIService(note_id, pdf_path)
        
        # Get response from Gemini
        response_text = ai_service.send_chat_message(user_message)
        
        return JsonResponse({'response': response_text})
        
    except FileNotFoundError:
        return JsonResponse({'error': 'PDF file not found for this note.'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=503)
    except Exception as e:
        return JsonResponse({'error': 'An unexpected server error occurred.'}, status=500)


# --- Feature 2: Generate Exam View ---
@require_POST
def generate_exam_view(request, note_id):
    """Triggers the exam generation process."""
    try:
        pdf_path = get_note_pdf_path(note_id)
        
        # 1. Call the service layer
        ai_service = AIService(note_id, pdf_path)
        exam_json_string = ai_service.generate_exam()
        
        # 2. Parse and save the result
        exam_data = json.loads(exam_json_string)
        save_exam_to_db(note_id, exam_data)
        
        return JsonResponse({'status': 'success', 'message': 'Exam generated and saved successfully!'})
            
    except FileNotFoundError:
        return JsonResponse({'status': 'error', 'message': 'PDF file not found. Cannot generate exam.'}, status=404)
    except ValueError as e:
        # Catches API errors from the service layer
        return JsonResponse({'status': 'error', 'message': str(e)}, status=503)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'AI generated malformed data. Try again.'}, status=500)
    except Exception as e:
        print(f"Exception during exam generation: {e}")
        return JsonResponse({'status': 'error', 'message': 'An unexpected server error occurred.'}, status=500)

# MOCK DATA/FUNCTION (Replace with your actual Django model logic)
def get_note_pdf_path(note_id):
    """
    Mocks fetching the absolute PDF path from a Note model
    based on the MEDIA_ROOT configuration.
    
    NOTE: In a real application, you would use:
    return Note.objects.get(id=note_id).pdf_file.path
    """
    
    # 1. Define the relative file path structure within MEDIA_ROOT
    # Our file is stored in a 'notes' subfolder and is named 'note_[id].pdf'
    relative_path_segments = ['notes', f'note_{note_id}.pdf']
    
    # 2. Use os.path.join to combine MEDIA_ROOT with the file path.
    # os.path.join is platform-independent (uses / on Linux/Mac and \ on Windows).
    full_path = os.path.join(
        settings.MEDIA_ROOT,
        *relative_path_segments # Unpack the list of path segments
    )

    # In development, it's useful to print the generated path for verification:
    print(f"--- DEBUG: Attempting to access PDF at: {full_path} ---") 
    
    return full_path

# END MOCK