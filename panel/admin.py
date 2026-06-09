from django.contrib import admin
from .models import Profile, SiteContent

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'location']

@admin.register(SiteContent)
class SiteContentAdmin(admin.ModelAdmin):
    list_display = ['key', 'label', 'updated_by', 'updated_at']
