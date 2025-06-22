from django.db import models


class CachedVideo(models.Model):
    video_id = models.CharField(max_length=11, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    duration = models.CharField(max_length=20, null=True, blank=True)
    channel_name = models.CharField(max_length=255, null=True, blank=True)
    published_at = models.CharField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cached_videos"

    def __str__(self):
        return f"{self.title} ({self.video_id})"
