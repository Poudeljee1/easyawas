from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.contrib.auth.models import User
from listings.models import Property
from bookings.models import Booking
from .models import Profile, SiteContent
from .forms import ProfileForm, AccountForm, SiteContentForm


@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    my_listings = Property.objects.filter(host=request.user)
    my_bookings = Booking.objects.filter(guest=request.user).order_by('-created_at')[:5]
    total_earnings = sum(
        b.total_price for b in Booking.objects.filter(
            property__host=request.user, status='confirmed'
        )
    )
    return render(request, 'panel/dashboard.html', {
        'profile': profile,
        'my_listings': my_listings,
        'my_bookings': my_bookings,
        'total_earnings': total_earnings,
    })


@login_required
def edit_profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
        account_form = AccountForm(request.POST, instance=request.user)
        if profile_form.is_valid() and account_form.is_valid():
            profile_form.save()
            account_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('dashboard')
    else:
        profile_form = ProfileForm(instance=profile)
        account_form = AccountForm(instance=request.user)
    return render(request, 'panel/edit_profile.html', {
        'profile_form': profile_form,
        'account_form': account_form,
    })


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully!')
            return redirect('dashboard')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'panel/change_password.html', {'form': form})


@staff_member_required
def site_content(request):
    contents = SiteContent.objects.all().order_by('key')
    return render(request, 'panel/site_content.html', {'contents': contents})


@staff_member_required
def edit_content(request, pk):
    content = get_object_or_404(SiteContent, pk=pk)
    if request.method == 'POST':
        form = SiteContentForm(request.POST, instance=content)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, f'"{content.label}" updated!')
            return redirect('site_content')
    else:
        form = SiteContentForm(instance=content)
    return render(request, 'panel/edit_content.html', {'form': form, 'content': content})
