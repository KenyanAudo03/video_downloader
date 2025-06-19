from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

class UserSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    
    def __str__(self):
        return f"Session {self.session_id}"

class VideoDownload(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    PLATFORM_CHOICES = [
        ('youtube', 'YouTube'),
        ('instagram', 'Instagram'),
        ('tiktok', 'TikTok'),
        ('twitter', 'Twitter'),
        ('facebook', 'Facebook'),
        ('vimeo', 'Vimeo'),
        ('other', 'Other'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(UserSession, on_delete=models.CASCADE)
    original_url = models.URLField()
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    title = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True)
    duration = models.CharField(max_length=20, blank=True)
    quality = models.CharField(max_length=20, default='best')
    file_size = models.BigIntegerField(null=True, blank=True)
    download_url = models.URLField(blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    download_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title or self.original_url} - {self.status}"