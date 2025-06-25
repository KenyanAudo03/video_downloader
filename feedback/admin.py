from django.contrib import admin
from django.utils.html import format_html
from .models import Feedback


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "short_description_display",
        "colored_screenshot_status",
        "page_url",
        "created_at",
        "colored_resolution_status",
    ]
    list_filter = ["is_resolved", "created_at"]
    search_fields = ["description", "page_url", "ip_address"]
    list_per_page = 25

    readonly_fields = [
        "id",
        "created_at",
        "user_agent",
        "page_url",
        "ip_address",
        "description",
        "screenshot",
        "screenshot_preview",
        "short_description_display",
        "colored_screenshot_status",
        "colored_resolution_status",
    ]

    fieldsets = (
        (
            "📝 Feedback Details",
            {
                "fields": (
                    "id",
                    "short_description_display",
                    "description",
                    "created_at",
                    "page_url",
                )
            },
        ),
        (
            "🖼 Screenshot (if available)",
            {
                "fields": ("screenshot", "screenshot_preview"),
                "classes": ("collapse",),
            },
        ),
        (
            "⚙️ Technical Info",
            {
                "fields": ("user_agent", "ip_address"),
                "classes": ("collapse",),
            },
        ),
    )

    def short_description_display(self, obj):
        return format_html(
            '<div title="{desc}">{short}</div>',
            desc=obj.description,
            short=obj.short_description,
        )

    short_description_display.short_description = "Short Description"

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

    actions = []
