

# class Note(models.Model):
#     SUBJECT_CHOICES = [
#         ('maths', 'Mathematics'),
#         ('physics', 'Physics'),
#         ('cs', 'Computer Science'),
#         ('other', 'Other'),
#     ]

#     title = models.CharField(max_length=255)
#     description = models.TextField(blank=True)
#     subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES)
#     file = models.FileField(upload_to='notes/')
#     uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     uploaded_at = models.DateTimeField(auto_now_add=True)


# from django.db import models
# from django.contrib.auth.models import User

# class Note(models.Model):
#     SUBJECT_CHOICES = [
#         ('maths', 'Mathematics'),
#         ('physics', 'Physics'),
#         ('cs', 'Computer Science'),
#         ('other', 'Other'),
#     ]
#     from django.db import models
# from django.contrib.auth.models import User

# class Note(models.Model):
#     title = models.CharField(max_length=255)
#     description = models.TextField(blank=True)
#     subject = models.CharField(max_length=100)  # Allow users to type the subject
#     semester = models.CharField(max_length=50)  # Add semester field
#     file = models.FileField(upload_to='notes/')
#     uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
#     uploaded_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.title


from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from PIL import Image
import PyPDF2
import docx2txt
from pptx import Presentation
from rake_nltk import Rake
import nltk
from nltk.corpus import stopwords
from collections import Counter
import string
import os
import re
import tempfile
from django.core.files.storage import default_storage
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdf2image import convert_from_path
import pytesseract

# Lazy-initialized KeyBERT model holder
_KB_MODEL = None

def _get_keybert_model():
    global _KB_MODEL
    if _KB_MODEL is not None:
        return _KB_MODEL
    try:
        # Import here to avoid heavy import at startup if unused
        from keybert import KeyBERT
        from sentence_transformers import SentenceTransformer
        # Use a lightweight model and force CPU to avoid device/meta tensor issues
        st_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
        _KB_MODEL = KeyBERT(model=st_model)
        return _KB_MODEL
    except Exception as e:
        print(f"KeyBERT init failed (will fallback): {e}")
        _KB_MODEL = None
        return None

# Ensure required NLTK data is available (safe for dev)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    # Newer NLTK versions split resources into punkt_tab
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    try:
        nltk.download('punkt_tab')
    except Exception:
        # Not available on older versions; ignore
        pass
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')

