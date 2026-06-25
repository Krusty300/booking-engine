from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db import models
from datetime import datetime, timedelta
from .models import Resource, Booking, Category, UserProfile, AnalyticsEvent, DailyAnalytics
from .services import BookingService
from .export_service import ExportService
from .forms import SignUpForm, ResourceForm, ResourceStatusForm, CategoryForm, UserProfileForm, UserSettingsForm
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import TemplateView
from calendar import monthcalendar, month_name
from datetime import datetime, timedelta
from django.db.models import Q
from django.core.paginator import Paginator
from .email_service import send_review_submitted_email, send_review_approved_email, send_review_rejected_email
from .forms import ReviewForm, ReviewFilterForm
from .models import Review
from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
import calendar
import json

# Import analytics service after all other imports
from .analytics_service import AnalyticsService

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
    """Show the current user's bookings with enhanced filtering and pagination"""
    # Get all bookings
    all_bookings = Booking.objects.filter(customer=request.user)
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    date_filter = request.GET.get('date', 'all')
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', '-start_time')
    
    # Apply status filter
    if status_filter == 'upcoming':
        bookings = all_bookings.filter(
            start_time__gte=timezone.now(),
            status__in=['PENDING', 'CONFIRMED']
        )
    elif status_filter == 'past':
        bookings = all_bookings.filter(
            Q(start_time__lt=timezone.now()) | Q(status='COMPLETED')
        )
    elif status_filter == 'cancelled':
        bookings = all_bookings.filter(status='CANCELLED')
    elif status_filter == 'pending':
        bookings = all_bookings.filter(status='PENDING')
    elif status_filter == 'confirmed':
        bookings = all_bookings.filter(status='CONFIRMED')
    else:  # 'all'
        bookings = all_bookings
    
    # Apply date filter
    now = timezone.now()
    if date_filter == 'today':
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        bookings = bookings.filter(start_time__gte=today_start, start_time__lte=today_end)
    elif date_filter == 'week':
        week_start = now - timedelta(days=7)
        bookings = bookings.filter(start_time__gte=week_start)
    elif date_filter == 'month':
        month_start = now - timedelta(days=30)
        bookings = bookings.filter(start_time__gte=month_start)
    elif date_filter == 'upcoming_dates':
        bookings = bookings.filter(start_time__gte=now)
    
    # Apply search
    if search_query:
        bookings = bookings.filter(
            Q(resource__name__icontains=search_query) |
            Q(resource__description__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
    
    # Apply sorting
    if sort_by == 'start_time':
        bookings = bookings.order_by('start_time')
    elif sort_by == 'end_time':
        bookings = bookings.order_by('end_time')
    elif sort_by == 'resource':
        bookings = bookings.order_by('resource__name')
    elif sort_by == 'status':
        bookings = bookings.order_by('status')
    else:  # '-start_time'
        bookings = bookings.order_by('-start_time')
    
    # Pagination
    paginator = Paginator(bookings, 10)  # 10 bookings per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Calculate statistics
    total = all_bookings.count()
    upcoming = all_bookings.filter(
        start_time__gte=timezone.now(),
        status__in=['PENDING', 'CONFIRMED']
    ).count()
    past = all_bookings.filter(
        Q(start_time__lt=timezone.now()) | Q(status='COMPLETED')
    ).count()
    cancelled = all_bookings.filter(status='CANCELLED').count()
    pending = all_bookings.filter(status='PENDING').count()
    confirmed = all_bookings.filter(status='CONFIRMED').count()
    
    # Get upcoming bookings for quick view
    upcoming_bookings = all_bookings.filter(
        start_time__gte=timezone.now(),
        status__in=['PENDING', 'CONFIRMED']
    ).order_by('start_time')[:3]
    
    context = {
        'bookings': page_obj,
        'total': total,
        'upcoming': upcoming,
        'past': past,
        'cancelled': cancelled,
        'pending': pending,
        'confirmed': confirmed,
        'current_filter': status_filter,
        'current_date_filter': date_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'now': timezone.now(),
        'upcoming_bookings': upcoming_bookings,
        'page_obj': page_obj,
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

@login_required
def export_bookings(request):
    """Export bookings as CSV"""
    import csv
    from django.http import HttpResponse
    
    bookings = Booking.objects.filter(customer=request.user).order_by('-start_time')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="my_bookings_{timezone.now().strftime("%Y%m%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['ID', 'Resource', 'Start Time', 'End Time', 'Duration (hours)', 'Status', 'Notes', 'Created At'])
    
    for booking in bookings:
        writer.writerow([
            booking.id,
            booking.resource.name,
            booking.start_time.strftime('%Y-%m-%d %H:%M'),
            booking.end_time.strftime('%Y-%m-%d %H:%M'),
            booking.get_duration(),
            booking.get_status_display(),
            booking.notes or '',
            booking.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    
    return response


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
            is_past_slot = slot_start < now
            
            # Check if the slot is booked
            is_booked = Booking.objects.filter(
                resource=resource,
                start_time__lt=slot_end,
                end_time__gt=slot_start,
                status__in=['PENDING', 'CONFIRMED']
            ).exists()
            
            # A slot is available if it's not booked AND not in the past
            is_available = not is_booked and not is_past_slot
            
            slots.append({
                'start': slot_start.isoformat(),
                'end': slot_end.isoformat(),
                'available': is_available,
                'start_display': slot_start.strftime('%I:%M %p'),
                'end_display': slot_end.strftime('%I:%M %p'),
                'is_past': is_past_slot,
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


# ============ ANALYTICS VIEWS ============

@staff_member_required
def admin_dashboard(request):
    """Admin dashboard with analytics"""
    context = {
        'stats': AnalyticsService.get_dashboard_stats(request),
        'booking_analytics': AnalyticsService.get_booking_analytics('month'),
        'user_analytics': AnalyticsService.get_user_analytics(),
        'resource_analytics': AnalyticsService.get_resource_analytics(),
        # New chart data
        'hourly_patterns': AnalyticsService.get_hourly_patterns(),
        'weekly_trends': AnalyticsService.get_weekly_trends(),
        'status_distribution': AnalyticsService.get_status_distribution(),
        'monthly_trends': AnalyticsService.get_monthly_trends(),
    }
    return render(request, 'bookings/admin_dashboard.html', context)

@staff_member_required
def analytics_data(request):
    """API endpoint for analytics data (for charts)"""
    data_type = request.GET.get('type', 'dashboard')
    
    if data_type == 'dashboard':
        stats = AnalyticsService.get_dashboard_stats(request)
        # Convert QuerySets to lists for JSON serialization
        data = {
            'total_bookings': stats.get('total_bookings', 0),
            'confirmed_bookings': stats.get('confirmed_bookings', 0),
            'cancelled_bookings': stats.get('cancelled_bookings', 0),
            'completed_bookings': stats.get('completed_bookings', 0),
            'total_users': stats.get('total_users', 0),
            'active_users': stats.get('active_users', 0),
            'new_users': stats.get('new_users', 0),
            'total_revenue': str(stats.get('total_revenue', 0)),
            'booking_trends': stats.get('booking_trends', []),
            'category_distribution': stats.get('category_distribution', []),
            'status_distribution': stats.get('status_distribution', []),
            'popular_resources': [
                {
                    'name': r.name,
                    'booking_count': r.booking_count,
                    'category': r.category.name if r.category else 'Uncategorized'
                }
                for r in stats.get('popular_resources', [])
            ],
            'recent_bookings': [
                {
                    'id': b.id,
                    'resource': b.resource.name,
                    'customer': b.customer.username,
                    'status': b.get_status_display(),
                    'start_time': b.start_time.strftime('%Y-%m-%d %H:%M')
                }
                for b in stats.get('recent_bookings', [])
            ]
        }
    elif data_type == 'bookings':
        period = request.GET.get('period', 'month')
        data = AnalyticsService.get_booking_analytics(period)
    elif data_type == 'users':
        user_data = AnalyticsService.get_user_analytics()
        # Convert QuerySets to lists
        data = {
            'active_users': user_data.get('active_users', 0),
            'inactive_users': user_data.get('inactive_users', 0),
            'new_users_trend': user_data.get('new_users_trend', []),
            'total_users': user_data.get('total_users', 0),
            'users_with_bookings': user_data.get('users_with_bookings', 0),
            'users_with_resources': user_data.get('users_with_resources', 0),
            'engagement_rate': user_data.get('engagement_rate', 0),
            'top_users': [
                {
                    'username': u.username,
                    'booking_count': u.booking_count
                }
                for u in user_data.get('top_users', [])
            ]
        }
    elif data_type == 'resources':
        resource_data = AnalyticsService.get_resource_analytics()
        # Convert QuerySets to lists
        data = {
            'resource_popularity': [
                {
                    'name': r.name,
                    'booking_count': r.booking_count,
                    'category': r.category.name if r.category else 'Uncategorized',
                    'status': r.get_status_display()
                }
                for r in resource_data.get('resource_popularity', [])
            ],
            'category_counts': list(resource_data.get('category_counts', [])),
            'status_counts': list(resource_data.get('status_counts', [])),
            'popular_hours': resource_data.get('popular_hours', {})
        }
    else:
        data = {'error': 'Invalid data type'}
    
    return JsonResponse(data, safe=False)

@staff_member_required
def export_report(request):
    """Export reports in various formats"""
    report_type = request.GET.get('type', 'bookings')
    format_type = request.GET.get('format', 'csv')
    
    if format_type == 'csv':
        # CSV export (existing)
        if report_type == 'bookings':
            content = AnalyticsService.export_bookings_csv()
            filename = f'bookings_export_{timezone.now().strftime("%Y%m%d")}.csv'
        elif report_type == 'users':
            content = AnalyticsService.export_users_csv()
            filename = f'users_export_{timezone.now().strftime("%Y%m%d")}.csv'
        elif report_type == 'resources':
            content = AnalyticsService.export_resources_csv()
            filename = f'resources_export_{timezone.now().strftime("%Y%m%d")}.csv'
        else:
            return HttpResponse('Invalid report type', status=400)
        
        response = HttpResponse(content, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    elif format_type == 'excel':
        excel_file = ExportService.export_to_excel(report_type)
        response = HttpResponse(excel_file.getvalue(), 
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{report_type}_{timezone.now().strftime("%Y%m%d")}.xlsx"'
        return response
    
    elif format_type == 'pdf':
        pdf_file = ExportService.export_to_pdf(report_type)
        response = HttpResponse(pdf_file.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report_type}_{timezone.now().strftime("%Y%m%d")}.pdf"'
        return response
    
    return HttpResponse('Invalid format', status=400)


class CalendarView(TemplateView):
    """Calendar view showing resource availability with direct booking"""
    template_name = 'bookings/calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get month and year from URL params, default to current month
        year = int(self.request.GET.get('year', timezone.now().year))
        month = int(self.request.GET.get('month', timezone.now().month))
        
        # Get the resource ID if specified
        resource_id = self.request.GET.get('resource')
        selected_date = self.request.GET.get('date')
        
        # Get all approved resources for the calendar
        if self.request.user.is_staff:
            resources = Resource.objects.all()
        else:
            resources = Resource.objects.filter(status='APPROVED')
        
        # If a specific resource is selected, use it
        selected_resource = None
        if resource_id:
            try:
                selected_resource = resources.get(id=resource_id)
            except Resource.DoesNotExist:
                pass
        
        # Build calendar data
        calendar_data = self.build_calendar_data(year, month, selected_resource)
        
        # Get time slots for selected date
        time_slots = []
        selected_date_obj = None
        if selected_date:
            try:
                selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
                time_slots = self.get_time_slots_for_date(selected_date_obj, selected_resource)
            except ValueError:
                pass
        
        # Get month navigation
        prev_month = month - 1
        prev_year = year
        if prev_month == 0:
            prev_month = 12
            prev_year = year - 1
        
        next_month = month + 1
        next_year = year
        if next_month == 13:
            next_month = 1
            next_year = year + 1
        
        context.update({
            'year': year,
            'month': month,
            'month_name': month_name[month],
            'calendar_data': calendar_data,
            'resources': resources,
            'selected_resource': selected_resource,
            'selected_date': selected_date_obj,
            'time_slots': time_slots,
            'prev_year': prev_year,
            'prev_month': prev_month,
            'next_year': next_year,
            'next_month': next_month,
            'today': timezone.now().date(),
        })
        
        return context
    
    def build_calendar_data(self, year, month, selected_resource=None):
        """Build calendar data with availability information"""
        cal = monthcalendar(year, month)
        today = timezone.now().date()
        
        calendar_data = []
        
        for week in cal:
            week_data = []
            for day in week:
                if day == 0:
                    week_data.append(None)
                else:
                    date_obj = datetime(year, month, day).date()
                    
                    # Check if this date is available for booking
                    availability = self.get_day_availability(date_obj, selected_resource)
                    
                    week_data.append({
                        'day': day,
                        'date': date_obj,
                        'is_today': date_obj == today,
                        'is_past': date_obj < today,
                        'availability': availability,
                        'available_count': availability.get('available_count', 0),
                        'total_slots': availability.get('total_slots', 0),
                        'is_fully_booked': availability.get('is_fully_booked', False),
                        'has_availability': availability.get('available_count', 0) > 0,
                    })
            
            calendar_data.append(week_data)
        
        return calendar_data
    
    def get_day_availability(self, date_obj, resource=None):
        """Get availability for a specific day"""
        # If date is in the past, mark as unavailable
        if date_obj < timezone.now().date():
            return {
                'available_count': 0,
                'total_slots': 0,
                'is_fully_booked': True,
                'is_past': True
            }
        
        # Generate time slots for the day (9 AM - 5 PM)
        start_hour = 9
        end_hour = 17
        total_slots = end_hour - start_hour
        available_count = 0
        
        # Get bookings for this day
        day_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time()))
        day_end = timezone.make_aware(datetime.combine(date_obj, datetime.max.time()))
        
        # Filter resources
        if resource:
            resources_list = [resource]
        else:
            resources_list = Resource.objects.filter(status='APPROVED')
        
        # Check each time slot
        for hour in range(start_hour, end_hour):
            slot_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time().replace(hour=hour)))
            slot_end = slot_start + timedelta(hours=1)
            
            # Check if any resource is available for this slot
            is_available = False
            for res in resources_list:
                # Check if slot is booked for this resource
                is_booked = Booking.objects.filter(
                    resource=res,
                    start_time__lt=slot_end,
                    end_time__gt=slot_start,
                    status__in=['PENDING', 'CONFIRMED']
                ).exists()
                
                if not is_booked:
                    is_available = True
                    break
            
            if is_available:
                available_count += 1
        
        is_fully_booked = available_count == 0
        
        return {
            'available_count': available_count,
            'total_slots': total_slots,
            'is_fully_booked': is_fully_booked,
            'is_past': False,
            'available_percentage': (available_count / total_slots * 100) if total_slots > 0 else 0
        }
    
    def get_time_slots_for_date(self, date_obj, resource=None):
        """Get available time slots for a specific date"""
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        now = timezone.now()
        slots = []
        start_hour = 9
        end_hour = 17
        
        # Get resources
        if resource:
            resources_list = [resource]
        else:
            resources_list = Resource.objects.filter(status='APPROVED')
        
        for hour in range(start_hour, end_hour):
            slot_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time().replace(hour=hour)))
            slot_end = slot_start + timedelta(hours=1)
            
            # Check if slot is in the past
            is_past = slot_start < now
            
            # Check availability for this slot across all resources
            available_resources = []
            for res in resources_list:
                is_booked = Booking.objects.filter(
                    resource=res,
                    start_time__lt=slot_end,
                    end_time__gt=slot_start,
                    status__in=['PENDING', 'CONFIRMED']
                ).exists()
                
                if not is_booked and not is_past:
                    available_resources.append({
                        'id': res.id,
                        'name': res.name,
                        'category': res.category.name if res.category else 'Uncategorized'
                    })
            
            slots.append({
                'start_time': slot_start,
                'end_time': slot_end,
                'start_display': slot_start.strftime('%I:%M %p'),
                'end_display': slot_end.strftime('%I:%M %p'),
                'is_past': is_past,
                'is_available': len(available_resources) > 0 and not is_past,
                'available_resources': available_resources,
                'resource_count': len(available_resources)
            })
        
        return slots
    
    def post(self, request, *args, **kwargs):
        """Handle AJAX booking requests from the calendar"""
        import json
        from .services import BookingService
        from django.core.exceptions import ValidationError
        
        try:
            data = json.loads(request.body)
            resource_id = data.get('resource_id')
            start_time_str = data.get('start_time')
            end_time_str = data.get('end_time')
            notes = data.get('notes', '')
            
            if not all([resource_id, start_time_str, end_time_str]):
                return JsonResponse({'error': 'Missing parameters'}, status=400)
            
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
            return JsonResponse({'error': str(e)}, status=500)


def custom_logout(request):
    """Custom logout view that allows GET requests"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('/')

@login_required
def write_review(request, resource_id):
    """View for writing a review"""
    resource = get_object_or_404(Resource, id=resource_id)
    
    # Check if user has already reviewed this resource
    existing_review = Review.objects.filter(user=request.user, resource=resource).first()
    if existing_review:
        messages.warning(request, 'You have already reviewed this resource.')
        return redirect('edit_review', review_id=existing_review.id)
    
    # Check if user has booked this resource
    has_booked = Booking.objects.filter(
        customer=request.user,
        resource=resource,
        status='CONFIRMED'
    ).exists()
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.resource = resource
            review.is_verified = has_booked
            
            # IMPORTANT: Set to PENDING for admin approval
            review.status = 'PENDING'  # Changed to 'PENDING' for moderation
            
            # Link to booking if exists
            booking = Booking.objects.filter(
                customer=request.user,
                resource=resource,
                status='CONFIRMED'
            ).first()
            if booking:
                review.booking = booking
            
            review.save()
            
            # Send confirmation email
            send_review_submitted_email(review)
            
            messages.success(request, 'Your review has been submitted and is awaiting admin approval.')
            return redirect('resource_detail', resource_id=resource.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ReviewForm()
    
    context = {
        'resource': resource,
        'form': form,
        'has_booked': has_booked,
    }
    return render(request, 'bookings/write_review.html', context)

@login_required
def edit_review(request, review_id):
    """View for editing a review"""
    review = get_object_or_404(Review, id=review_id, user=request.user)
    
    if review.status == 'APPROVED':
        messages.warning(request, 'This review has been approved and cannot be edited.')
        return redirect('resource_detail', resource_id=review.resource.id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your review has been updated.')
            return redirect('resource_detail', resource_id=review.resource.id)
    else:
        form = ReviewForm(instance=review)
    
    context = {
        'review': review,
        'form': form,
        'resource': review.resource,
    }
    return render(request, 'bookings/edit_review.html', context)

@login_required
def delete_review(request, review_id):
    """View for deleting a review"""
    review = get_object_or_404(Review, id=review_id, user=request.user)
    
    if request.method == 'POST':
        review.delete()
        messages.success(request, 'Your review has been deleted.')
        return redirect('resource_detail', resource_id=review.resource.id)
    
    return render(request, 'bookings/delete_review.html', {'review': review})

@login_required
def my_reviews(request):
    """View for user's reviews"""
    reviews = Review.objects.filter(user=request.user).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        reviews = reviews.filter(status=status_filter)
    
    context = {
        'reviews': reviews,
        'status_filter': status_filter,
    }
    return render(request, 'bookings/my_reviews.html', context)

@login_required
def resource_reviews(request, resource_id):
    """View for all reviews of a resource"""
    resource = get_object_or_404(Resource, id=resource_id)
    reviews = resource.reviews.filter(status='APPROVED')
    
    # Filter form
    filter_form = ReviewFilterForm(request.GET or None)
    if filter_form.is_valid():
        if rating := filter_form.cleaned_data.get('rating'):
            reviews = reviews.filter(rating=rating)
        
        sort = filter_form.cleaned_data.get('sort', 'newest')
        if sort == 'newest':
            reviews = reviews.order_by('-created_at')
        elif sort == 'oldest':
            reviews = reviews.order_by('created_at')
        elif sort == 'highest':
            reviews = reviews.order_by('-rating')
        elif sort == 'lowest':
            reviews = reviews.order_by('rating')
        elif sort == 'helpful':
            reviews = reviews.order_by('-helpful_count')
    
    # Pagination
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    avg_rating = resource.get_average_rating()
    rating_count = resource.get_rating_count()
    distribution = resource.get_rating_distribution()
    
    context = {
        'resource': resource,
        'reviews': page_obj,
        'avg_rating': avg_rating,
        'rating_count': rating_count,
        'distribution': distribution,
        'filter_form': filter_form,
        'page_obj': page_obj,
    }
    return render(request, 'bookings/resource_reviews.html', context)

@login_required
def toggle_review_helpful(request, review_id):
    """Toggle helpful status for a review"""
    if request.method == 'POST':
        review = get_object_or_404(Review, id=review_id)
        review.toggle_helpful(request.user)
        return JsonResponse({
            'helpful_count': review.helpful_count,
            'is_helpful': review.is_helpful(request.user)
        })
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def my_review_history(request):
    """View for user's review history"""
    reviews = Review.objects.filter(user=request.user).order_by('-created_at')
    total = reviews.count()
    approved = reviews.filter(status='APPROVED').count()
    pending = reviews.filter(status='PENDING').count()
    rejected = reviews.filter(status='REJECTED').count()
    
    context = {
        'reviews': reviews,
        'total': total,
        'approved': approved,
        'pending': pending,
        'rejected': rejected,
    }
    return render(request, 'bookings/my_review_history.html', context)

@staff_member_required
def admin_reviews(request):
    """Admin view for managing all reviews"""
    reviews = Review.objects.all().order_by('-created_at')
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    rating_filter = request.GET.get('rating', 'all')
    search_query = request.GET.get('search', '')
    
    # Apply filters
    if status_filter != 'all':
        reviews = reviews.filter(status=status_filter)
    
    if rating_filter != 'all':
        reviews = reviews.filter(rating=rating_filter)
    
    if search_query:
        reviews = reviews.filter(
            Q(comment__icontains=search_query) |
            Q(title__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(resource__name__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(reviews, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total = Review.objects.count()
    pending = Review.objects.filter(status='PENDING').count()
    approved = Review.objects.filter(status='APPROVED').count()
    rejected = Review.objects.filter(status='REJECTED').count()
    
    # Get all resources for filter
    resources = Resource.objects.filter(reviews__isnull=False).distinct()
    
    context = {
        'reviews': page_obj,
        'total': total,
        'pending': pending,
        'approved': approved,
        'rejected': rejected,
        'status_filter': status_filter,
        'rating_filter': rating_filter,
        'search_query': search_query,
        'resources': resources,
        'page_obj': page_obj,
        'rating_choices': Review.RATING_CHOICES,
        'status_choices': Review.STATUS_CHOICES,
    }
    return render(request, 'bookings/admin/admin_reviews.html', context)

@staff_member_required
def admin_review_detail(request, review_id):
    """View for admin to see review details and moderate"""
    review = get_object_or_404(Review, id=review_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('moderation_reason', '')
        
        if action == 'approve':
            review.moderate('APPROVED', request.user, None)
            messages.success(request, f'Review #{review.id} has been approved.')
            send_review_approved_email(review)
            
        elif action == 'reject':
            if not reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return redirect('admin_review_detail', review_id=review.id)
            review.moderate('REJECTED', request.user, reason)
            messages.success(request, f'Review #{review.id} has been rejected.')
            send_review_rejected_email(review)
            
        elif action == 'reject-approved':
            # Handle rejection of an approved review
            if not reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return redirect('admin_review_detail', review_id=review.id)
            review.moderate('REJECTED', request.user, reason)
            messages.success(request, f'Review #{review.id} has been rejected and removed from public view.')
            send_review_rejected_email(review)
            
        elif action == 'delete':
            review.delete()
            messages.success(request, 'Review has been deleted.')
            return redirect('admin_reviews')
        
        return redirect('admin_reviews')
    
    context = {
        'review': review,
        'review_status_choices': Review.STATUS_CHOICES,
    }
    return render(request, 'bookings/admin/admin_review_detail.html', context)

@staff_member_required
def admin_bulk_action_reviews(request):
    """Bulk action for reviews"""
    if request.method == 'POST':
        review_ids = request.POST.getlist('review_ids')
        action = request.POST.get('action')
        reason = request.POST.get('moderation_reason', '')
        
        if not review_ids:
            messages.error(request, 'No reviews selected.')
            return redirect('admin_reviews')
        
        reviews = Review.objects.filter(id__in=review_ids)
        count = reviews.count()
        
        if action == 'approve':
            for review in reviews:
                review.moderate('APPROVED', request.user, None)
                send_review_approved_email(review)
            messages.success(request, f'{count} reviews have been approved.')
            
        elif action == 'reject':
            if not reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return redirect('admin_reviews')
            for review in reviews:
                review.moderate('REJECTED', request.user, reason)
                send_review_rejected_email(review)
            messages.success(request, f'{count} reviews have been rejected.')
            
        elif action == 'delete':
            for review in reviews:
                review.delete()
            messages.success(request, f'{count} reviews have been deleted.')
        
        return redirect('admin_reviews')
    
    return redirect('admin_reviews')