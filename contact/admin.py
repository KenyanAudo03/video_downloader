from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Contact
from django.utils.formats import date_format

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = [
        "name_preview",
        "email_preview",
        "formatted_created_at",
        "is_read",
        "message_preview",
    ]
    list_filter = ["is_read", "created_at"]
    search_fields = ["name", "email", "message"]
    readonly_fields = ["name", "email", "created_at_formatted", "message", "is_read"]
    list_per_page = 20
    actions = ["mark_as_read", "mark_as_unread"]

    def formatted_created_at(self, obj):
        return obj.created_at.strftime("%B %d, %Y %H:%M")

    formatted_created_at.short_description = "Created At"

    # For readonly detail view
    def created_at_formatted(self, obj):
        return obj.created_at.strftime("%B %d, %Y %H:%M")

    created_at_formatted.short_description = "Created At"

    def message_preview(self, obj):
        return obj.message[:10] + "..." if len(obj.message) > 10 else obj.message

    message_preview.short_description = "Message Preview"

    def name_preview(self, obj):
        return obj.name[:7] + "..." if len(obj.name) > 7 else obj.name

    name_preview.short_description = "Name Preview"

    def email_preview(self, obj):
        return obj.email[:10] + "..." if len(obj.email) > 10 else obj.email

    email_preview.short_description = "Email Preview"

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)

    mark_as_read.short_description = "Mark selected messages as read"

    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False)

    mark_as_unread.short_description = "Mark selected messages as unread"

    fieldsets = (
        ("Contact Information", {
            "fields": ("name", "email", "created_at_formatted", "message", "is_read")
        }),
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    def has_view_permission(self, request, obj=None):
        return True

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Override to mark message as read when opened"""
        if object_id:
            try:
                contact = Contact.objects.get(pk=object_id)
                if not contact.is_read:
                    contact.is_read = True
                    contact.save()
            except Contact.DoesNotExist:
                pass
        return super().changeform_view(request, object_id, form_url, extra_context)
