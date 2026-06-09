from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Property
from .forms import PropertyForm


def home(request):
    properties = Property.objects.filter(is_available=True)
    cities = Property.objects.values_list('city', flat=True).distinct()

    q = request.GET.get('q', '')
    city = request.GET.get('city', '')
    prop_type = request.GET.get('type', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')

    if q:
        properties = properties.filter(title__icontains=q) | properties.filter(location__icontains=q)
    if city:
        properties = properties.filter(city__iexact=city)
    if prop_type:
        properties = properties.filter(property_type=prop_type)
    if min_price:
        properties = properties.filter(price_per_night__gte=min_price)
    if max_price:
        properties = properties.filter(price_per_night__lte=max_price)

    return render(request, 'listings/home.html', {
        'properties': properties,
        'cities': cities,
        'property_types': Property.PROPERTY_TYPES,
    })


def property_detail(request, pk):
    property = get_object_or_404(Property, pk=pk)
    return render(request, 'listings/detail.html', {'property': property})


@login_required
def my_listings(request):
    properties = Property.objects.filter(host=request.user)
    return render(request, 'listings/my_listings.html', {'properties': properties})


@login_required
def create_listing(request):
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES)
        if form.is_valid():
            prop = form.save(commit=False)
            prop.host = request.user
            prop.save()
            messages.success(request, 'Listing created successfully!')
            return redirect('property_detail', pk=prop.pk)
    else:
        form = PropertyForm()
    return render(request, 'listings/form.html', {'form': form, 'action': 'Create'})


@login_required
def edit_listing(request, pk):
    property = get_object_or_404(Property, pk=pk, host=request.user)
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, instance=property)
        if form.is_valid():
            form.save()
            messages.success(request, 'Listing updated!')
            return redirect('property_detail', pk=property.pk)
    else:
        form = PropertyForm(instance=property)
    return render(request, 'listings/form.html', {'form': form, 'action': 'Edit'})


@login_required
def delete_listing(request, pk):
    property = get_object_or_404(Property, pk=pk, host=request.user)
    if request.method == 'POST':
        property.delete()
        messages.success(request, 'Listing deleted.')
        return redirect('my_listings')
    return render(request, 'listings/confirm_delete.html', {'property': property})
