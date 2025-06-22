# models.py
from django.db import models
from django.utils import timezone


class PlayedVideo(models.Model):
    video_id = models.CharField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=500)
    channel = models.CharField(max_length=200, blank=True, null=True)
    play_count = models.PositiveIntegerField(default=0)
    first_played = models.DateTimeField(auto_now_add=True)
    last_played = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_played"]
        indexes = [
            models.Index(fields=["video_id"]),
            models.Index(fields=["-play_count"]),
            models.Index(fields=["-last_played"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.play_count} plays)"

    @classmethod
    def increment_play_count(cls, video_id, title, channel=None):
        """
        Increment play count for a video, or create new entry if doesn't exist
        """
        video, created = cls.objects.get_or_create(
            video_id=video_id,
            defaults={
                "title": title,
                "channel": channel or "Unknown Channel",
                "play_count": 1,
            },
        )

        if not created:
            # Update existing record
            video.play_count += 1
            video.last_played = timezone.now()
            # Update title and channel in case they've changed
            video.title = title
            if channel:
                video.channel = channel
            video.save(update_fields=["play_count", "last_played", "title", "channel"])

        return video
