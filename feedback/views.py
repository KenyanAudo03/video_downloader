# views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.conf import settings
import json
import base64
import uuid
from .models import Feedback

def get_client_ip(request):
    """Get the client's IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@csrf_exempt
@require_http_methods(["POST"])
def submit_feedback(request):
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        description = data.get('description', '').strip()
        if not description:
            return JsonResponse({
                'success': False, 
                'error': 'Description is required'
            }, status=400)
        
        # Create feedback instance
        feedback = Feedback(
            description=description,
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            page_url=data.get('page_url', ''),
            ip_address=get_client_ip(request)
        )
        
        # Handle screenshot if provided
        screenshot_data = data.get('screenshot')
        if screenshot_data:
            try:
                # Remove data URL prefix
                if screenshot_data.startswith('data:image/png;base64,'):
                    screenshot_data = screenshot_data.replace('data:image/png;base64,', '')
                
                # Decode base64 image
                image_data = base64.b64decode(screenshot_data)
                
                # Create filename
                filename = f'feedback_screenshot_{uuid.uuid4().hex[:8]}.png'
                
                # Save image
                feedback.screenshot.save(
                    filename,
                    ContentFile(image_data),
                    save=False
                )
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid screenshot data: {str(e)}'
                }, status=400)
        
        feedback.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Feedback submitted successfully!',
            'feedback_id': str(feedback.id)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }, status=500)