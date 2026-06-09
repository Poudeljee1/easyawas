from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from listings.models import Property
from .models import Booking
from .forms import BookingForm
import stripe
from datetime import date

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def create_booking(request, property_pk):
    property = get_object_or_404(Property, pk=property_pk, is_available=True)

    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            check_in = form.cleaned_data['check_in']
            check_out = form.cleaned_data['check_out']
            guests = form.cleaned_data['guests']

            if check_in >= check_out:
                form.add_error('check_out', 'Check-out must be after check-in.')
            elif check_in < date.today():
                form.add_error('check_in', 'Check-in cannot be in the past.')
            elif guests > property.max_guests:
                form.add_error('guests', f'Max {property.max_guests} guests allowed.')
            else:
                nights = (check_out - check_in).days
                total = property.price_per_night * nights

                booking = Booking.objects.create(
                    property=property,
                    guest=request.user,
                    check_in=check_in,
                    check_out=check_out,
                    guests=guests,
                    total_price=total,
                    status='pending',
                )
                return redirect('booking_payment', pk=booking.pk)
    else:
        form = BookingForm()

    return render(request, 'bookings/create.html', {'form': form, 'property': property})


@login_required
def booking_payment(request, pk):
    booking = get_object_or_404(Booking, pk=pk, guest=request.user)

    if request.method == 'POST':
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(booking.total_price * 100),
                currency='usd',
                metadata={'booking_id': booking.pk},
            )
            booking.stripe_payment_intent = intent['id']
            booking.status = 'confirmed'
            booking.save()
            messages.success(request, 'Booking confirmed! Payment processed.')
            return redirect('my_bookings')
        except stripe.error.StripeError as e:
            messages.error(request, f'Payment failed: {e.user_message}')

    return render(request, 'bookings/payment.html', {
        'booking': booking,
        'stripe_key': settings.STRIPE_PUBLISHABLE_KEY,
    })


@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(guest=request.user).order_by('-created_at')
    return render(request, 'bookings/my_bookings.html', {'bookings': bookings})


@login_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, guest=request.user)
    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, 'Booking cancelled.')
        return redirect('my_bookings')
    return render(request, 'bookings/confirm_cancel.html', {'booking': booking})
