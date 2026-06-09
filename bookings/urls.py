from django.urls import path
from . import views

urlpatterns = [
    path('book/<int:property_pk>/', views.create_booking, name='create_booking'),
    path('payment/<int:pk>/', views.booking_payment, name='booking_payment'),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('cancel/<int:pk>/', views.cancel_booking, name='cancel_booking'),
]
