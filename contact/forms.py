# forms.py
from django import forms
from .models import Contact


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "email", "message"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Your Name",
                    "required": True,
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "your.email@example.com",
                    "required": True,
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Tell us what you need help with...",
                    "rows": 5,
                    "required": True,
                }
            ),
        }
