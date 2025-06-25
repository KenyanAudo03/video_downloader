# models.py
from django.db import models
from django.utils import timezone
import uuid

class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.TextField(help_text="User's feedback description")
    screenshot = models.ImageField(upload_to='feedback_screenshots/', blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True, help_text="Browser information")
    page_url = models.URLField(blank=True, null=True, help_text="Page where feedback was submitted")
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    is_resolved = models.BooleanField(default=False)
    admin_notes = models.TextField(blank=True, help_text="Internal notes for admin")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Feedback"
        verbose_name_plural = "Feedback"
    
    def __str__(self):
        return f"Feedback {self.id} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def short_description(self):
        return self.description[:100] + "..." if len(self.description) > 100 else self.description