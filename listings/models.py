from django.db import models
from django.contrib.auth.models import User


class Property(models.Model):
    PROPERTY_TYPES = [
        ('room', 'Room'),
        ('apartment', 'Apartment'),
        ('house', 'House'),
    ]

    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='properties')
    title = models.CharField(max_length=200)
    description = models.TextField()
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    location = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    price_per_night = models.DecimalField(max_digits=8, decimal_places=2)
    bedrooms = models.PositiveIntegerField(default=1)
    bathrooms = models.PositiveIntegerField(default=1)
    max_guests = models.PositiveIntegerField(default=2)
    image = models.ImageField(upload_to='properties/', blank=True, null=True)
    is_available = models.BooleanField(default=True)
    amenities = models.TextField(blank=True, help_text='Comma-separated: WiFi, Parking, AC')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Properties'

    def __str__(self):
        return self.title

    def amenities_list(self):
        return [a.strip() for a in self.amenities.split(',') if a.strip()]
