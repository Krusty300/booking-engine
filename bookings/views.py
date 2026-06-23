from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta
from .models import Resource, Booking, Category, UserProfile
from .services import BookingService
from .forms import SignUpForm, ResourceForm, ResourceStatusForm, CategoryForm, UserProfileForm, UserSettingsForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

# ============ AUTHENTICATION VIEWS ============

def signup(request):
    """User registration view"""
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Account created successfully! Welcome {user.username}!")
            return redirect('resource_list')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SignUpForm()
    
    return render(request, 'registration/signup.html', {'form': form})

# ============ RESOURCE LISTING AND BOOKING VIEWS ============

@login_required
def resource_list(request):
    """List all available resources with category filtering"""
    # Get all categories for the filter
    categories = Category.objects.all().order_by('name')
    
    # Get filter parameters
    category_filter = request.GET.get('category', 'all')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    if request.user.is_staff:
        resources = Resource.objects.all().order_by('-created_at')
    else:
        resources = Resource.objects.filter(status='APPROVED').order_by('-created_at')
    
    # Apply category filter
    if category_filter != 'all' and category_filter:
        try:
            category = Category.objects.get(slug=category_filter)
            resources = resources.filter(category=category)
        except Category.DoesNotExist:
            pass
    
    # Apply search filter
    if search_query:
        resources = resources.filter(
            models.Q(name__icontains=search_query) |
            models.Q(description__icontains=search_query)
        )
    
    context = {
        'resources': resources,
        'categories': categories,
        'current_category': category_filter,
        'search_query': search_query,
    }
    return render(request, 'bookings/resource_list.html', context)

@login_required
def resource_detail(request, resource_id):
    """Show a resource's availability and booking form"""
    resource = get_object_or_404(Resource, id=resource_id)
    
    # Check if resource is accessible
    is_owner = request.user == resource.owner
    is_admin = request.user.is_staff
    
    if resource.status != 'APPROVED':
        # Allow owners and admins to see their own resources regardless of status
        if is_owner or is_admin:
            # Show with status warning only to owners/admins
            status_message = f"This resource is {resource.get_status_display()}. "
            if resource.status == 'PENDING':
                status_message += "It is waiting for admin approval."
            elif resource.status == 'REJECTED':
                status_message += "It has been rejected by an admin."
            elif resource.status == 'INACTIVE':
                status_message += "It has been deactivated by an admin."
            messages.warning(request, status_message)
        else:
            # Regular users see an unavailable message
            messages.error(request, "This resource is currently not available for booking.")
            return redirect('resource_list')
    
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    # Get category-specific rules
    category_rules = resource.get_category_rules()
    
    context = {
        'resource': resource,
        'today': today,
        'tomorrow': tomorrow,
        'is_owner': is_owner,
        'is_admin': is_admin,
        'show_status': is_owner or is_admin,
        'category_rules': category_rules,
    }
    return render(request, 'bookings/resource_detail.html', context)

# ============ RESOURCE MANAGEMENT VIEWS (USER) ============

@login_required
def my_resources(request):
    """View for users to see and manage their own resources"""
    resources = Resource.objects.filter(owner=request.user).order_by('-created_at')
    
    # Get filter from query params
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        resources = resources.filter(status=status_filter)
    
    # Get statistics
    total = Resource.objects.filter(owner=request.user).count()
    approved = Resource.objects.filter(owner=request.user, status='APPROVED').count()
    pending = Resource.objects.filter(owner=request.user, status='PENDING').count()
    rejected = Resource.objects.filter(owner=request.user, status='REJECTED').count()
    inactive = Resource.objects.filter(owner=request.user, status='INACTIVE').count()
    
    context = {
        'resources': resources,
        'total': total,
        'approved': approved,
        'pending': pending,
        'rejected': rejected,
        'inactive': inactive,
        'current_filter': status_filter,
    }
    return render(request, 'bookings/my_resources.html', context)

