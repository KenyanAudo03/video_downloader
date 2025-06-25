from django.contrib import admin
from django.utils.html import format_html
from .models import Feedback
from django.utils.timezone import localtime


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = [
        "short_id",
        "short_description_display",
        "formatted_created_at",
        "colored_screenshot_status",
        "colored_resolution_status",
    ]
    list_filter = ["is_resolved", "created_at"]
    search_fields = ["description", "page_url", "ip_address"]
    list_per_page = 25

    readonly_fields = [
        "id",
        "description",
        "formatted_created_at",
        "page_url",
        "screenshot",
        "screenshot_preview",
        "user_agent",
        "ip_address",
        "short_description_display",
        "colored_screenshot_status",
        "colored_resolution_status",
    ]

    def short_id(self, obj):
        return str(obj.id)[:5]

    short_id.short_description = "ID"

    def short_description_display(self, obj):
        short = (
            obj.description[:10] + "..."
            if len(obj.description) > 10
            else obj.description
        )
        return format_html('<div title="{}">{}</div>', obj.description, short)

    short_description_display.short_description = "Description"

    def formatted_created_at(self, obj):
        return localtime(obj.created_at).strftime("%B %d, %Y %H:%M")

    formatted_created_at.short_description = "Created At"

    def colored_screenshot_status(self, obj):
        if obj.screenshot:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Screenshot</span>'
            )
        return format_html('<span style="color: #999;">No Screenshot</span>')

    colored_screenshot_status.short_description = "Screenshot?"

    def colored_resolution_status(self, obj):
        color = "green" if obj.is_resolved else "red"
        label = "Resolved" if obj.is_resolved else "Unresolved"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>', color, label
        )

    colored_resolution_status.short_description = "Status"

    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(
                '<img src="{}" style="border: 2px solid #eee; border-radius: 6px; max-width: 100%; max-height: 300px;" />',
                obj.screenshot.url,
            )
        return format_html('<span style="color: #999;">No screenshot available</span>')

    screenshot_preview.short_description = "Screenshot Preview"

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if object_id:
            try:
                feedback = Feedback.objects.get(pk=object_id)
                if not feedback.is_resolved:
                    feedback.is_resolved = True
                    feedback.save()
            except Feedback.DoesNotExist:
                pass
        return super().changeform_view(request, object_id, form_url, extra_context)

    fieldsets = (
        (
            "Feedback Overview",
            {
                "fields": (
                    "formatted_created_at",
                    "page_url",
                    "screenshot_preview",
                    "description",
                )
            },
        ),
    )

    actions = []
