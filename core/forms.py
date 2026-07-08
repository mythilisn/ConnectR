# from django import forms
# from .models import Note

# class NoteForm(forms.ModelForm):
#     class Meta:
#         model = Note
#         fields = ['title', 'description', 'subject', 'file']

from django import forms
from .models import Note

class NoteForm(forms.ModelForm):
    class Meta:
        model = Note
        fields = ['title', 'description', 'subject', 'semester', 'file']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter description'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter subject'}),
            'semester': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter semester'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_semester(self):
        semester = self.cleaned_data.get('semester')
        valid_semesters = ["1", "2", "3", "4", "5", "6", "7", "8"]
        if semester not in valid_semesters:
            raise forms.ValidationError("Please enter a valid semester (1-8).")
        return semester

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
    

from .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['image', 'bio']