@login_required
def create_resource(request):
    """View for users to create a new resource"""
    if request.method == 'POST':
        form = ResourceForm(request.POST, request.FILES)
        if form.is_valid():
            resource = form.save(commit=False)
            resource.owner = request.user
            resource.status = 'APPROVED'
            resource.save()
            
            # Save extra fields (you can add these to a separate model later)
            # For now, we'll just log them
            print(f"Contact email: {form.cleaned_data.get('contact_email')}")
            print(f"Contact phone: {form.cleaned_data.get('contact_phone')}")
            print(f"Website: {form.cleaned_data.get('website')}")
            print(f"Tags: {form.cleaned_data.get('tags')}")
            
            messages.success(request, f'Resource "{resource.name}" created successfully!')
            return redirect('my_resources')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ResourceForm()
    
    return render(request, 'bookings/resource_form.html', {'form': form, 'title': 'Create Resource'})

@login_required
def edit_resource(request, resource_id):
    """View for users to edit their own resources"""
    resource = get_object_or_404(Resource, id=resource_id)
    
    if resource.owner != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to edit this resource.')
        return redirect('my_resources')
    
    if request.method == 'POST':
        form = ResourceForm(request.POST, request.FILES, instance=resource)
        if form.is_valid():
            form.save()
            messages.success(request, f'Resource "{resource.name}" updated successfully!')
            return redirect('my_resources')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ResourceForm(instance=resource)
    
    return render(request, 'bookings/resource_form.html', {
        'form': form, 
        'resource': resource,
        'title': 'Edit Resource'
    })

@login_required
def delete_resource(request, resource_id):
    """View for users to delete their own resources"""
    resource = get_object_or_404(Resource, id=resource_id)
    
    if resource.owner != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to delete this resource.')
        return redirect('my_resources')
    
    # Check if there are any bookings for this resource
    bookings = Booking.objects.filter(resource=resource, status__in=['PENDING', 'CONFIRMED'])
    if bookings.exists():
        messages.error(request, f'Cannot delete "{resource.name}" because it has active bookings.')
        return redirect('my_resources')
    
    if request.method == 'POST':
        resource_name = resource.name
        resource.delete()
        messages.success(request, f'Resource "{resource_name}" deleted successfully.')
        return redirect('my_resources')
    
    return render(request, 'bookings/resource_confirm_delete.html', {'resource': resource})

# ============ ADMIN RESOURCE MANAGEMENT VIEWS ============

@user_passes_test(lambda u: u.is_staff)
def admin_manage_resources(request):
    """Admin view to manage all resources"""
    resources = Resource.objects.all().order_by('-created_at')
    
    # Get filter from query params
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        resources = resources.filter(status=status_filter)
    
    context = {
        'resources': resources,
        'status_filter': status_filter,
        'status_choices': Resource.STATUS_CHOICES,
    }
    return render(request, 'bookings/admin_manage_resources.html', context)

@user_passes_test(lambda u: u.is_staff)
def admin_update_resource_status(request, resource_id):
    """Admin view to update resource status"""
    resource = get_object_or_404(Resource, id=resource_id)
    
    if request.method == 'POST':
        form = ResourceStatusForm(request.POST, instance=resource)
        if form.is_valid():
            form.save()
            messages.success(request, f'Resource "{resource.name}" status updated to {resource.get_status_display()}.')
        else:
            messages.error(request, 'Failed to update resource status.')
    
    return redirect('admin_manage_resources')

# ============ CATEGORY MANAGEMENT VIEWS (ADMIN ONLY) ============

@user_passes_test(lambda u: u.is_staff)
def manage_categories(request):
    """View for admins to manage categories"""
    categories = Category.objects.all().order_by('name')
    return render(request, 'bookings/manage_categories.html', {'categories': categories})

@user_passes_test(lambda u: u.is_staff)
def create_category(request):
    """View for admins to create a new category"""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully!')
            return redirect('manage_categories')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CategoryForm()
    
    return render(request, 'bookings/category_form.html', {'form': form, 'title': 'Create Category'})