class Note(models.Model):
    SUBJECT_CHOICES = [
        ('maths', 'Mathematics'),
        ('physics', 'Physics'),
        ('cs', 'Computer Science'),
        ('other', 'Other'),
    ]
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    subject = models.CharField(max_length=100)  # Or use choices=SUBJECT_CHOICES
    semester = models.CharField(max_length=50)
    file = models.FileField(upload_to='notes/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    views = models.PositiveIntegerField(default=0)
    downloads = models.PositiveIntegerField(default=0)
    upload_date = models.DateTimeField(default=timezone.now)
    tags = models.TextField(blank=True, help_text="Comma-separated tags/keywords")
    summary = models.TextField(blank=True, help_text="AI-generated brief summary of the note content")
    
    def __str__(self):
        return self.title
        
    def extract_text_from_file(self):
        """Extract text from different file types using safe fallbacks.
        Tries absolute path first; if missing, uses Django storage or temp files.
        """
        if not self.file:
            return ""
        file_extension = os.path.splitext(self.file.name)[1].lower().lstrip('.')
        text = ""
        try:
            file_path = getattr(self.file, 'path', None)
            path_exists = file_path and os.path.exists(file_path)

            # Helper: open through storage if path missing
            def open_from_storage(mode='rb'):
                return default_storage.open(self.file.name, mode)

            if file_extension == 'pdf':
                if path_exists:
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        text = "\n".join([page.extract_text() or "" for page in reader.pages])
                else:
                    try:
                        with open_from_storage('rb') as f:
                            reader = PyPDF2.PdfReader(f)
                            text = "\n".join([page.extract_text() or "" for page in reader.pages])
                    except Exception:
                        text = ""
                # Fallback to pdfminer if PyPDF2 yields little or no text
                if not text or len(text.strip()) < 10:
                    try:
                        if path_exists:
                            text = pdfminer_extract_text(file_path) or ""
                        else:
                            # dump to temp and use pdfminer
                            with open_from_storage('rb') as fsrc, tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                                tmp.write(fsrc.read())
                                tmp_path = tmp.name
                            try:
                                text = pdfminer_extract_text(tmp_path) or ""
                            finally:
                                os.unlink(tmp_path)
                    except Exception as e:
                        print(f"pdfminer fallback failed: {e}")

                # Final fallback: OCR via Tesseract if still no text
                if (not text or len(text.strip()) < 10):
                    try:
                        # Configure Tesseract path on Windows if provided
                        tess_cmd = os.getenv('TESSERACT_CMD')
                        if tess_cmd:
                            pytesseract.pytesseract.tesseract_cmd = tess_cmd
                        # Prepare a real path for pdf2image
                        effective_path = file_path
                        clean_tmp = False
                        if not path_exists:
                            with open_from_storage('rb') as fsrc, tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                                tmp.write(fsrc.read())
                                effective_path = tmp.name
                                clean_tmp = True
                        # Convert a limited number of pages for performance
                        poppler_path = os.getenv('POPPLER_PATH') or None
                        images = convert_from_path(effective_path, dpi=200, poppler_path=poppler_path)
                        ocr_texts = []
                        max_pages = 5
                        for idx, img in enumerate(images):
                            if idx >= max_pages:
                                break
                            ocr_texts.append(pytesseract.image_to_string(img))
                        text = "\n".join(ocr_texts)
                        if clean_tmp and effective_path and os.path.exists(effective_path):
                            os.unlink(effective_path)
                    except Exception as e:
                        print(f"OCR fallback failed: {e}")

            elif file_extension in ['docx']:
                if path_exists:
                    text = docx2txt.process(file_path) or ""
                else:
                    # Write to temp file then process
                    try:
                        with open_from_storage('rb') as fsrc, tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp:
                            tmp.write(fsrc.read())
                            tmp_path = tmp.name
                        try:
                            text = docx2txt.process(tmp_path) or ""
                        finally:
                            os.unlink(tmp_path)
                    except Exception:
                        text = ""

            elif file_extension in ['pptx']:
                if path_exists:
                    prs = Presentation(file_path)
                else:
                    # Write to temp and open
                    try:
                        with open_from_storage('rb') as fsrc, tempfile.NamedTemporaryFile(delete=False, suffix='.pptx') as tmp:
                            tmp.write(fsrc.read())
                            tmp_path = tmp.name
                        prs = Presentation(tmp_path)
                        os.unlink(tmp_path)
                    except Exception as e:
                        print(f"Error reading PPTX: {e}")
                        prs = None
                if prs:
                    parts = []
                    for slide in prs.slides:
                        for shape in slide.shapes:
                            if hasattr(shape, 'text') and shape.text:
                                parts.append(shape.text)
                    text = "\n".join(parts)

            elif file_extension in ['txt']:
                if path_exists:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text = f.read()
                else:
                    try:
                        with open_from_storage('r') as f:
                            text = f.read()
                    except Exception:
                        # Fallback for in-memory file
                        try:
                            self.file.seek(0)
                            text = self.file.read().decode('utf-8', errors='ignore')
                        except Exception:
                            text = ""
        except Exception as e:
            # Log and continue; don't break save
            print(f"Error extracting text: {e}")
        return text
    
    def extract_keywords(self, text, num_keywords=12):
        """Extract keywords using KeyBERT (phrases), RAKE (phrases), and regex unigrams.
        Returns up to num_keywords unique, quality tags.
        """
        if not text:
            return []

        candidates: list[str] = []

        # 1) KeyBERT for high-quality phrases
        try:
            kb = _get_keybert_model()
            if kb is not None:
                kb_kw = kb.extract_keywords(
                    text,
                    keyphrase_ngram_range=(1, 3),
                    stop_words='english',
                    top_n=max(num_keywords * 2, 15)
                )
                # kb_kw is list of tuples [(phrase, score), ...]
                candidates.extend([p for p, _ in kb_kw])
        except Exception as e:
            print(f"KeyBERT extraction failed (continuing): {e}")

        # 2) RAKE phrases
        try:
            rake = Rake(language='english', min_length=1, max_length=3)
            rake.extract_keywords_from_text(text)
            ranked_phrases = rake.get_ranked_phrases()
            candidates.extend(ranked_phrases[: max(num_keywords * 2, 20)])
        except Exception as e:
            print(f"RAKE error: {e}")

        # 3) Frequency-based unigrams from regex tokens (no punkt dependency)
        tokens = re.findall(r"[A-Za-z0-9]+", text.lower())
        try:
            stop_words = set(stopwords.words('english'))
        except LookupError:
            # Fallback: minimal stop set if NLTK stopwords missing
            stop_words = {"the","a","an","and","or","is","are","to","in","of","for","on","with","by","as","at","from","this","that","it"}
        words = [w for w in tokens if w not in stop_words and len(w) > 2]
        freq = Counter(words)
        candidates.extend([w for w, _ in freq.most_common(num_keywords * 2)])

        # Normalize, de-duplicate while preserving order, strip punctuation
        normalized = []
        seen = set()
        for c in candidates:
            c = (c or '').strip().lower()
            c = re.sub(r"\s+", " ", c)
            c = c.strip(string.punctuation + ' ')
            if not c:
                continue
            if c not in seen:
                seen.add(c)
                normalized.append(c)

        return normalized[:num_keywords]
    
    def generate_tags(self):
        """Generate and set tags from title, description, subject, semester and file content."""
        base_text = f"{self.title or ''} {self.description or ''}"
        file_text = self.extract_text_from_file()
        keywords = self.extract_keywords(f"{base_text} {file_text}")
        additional = [str(self.subject).lower()] if self.subject else []
        if self.semester:
            additional.append(f"sem{self.semester}")
        # De-duplicate while preserving order
        seen = set()
        all_tags = []
        for t in keywords + additional:
            t = (t or '').strip().lower()
            if t and t not in seen:
                seen.add(t)
                all_tags.append(t)
        self.tags = ", ".join(all_tags)

    def save(self, *args, **kwargs):
        # Regenerate tags if empty or if key fields changed
        should_regenerate = not self.tags
        if self.pk:
            try:
                old = Note.objects.get(pk=self.pk)
                if (
                    old.title != self.title or
                    old.description != self.description or
                    old.subject != self.subject or
                    old.semester != self.semester or
                    old.file != self.file
                ):
                    should_regenerate = True
            except Note.DoesNotExist:
                should_regenerate = True
        if should_regenerate:
            self.generate_tags()
        super().save(*args, **kwargs)

    def get_tag_list(self):
        """Return tags as a list for templates."""
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(',') if t.strip()]

class Feedback(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(default=1)  # 1 to 5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Rating(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stars = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    image = models.ImageField(upload_to='profile_images/', default='profile_images/default-profile.png')
    bio = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            if self.image and hasattr(self.image, 'path'):
                img = Image.open(self.image.path)
                if img.height > 300 or img.width > 300:
                    output_size = (300, 300)
                    img.thumbnail(output_size)
                    img.save(self.image.path)
        except Exception as e:
            print(f"Error processing image: {e}")

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Ensure profile exists
    Profile.objects.get_or_create(user=instance)
    instance.profile.save()
