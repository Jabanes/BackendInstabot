from django.contrib import admin
from .firebase_stores import NonFollowerStore

class NonFollowerAdmin(admin.ModelAdmin):
    list_display = ("user", "username")
    search_fields = ("username", "user__username")
    list_filter = ("user",)

# admin.site.register(NonFollowerStore, NonFollowerAdmin)