@user_passes_test(lambda u: u.is_staff)
def edit_category(request, category_id):
    """View for admins to edit a category"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('manage_categories')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CategoryForm(instance=category)
    
    return render(request, 'bookings/category_form.html', {'form': form, 'category': category, 'title': 'Edit Category'})

@user_passes_test(lambda u: u.is_staff)
def delete_category(request, category_id):
    """View for admins to delete a category"""
    category = get_object_or_404(Category, id=category_id)
    
    # Check if category has resources
    if category.resources.exists():
        messages.error(request, f'Cannot delete "{category.name}" because it has resources assigned to it.')
        return redirect('manage_categories')
    
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f'Category "{category_name}" deleted successfully.')
        return redirect('manage_categories')
    
    return render(request, 'bookings/category_confirm_delete.html', {'category': category})

# ============ BOOKING MANAGEMENT VIEWS ============

@login_required
def my_bookings(request):
    """Show the current user's bookings with filtering"""
    # Get all bookings
    all_bookings = Booking.objects.filter(customer=request.user)
    
    # Get filter parameter from URL
    status_filter = request.GET.get('status', 'all')
    
    # Apply filter
    if status_filter == 'upcoming':
        bookings = all_bookings.filter(
            start_time__gte=timezone.now(),
            status__in=['PENDING', 'CONFIRMED']
        ).order_by('start_time')
    elif status_filter == 'past':
        bookings = all_bookings.filter(
            models.Q(start_time__lt=timezone.now()) | models.Q(status='COMPLETED')
        ).order_by('-start_time')
    elif status_filter == 'cancelled':
        bookings = all_bookings.filter(status='CANCELLED').order_by('-start_time')
    else:  # 'all'
        bookings = all_bookings.order_by('-start_time')
    
    # Calculate statistics
    total = all_bookings.count()
    upcoming = all_bookings.filter(
        start_time__gte=timezone.now(),
        status__in=['PENDING', 'CONFIRMED']
    ).count()
    past = all_bookings.filter(
        models.Q(start_time__lt=timezone.now()) | models.Q(status='COMPLETED')
    ).count()
    cancelled = all_bookings.filter(status='CANCELLED').count()
    
    context = {
        'bookings': bookings,
        'total': total,
        'upcoming': upcoming,
        'past': past,
        'cancelled': cancelled,
        'current_filter': status_filter,
        'now': timezone.now(),
    }
    return render(request, 'bookings/my_bookings.html', context)

@login_required
def cancel_booking(request, booking_id):
    """Cancel a booking"""
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    if booking.status in ['CANCELLED', 'COMPLETED']:
        messages.error(request, 'This booking cannot be cancelled.')
    elif booking.start_time < timezone.now():
        messages.error(request, 'Cannot cancel a booking that has already passed.')
    else:
        booking.status = 'CANCELLED'
        booking.save()
        messages.success(request, 'Booking cancelled successfully.')
    
    return redirect('my_bookings')

# ============ API ENDPOINTS ============

