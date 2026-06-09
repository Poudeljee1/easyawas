from django import forms
from django.contrib.auth.models import User
from .models import Profile, SiteContent


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['photo', 'bio', 'phone', 'location']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tell renters about yourself...'}),
            'phone': forms.TextInput(attrs={'placeholder': '+91 98765 43210'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. Mumbai, India'}),
        }


class AccountForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last name'}),
            'email': forms.EmailInput(attrs={'placeholder': 'you@email.com'}),
        }


class SiteContentForm(forms.ModelForm):
    class Meta:
        model = SiteContent
        fields = ['value']
        widgets = {
            'value': forms.Textarea(attrs={'rows': 4}),
        }
