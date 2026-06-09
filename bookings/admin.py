from django.contrib import admin
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['property', 'guest', 'check_in', 'check_out', 'total_price', 'status']
    list_filter = ['status']
