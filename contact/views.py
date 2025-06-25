from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .forms import ContactForm
from .models import Contact
import json


# Create your views here.
@require_http_methods(["POST"])
def submit_contact(request):
    try:
        data = json.loads(request.body)
        form = ContactForm(data)

        if form.is_valid():
            contact = form.save()
            return JsonResponse(
                {
                    "success": True,
                    "message": "Thank you for your message! We'll get back to you soon.",
                }
            )
        else:
            return JsonResponse({"success": False, "errors": form.errors})
    except Exception as e:
        return JsonResponse(
            {"success": False, "message": "An error occurred. Please try again."}
        )