@login_required
def get_available_times(request):
    """AJAX endpoint to get available time slots for a specific date"""
    resource_id = request.GET.get('resource_id')
    date_str = request.GET.get('date')
    
    if not resource_id or not date_str:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        resource = get_object_or_404(Resource, id=resource_id)
        now = timezone.now()
        
        slots = []
        start_hour = 9
        end_hour = 17
        
        for hour in range(start_hour, end_hour):
            slot_start = timezone.make_aware(datetime.combine(date, datetime.min.time().replace(hour=hour)))
            slot_end = slot_start + timedelta(hours=1)
            
            # Check if the slot is in the past
            is_past = slot_start < now
            
            # Check if the slot is booked
            is_booked = Booking.objects.filter(
                resource=resource,
                start_time__lt=slot_end,
                end_time__gt=slot_start,
                status__in=['PENDING', 'CONFIRMED']
            ).exists()
            
            # A slot is available if it's not booked AND not in the past
            is_available = not is_booked and not is_past
            
            slots.append({
                'start': slot_start.isoformat(),
                'end': slot_end.isoformat(),
                'available': is_available,
                'start_display': slot_start.strftime('%I:%M %p'),
                'end_display': slot_end.strftime('%I:%M %p'),
                'is_past': is_past,
                'is_booked': is_booked,
            })
        
        return JsonResponse({'slots': slots})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def book_slot(request):
    """Handle booking creation via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    resource_id = request.POST.get('resource_id')
    start_time_str = request.POST.get('start_time')
    end_time_str = request.POST.get('end_time')
    notes = request.POST.get('notes', '')
    
    if not all([resource_id, start_time_str, end_time_str]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
        
        if timezone.is_naive(start_time):
            start_time = timezone.make_aware(start_time)
        if timezone.is_naive(end_time):
            end_time = timezone.make_aware(end_time)
        
        booking = BookingService.create_booking(
            resource_id=resource_id,
            customer=request.user,
            start_time=start_time,
            end_time=end_time,
            notes=notes
        )
        
        return JsonResponse({
            'success': True,
            'booking_id': booking.id,
            'message': f'Booking confirmed for {booking.start_time.strftime("%I:%M %p")}'
        })
        
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        # Print the full error to terminal
        import traceback
        print("=" * 50)
        print("ERROR IN BOOKING:")
        traceback.print_exc()
        print("=" * 50)
        return JsonResponse({'error': f'Error: {str(e)}'}, status=500)

@login_required
def profile(request):
    """View for user profile with booking history"""
    # Safety net: create profile if it doesn't exist
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if created:
        messages.info(request, "Your profile was created automatically.")
    
    bookings = Booking.objects.filter(customer=request.user).order_by('-created_at')
    
    # Get booking stats
    stats = profile.get_booking_stats()
    
    # Get recent bookings (last 10)
    recent_bookings = bookings[:10]
    
    # Get upcoming bookings
    upcoming_bookings = bookings.filter(
        start_time__gte=timezone.now(),
        status__in=['PENDING', 'CONFIRMED']
    ).order_by('start_time')[:5]
    
    context = {
        'profile': profile,
        'stats': stats,
        'recent_bookings': recent_bookings,
        'upcoming_bookings': upcoming_bookings,
        'now': timezone.now(),
    }
    return render(request, 'bookings/profile.html', context)

@login_required
def edit_profile(request):
    """View for editing user profile"""
    profile = request.user.profile
    
    if request.method == 'POST':
        user_form = UserSettingsForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserSettingsForm(instance=request.user)
        profile_form = UserProfileForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'profile': profile,
    }
    return render(request, 'bookings/edit_profile.html', context)

@login_required
def change_password(request):
    """View for changing user password"""
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keep user logged in
            messages.success(request, 'Your password has been changed successfully!')
            return redirect('profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, 'bookings/change_password.html', {'form': form})

@login_required
def booking_history(request):
    """View for full booking history with filters"""
    bookings = Booking.objects.filter(customer=request.user).order_by('-start_time')
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    date_filter = request.GET.get('date', 'all')
    search_query = request.GET.get('search', '')
    
    # Apply status filter
    if status_filter != 'all':
        bookings = bookings.filter(status=status_filter)
    
    # Apply date filter
    now = timezone.now()
    if date_filter == 'upcoming':
        bookings = bookings.filter(start_time__gte=now, status__in=['PENDING', 'CONFIRMED'])
    elif date_filter == 'past':
        bookings = bookings.filter(start_time__lt=now)
    elif date_filter == 'this_month':
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        bookings = bookings.filter(start_time__gte=month_start)
    
    # Apply search
    if search_query:
        bookings = bookings.filter(
            models.Q(resource__name__icontains=search_query) |
            models.Q(resource__description__icontains=search_query)
        )
    
    # Pagination (simple)
    page = int(request.GET.get('page', 1))
    items_per_page = 10
    start = (page - 1) * items_per_page
    end = start + items_per_page
    total = bookings.count()
    total_pages = (total + items_per_page - 1) // items_per_page
    
    context = {
        'bookings': bookings[start:end],
        'page': page,
        'total_pages': total_pages,
        'total': total,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'search_query': search_query,
        'now': now,
        'status_choices': Booking.STATUS_CHOICES,
    }
    return render(request, 'bookings/booking_history.html', context)
