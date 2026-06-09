from django.contrib import admin
from .models import Property

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['title', 'property_type', 'city', 'price_per_night', 'is_available', 'host']
    list_filter = ['property_type', 'is_available', 'city']
    search_fields = ['title', 'location', 'city']
