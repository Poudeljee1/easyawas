from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('change-password/', views.change_password, name='change_password'),
    path('site-content/', views.site_content, name='site_content'),
    path('site-content/<int:pk>/edit/', views.edit_content, name='edit_content'),
]
