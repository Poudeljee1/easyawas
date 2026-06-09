from django import forms
from .models import Property


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        exclude = ['host', 'created_at']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'amenities': forms.TextInput(attrs={'placeholder': 'WiFi, Parking, AC, Pool'}),
        }
