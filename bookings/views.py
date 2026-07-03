from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, authenticate
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.db import models, transaction
from datetime import datetime, timedelta
from .models import (
    Resource, Booking, Category, UserProfile, AnalyticsEvent, DailyAnalytics, 
    Equipment, EquipmentRental, MaintenanceRecord, EquipmentCategory, Review,
    MeetingRoom, SavedSearch, EquipmentReservation
)
from .services import BookingService
from .services.equipment_service import EquipmentService
from .export_service import ExportService
from .forms import (
    SignUpForm, ResourceForm, ResourceStatusForm, CategoryForm, 
    UserProfileForm, UserSettingsForm, ReviewForm, ReviewFilterForm,
    EquipmentForm, MeetingRoomForm
)
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.admin.views.decorators import staff_member_required
from django.views.generic import TemplateView
from calendar import monthcalendar, month_name
from django.db.models import Q
from django.core.paginator import Paginator
from .email_service import send_review_submitted_email, send_review_approved_email, send_review_rejected_email
from django.contrib.auth import logout
import calendar
import csv
import json
from .services.search_service import SearchService
from .services.reservation_service import ReservationService
from django.template.loader import render_to_string
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

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
            return redirect('bookings:resource_list')  # ✅ Fixed with namespace
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SignUpForm()
    
    return render(request, 'registration/signup.html', {'form': form})

# ============ RESOURCE LISTING AND BOOKING VIEWS ============

@login_required
def resource_list(request):
    """List all available resources with category filtering"""
    categories = Category.objects.all().order_by('name')
    
    category_filter = request.GET.get('category', 'all')
    search_query = request.GET.get('search', '').strip()
    
    if request.user.is_staff:
        resources = Resource.objects.all().order_by('-created_at', 'id')
    else:
        resources = Resource.objects.filter(status='APPROVED').order_by('-created_at', 'id')
    
    if category_filter != 'all' and category_filter:
        try:
            category = Category.objects.get(slug=category_filter)
            resources = resources.filter(category=category)
        except Category.DoesNotExist:
            pass
    
    if search_query and len(search_query) >= 2:
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
    
    is_owner = request.user == resource.owner
    is_admin = request.user.is_staff
    
    if resource.status != 'APPROVED':
        if is_owner or is_admin:
            status_message = f"This resource is {resource.get_status_display()}. "
            if resource.status == 'PENDING':
                status_message += "It is waiting for admin approval."
            elif resource.status == 'REJECTED':
                status_message += "It has been rejected by an admin."
            elif resource.status == 'INACTIVE':
                status_message += "It has been deactivated by an admin."
            messages.warning(request, status_message)
        else:
            messages.error(request, "This resource is currently not available for booking.")
            return redirect('resource_list')
    
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
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
    resources = Resource.objects.filter(owner=request.user).order_by('-created_at', 'id')
    
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        resources = resources.filter(status=status_filter)
    
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
            try:
                # 1. Always create the Resource first
                resource = form.save(commit=False)
                resource.owner = request.user
                resource.status = 'APPROVED'
                resource.save()
                
                # 2. Check if this should be a Meeting Room (explicit checkbox)
                is_meeting_room = request.POST.get('is_meeting_room') == 'on'
                
                # 3. Create MeetingRoom if checkbox is checked
                if is_meeting_room:
                    meeting_room = MeetingRoom.objects.create(resource=resource)
                    
                    # Room identification
                    meeting_room.room_number = request.POST.get('room_number', '')
                    meeting_room.floor_number = int(request.POST.get('floor_number', 1))
                    meeting_room.building_name = request.POST.get('building_name', '')
                    
                    # Capacities
                    meeting_room.seating_capacity = int(request.POST.get('seating_capacity', 0))
                    meeting_room.standing_capacity = int(request.POST.get('standing_capacity', 0))
                    meeting_room.classroom_capacity = int(request.POST.get('classroom_capacity', 0))
                    meeting_room.theater_capacity = int(request.POST.get('theater_capacity', 0))
                    
                    # Features
                    meeting_room.has_projector = request.POST.get('has_projector') == 'on'
                    meeting_room.has_whiteboard = request.POST.get('has_whiteboard') == 'on'
                    meeting_room.has_video_conferencing = request.POST.get('has_video_conferencing') == 'on'
                    meeting_room.has_phone = request.POST.get('has_phone') == 'on'
                    meeting_room.has_smart_tv = request.POST.get('has_smart_tv') == 'on'
                    meeting_room.has_audio_system = request.POST.get('has_audio_system') == 'on'
                    meeting_room.has_wifi = request.POST.get('has_wifi') == 'on'
                    meeting_room.has_air_conditioning = request.POST.get('has_air_conditioning') == 'on'
                    meeting_room.is_accessible = request.POST.get('is_accessible') == 'on'
                    
                    # Room details
                    room_size = request.POST.get('room_size_sqft')
                    meeting_room.room_size_sqft = int(room_size) if room_size and room_size.strip() else None
                    meeting_room.natural_light = request.POST.get('natural_light') == 'on'
                    meeting_room.has_window = request.POST.get('has_window') == 'on'
                    
                    # Setup times with defaults
                    setup_time = request.POST.get('default_setup_time')
                    meeting_room.default_setup_time = int(setup_time) if setup_time and setup_time.strip() else 15
                    
                    teardown_time = request.POST.get('default_teardown_time')
                    meeting_room.default_teardown_time = int(teardown_time) if teardown_time and teardown_time.strip() else 15
                    
                    # Images
                    if 'room_photo' in request.FILES:
                        meeting_room.room_photo = request.FILES['room_photo']
                    if 'floor_plan' in request.FILES:
                        meeting_room.floor_plan = request.FILES['floor_plan']
                    
                    # Notes
                    meeting_room.notes = request.POST.get('notes', '')
                    
                    # Amenities (Many-to-Many)
                    if request.POST.getlist('amenities'):
                        meeting_room.amenities.set(request.POST.getlist('amenities'))
                    
                    # Set default capacity if none specified
                    if not any([meeting_room.seating_capacity, meeting_room.standing_capacity,
                               meeting_room.classroom_capacity, meeting_room.theater_capacity]):
                        meeting_room.seating_capacity = 1
                    
                    meeting_room.save()
                    messages.success(request, f'Meeting Room "{resource.name}" created successfully!')
                else:
                    messages.success(request, f'Resource "{resource.name}" created successfully!')
                
                return redirect('bookings:my_resources')
            except Exception as e:
                messages.error(request, f'Error creating resource: {str(e)}')
                # Log the error for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Create resource error: {e}', exc_info=True)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ResourceForm()
    
    # Pass empty meeting room form for new resources
    meeting_room_form = MeetingRoomForm()
    
    context = {
        'form': form,
        'meeting_room_form': meeting_room_form,
        'title': 'Create Resource',
    }
    return render(request, 'bookings/resource_form.html', context)

@login_required
def edit_resource(request, resource_id):
    """View for users to edit their own resources"""
    resource = get_object_or_404(Resource, id=resource_id)
    
    if resource.owner != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to edit this resource.')
        return redirect('bookings:my_resources')
    
    meeting_room_form = None
    
    if request.method == 'POST':
        form = ResourceForm(request.POST, request.FILES, instance=resource)
        
        if form.is_valid():
            try:
                resource = form.save()
                
                # Check if this should be a Meeting Room (explicit checkbox)
                is_meeting_room = request.POST.get('is_meeting_room') == 'on'
                
                if is_meeting_room:
                    # Get or create meeting room
                    meeting_room, created = MeetingRoom.objects.get_or_create(resource=resource)
                    
                    # Room identification
                    meeting_room.room_number = request.POST.get('room_number', '')
                    meeting_room.floor_number = int(request.POST.get('floor_number', 1))
                    meeting_room.building_name = request.POST.get('building_name', '')
                    
                    # Capacities
                    meeting_room.seating_capacity = int(request.POST.get('seating_capacity', 0))
                    meeting_room.standing_capacity = int(request.POST.get('standing_capacity', 0))
                    meeting_room.classroom_capacity = int(request.POST.get('classroom_capacity', 0))
                    meeting_room.theater_capacity = int(request.POST.get('theater_capacity', 0))
                    
                    # Features
                    meeting_room.has_projector = request.POST.get('has_projector') == 'on'
                    meeting_room.has_whiteboard = request.POST.get('has_whiteboard') == 'on'
                    meeting_room.has_video_conferencing = request.POST.get('has_video_conferencing') == 'on'
                    meeting_room.has_phone = request.POST.get('has_phone') == 'on'
                    meeting_room.has_smart_tv = request.POST.get('has_smart_tv') == 'on'
                    meeting_room.has_audio_system = request.POST.get('has_audio_system') == 'on'
                    meeting_room.has_wifi = request.POST.get('has_wifi') == 'on'
                    meeting_room.has_air_conditioning = request.POST.get('has_air_conditioning') == 'on'
                    meeting_room.is_accessible = request.POST.get('is_accessible') == 'on'
                    
                    # Room details
                    room_size = request.POST.get('room_size_sqft')
                    meeting_room.room_size_sqft = int(room_size) if room_size and room_size.strip() else None
                    meeting_room.natural_light = request.POST.get('natural_light') == 'on'
                    meeting_room.has_window = request.POST.get('has_window') == 'on'
                    
                    # Setup times with defaults
                    setup_time = request.POST.get('default_setup_time')
                    meeting_room.default_setup_time = int(setup_time) if setup_time and setup_time.strip() else 15
                    
                    teardown_time = request.POST.get('default_teardown_time')
                    meeting_room.default_teardown_time = int(teardown_time) if teardown_time and teardown_time.strip() else 15
                    
                    # Images
                    if request.POST.get('room_photo_clear'):
                        if meeting_room.room_photo:
                            meeting_room.room_photo.delete()
                            meeting_room.room_photo = None
                    if 'room_photo' in request.FILES:
                        meeting_room.room_photo = request.FILES['room_photo']
                    
                    if request.POST.get('floor_plan_clear'):
                        if meeting_room.floor_plan:
                            meeting_room.floor_plan.delete()
                            meeting_room.floor_plan = None
                    if 'floor_plan' in request.FILES:
                        meeting_room.floor_plan = request.FILES['floor_plan']
                    
                    # Notes
                    meeting_room.notes = request.POST.get('notes', '')
                    
                    # Amenities
                    if request.POST.getlist('amenities'):
                        meeting_room.amenities.set(request.POST.getlist('amenities'))
                    
                    # Set default capacity if none specified
                    if not any([meeting_room.seating_capacity, meeting_room.standing_capacity,
                               meeting_room.classroom_capacity, meeting_room.theater_capacity]):
                        meeting_room.seating_capacity = 1
                    
                    meeting_room.save()
                else:
                    # If checkbox is unchecked and meeting room exists, delete it
                    if resource.is_meeting_room():
                        meeting_room = resource.meeting_room
                        # Delete associated images if they exist
                        if meeting_room.room_photo:
                            meeting_room.room_photo.delete()
                        if meeting_room.floor_plan:
                            meeting_room.floor_plan.delete()
                        meeting_room.delete()
                        messages.info(request, 'Meeting room features have been removed.')
                
                messages.success(request, f'Resource "{resource.name}" updated successfully!')
                return redirect('bookings:my_resources')
            except Exception as e:
                messages.error(request, f'Error updating resource: {str(e)}')
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f'Edit resource error: {e}', exc_info=True)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ResourceForm(instance=resource)
        if resource.is_meeting_room():
            meeting_room_form = MeetingRoomForm(instance=resource.meeting_room)
    
    context = {
        'form': form,
        'resource': resource,
        'meeting_room_form': meeting_room_form,
        'title': 'Edit Resource',
    }
    return render(request, 'bookings/resource_form.html', context)

@login_required
def delete_resource(request, resource_id):
    """View for users to delete their own resources"""
    resource = get_object_or_404(Resource, id=resource_id)
    
    if resource.owner != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to delete this resource.')
        return redirect('bookings:my_resources')  # ✅ Fixed with namespace
    
    bookings = Booking.objects.filter(resource=resource, status__in=['PENDING', 'CONFIRMED'])
    if bookings.exists():
        messages.error(request, f'Cannot delete "{resource.name}" because it has active bookings.')
        return redirect('bookings:my_resources')  # ✅ Fixed with namespace
    
    if request.method == 'POST':
        resource_name = resource.name
        try:
            resource.delete()
            messages.success(request, f'Resource "{resource_name}" deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting resource: {str(e)}')
        return redirect('bookings:my_resources')  # ✅ Fixed with namespace
    
    return render(request, 'bookings/resource_confirm_delete.html', {'resource': resource})

# ============ ADMIN RESOURCE MANAGEMENT VIEWS ============

@user_passes_test(lambda u: u.is_staff)
def admin_manage_resources(request):
    """Admin view to manage all resources"""
    resources = Resource.objects.all().order_by('-created_at', 'id')
    
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
            try:
                form.save()
                messages.success(request, f'Resource "{resource.name}" status updated to {resource.get_status_display()}.')
            except Exception as e:
                messages.error(request, f'Failed to update resource status: {str(e)}')
        else:
            messages.error(request, 'Failed to update resource status.')
    
    return redirect('bookings:admin_manage_resources')  # ✅ Fixed with namespace

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
            try:
                form.save()
                messages.success(request, 'Category created successfully!')
                return redirect('bookings:manage_categories')  # ✅ Fixed with namespace
            except Exception as e:
                messages.error(request, f'Error creating category: {str(e)}')
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
            try:
                form.save()
                messages.success(request, 'Category updated successfully!')
                return redirect('bookings:manage_categories')  # ✅ Fixed with namespace
            except Exception as e:
                messages.error(request, f'Error updating category: {str(e)}')
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
        return redirect('bookings:manage_categories')  # ✅ Fixed with namespace
    
    if request.method == 'POST':
        category_name = category.name
        try:
            category.delete()
            messages.success(request, f'Category "{category_name}" deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting category: {str(e)}')
        return redirect('bookings:manage_categories')  # ✅ Fixed with namespace
    
    return render(request, 'bookings/category_confirm_delete.html', {'category': category})

# ============ BOOKING MANAGEMENT VIEWS ============

@login_required
def my_bookings(request):
    """Show the current user's bookings with enhanced filtering and pagination"""
    all_bookings = Booking.objects.filter(customer=request.user).order_by('-start_time', '-created_at')
    
    status_filter = request.GET.get('status', 'all')
    date_filter = request.GET.get('date', 'all')
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', '-start_time')
    
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
    else:
        bookings = all_bookings
    
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
    
    if search_query and len(search_query) >= 2:
        bookings = bookings.filter(
            Q(resource__name__icontains=search_query) |
            Q(resource__description__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
    
    if sort_by == 'start_time':
        bookings = bookings.order_by('start_time', 'id')
    elif sort_by == 'end_time':
        bookings = bookings.order_by('end_time', 'id')
    elif sort_by == 'resource':
        bookings = bookings.order_by('resource__name', 'id')
    elif sort_by == 'status':
        bookings = bookings.order_by('status', 'id')
    else:
        bookings = bookings.order_by('-start_time', '-created_at')
    
    paginator = Paginator(bookings, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
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
    
    upcoming_bookings = all_bookings.filter(
        start_time__gte=timezone.now(),
        status__in=['PENDING', 'CONFIRMED']
    ).order_by('start_time', 'id')[:3]
    
    booking_data = []
    for booking in page_obj:
        booking_data.append({
            'booking': booking,
            'resource': booking.resource,
            'category': booking.resource.category,
            'meeting_room': booking.resource.meeting_room if booking.resource.is_meeting_room() else None,
            'amenities': booking.resource.meeting_room.amenities.all() if booking.resource.is_meeting_room() else None,
            'has_image': booking.resource.has_image(),
            'image_url': booking.resource.get_image_url(),
        })
    
    context = {
        'bookings': page_obj,
        'booking_data': booking_data,
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
        try:
            booking.status = 'CANCELLED'
            booking.save()
            messages.success(request, 'Booking cancelled successfully.')
        except Exception as e:
            messages.error(request, f'Error cancelling booking: {str(e)}')
    
    return redirect('bookings:my_bookings')  # ✅ Fixed with namespace

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
            
            is_past_slot = slot_start < now
            
            is_booked = Booking.objects.filter(
                resource=resource,
                start_time__lt=slot_end,
                end_time__gt=slot_start,
                status__in=['PENDING', 'CONFIRMED']
            ).exists()
            
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
        
        with transaction.atomic():
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

# ============ USER PROFILE VIEWS ============

@login_required
def profile(request, user_id=None):
    """View for user profile with booking history"""
    if user_id:
        if not request.user.is_staff:
            messages.error(request, 'You do not have permission to view this profile.')
            return redirect('profile')
        user = get_object_or_404(User, id=user_id)
    else:
        user = request.user
    
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created and user == request.user:
        messages.info(request, "Your profile was created automatically.")
    
    bookings = Booking.objects.filter(customer=user).order_by('-created_at', '-id')
    stats = profile.get_booking_stats()
    recent_bookings = bookings[:10]
    
    upcoming_bookings = bookings.filter(
        start_time__gte=timezone.now(),
        status__in=['PENDING', 'CONFIRMED']
    ).order_by('start_time', 'id')[:5]
    
    is_own_profile = (user == request.user)
    
    context = {
        'profile_user': user,
        'profile': profile,
        'stats': stats,
        'recent_bookings': recent_bookings,
        'upcoming_bookings': upcoming_bookings,
        'now': timezone.now(),
        'is_own_profile': is_own_profile,
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
            try:
                user_form.save()
                profile_form.save()
                messages.success(request, 'Your profile has been updated successfully!')
                return redirect('bookings:profile')  # ✅ Fixed with namespace
            except Exception as e:
                messages.error(request, f'Error updating profile: {str(e)}')
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
            try:
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your password has been changed successfully!')
                return redirect('bookings:profile')  # ✅ Fixed with namespace
            except Exception as e:
                messages.error(request, f'Error changing password: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PasswordChangeForm(user=request.user)
    
    return render(request, 'bookings/change_password.html', {'form': form})

@login_required
def booking_history(request):
    """View for full booking history with filters"""
    bookings = Booking.objects.filter(customer=request.user).order_by('-start_time', '-created_at')
    
    status_filter = request.GET.get('status', 'all')
    date_filter = request.GET.get('date', 'all')
    search_query = request.GET.get('search', '').strip()
    
    if status_filter != 'all':
        bookings = bookings.filter(status=status_filter)
    
    now = timezone.now()
    if date_filter == 'upcoming':
        bookings = bookings.filter(start_time__gte=now, status__in=['PENDING', 'CONFIRMED'])
    elif date_filter == 'past':
        bookings = bookings.filter(start_time__lt=now)
    elif date_filter == 'this_month':
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        bookings = bookings.filter(start_time__gte=month_start)
    
    if search_query and len(search_query) >= 2:
        bookings = bookings.filter(
            models.Q(resource__name__icontains=search_query) |
            models.Q(resource__description__icontains=search_query)
        )
    
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

# ============ CALENDAR VIEW ============

class CalendarView(TemplateView):
    """Calendar view showing resource availability with direct booking"""
    template_name = 'bookings/calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        year = int(self.request.GET.get('year', timezone.now().year))
        month = int(self.request.GET.get('month', timezone.now().month))
        
        resource_id = self.request.GET.get('resource')
        selected_date = self.request.GET.get('date')
        
        if self.request.user.is_staff:
            resources = Resource.objects.all().order_by('name', 'id')
        else:
            resources = Resource.objects.filter(status='APPROVED').order_by('name', 'id')
        
        selected_resource = None
        if resource_id:
            try:
                selected_resource = resources.get(id=resource_id)
            except Resource.DoesNotExist:
                pass
        
        calendar_data = self.build_calendar_data(year, month, selected_resource)
        
        time_slots = []
        selected_date_obj = None
        if selected_date:
            try:
                selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
                time_slots = self.get_time_slots_for_date(selected_date_obj, selected_resource)
            except ValueError:
                pass
        
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
        if date_obj < timezone.now().date():
            return {
                'available_count': 0,
                'total_slots': 0,
                'is_fully_booked': True,
                'is_past': True
            }
        
        start_hour = 9
        end_hour = 17
        total_slots = end_hour - start_hour
        available_count = 0
        
        if resource:
            resources_list = [resource]
        else:
            resources_list = Resource.objects.filter(status='APPROVED')
        
        for hour in range(start_hour, end_hour):
            slot_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time().replace(hour=hour)))
            slot_end = slot_start + timedelta(hours=1)
            
            is_available = False
            for res in resources_list:
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
        now = timezone.now()
        slots = []
        start_hour = 9
        end_hour = 17
        
        if resource:
            resources_list = [resource]
        else:
            resources_list = Resource.objects.filter(status='APPROVED')
        
        for hour in range(start_hour, end_hour):
            slot_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time().replace(hour=hour)))
            slot_end = slot_start + timedelta(hours=1)
            
            is_past = slot_start < now
            
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
        try:
            if request.content_type and 'application/json' in request.content_type:
                data = json.loads(request.body)
            else:
                data = {
                    'resource_id': request.POST.get('resource_id'),
                    'start_time': request.POST.get('start_time'),
                    'end_time': request.POST.get('end_time'),
                    'notes': request.POST.get('notes', ''),
                }
            
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
            
            existing_booking = Booking.objects.filter(
                resource_id=resource_id,
                start_time=start_time,
                end_time=end_time
            ).exists()
            
            if existing_booking:
                return JsonResponse({
                    'error': 'This time slot is already booked. Please select another slot.'
                }, status=400)
            
            with transaction.atomic():
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
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except ValidationError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# ============ CUSTOM LOGOUT ============

def custom_logout(request):
    """Custom logout view that allows GET requests"""
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('/')

# ============ REVIEW VIEWS ============

@login_required
def write_review(request, resource_id):
    """View for writing a review"""
    resource = get_object_or_404(Resource, id=resource_id)
    
    existing_review = Review.objects.filter(user=request.user, resource=resource).first()
    if existing_review:
        messages.warning(request, 'You have already reviewed this resource.')
        return redirect('bookings:edit_review', review_id=existing_review.id)  # ✅ Fixed with namespace
    
    has_booked = Booking.objects.filter(
        customer=request.user,
        resource=resource,
        status='CONFIRMED'
    ).exists()
    
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            try:
                review = form.save(commit=False)
                review.user = request.user
                review.resource = resource
                review.is_verified = has_booked
                review.status = 'PENDING'
                
                booking = Booking.objects.filter(
                    customer=request.user,
                    resource=resource,
                    status='CONFIRMED'
                ).first()
                if booking:
                    review.booking = booking
                
                review.save()
                send_review_submitted_email(review)
                
                messages.success(request, 'Your review has been submitted and is awaiting admin approval.')
                return redirect('bookings:resource_detail', resource_id=resource.id)  # ✅ Fixed with namespace
            except Exception as e:
                messages.error(request, f'Error submitting review: {str(e)}')
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
        return redirect('bookings:resource_detail', resource_id=review.resource.id)  # ✅ Fixed
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            try:
                review = form.save(commit=False)
                if review.status == 'REJECTED':
                    review.status = 'PENDING'
                review.save()
                messages.success(request, 'Your review has been updated successfully.')
                return redirect('bookings:resource_detail', resource_id=review.resource.id)  # ✅ Fixed
            except Exception as e:
                messages.error(request, f'Error updating review: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
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
        try:
            resource_id = review.resource.id
            review.delete()
            messages.success(request, 'Your review has been deleted.')
            return redirect('bookings:resource_detail', resource_id=resource_id)  # ✅ Fixed
        except Exception as e:
            messages.error(request, f'Error deleting review: {str(e)}')
    
    return render(request, 'bookings/delete_review.html', {'review': review})

@login_required
def my_reviews(request):
    """View for user's reviews"""
    reviews = Review.objects.filter(user=request.user).order_by('-created_at', '-id')
    
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        reviews = reviews.filter(status=status_filter)
    
    # Counts for stats
    all_reviews = Review.objects.filter(user=request.user)
    approved_count = all_reviews.filter(status='APPROVED').count()
    pending_count = all_reviews.filter(status='PENDING').count()
    rejected_count = all_reviews.filter(status='REJECTED').count()
    
    context = {
        'reviews': reviews,
        'status_filter': status_filter,
        'approved_count': approved_count,
        'pending_count': pending_count,
        'rejected_count': rejected_count,
    }
    return render(request, 'bookings/my_reviews.html', context)

@login_required
def resource_reviews(request, resource_id):
    """View for all reviews of a resource"""
    resource = get_object_or_404(Resource, id=resource_id)
    reviews = resource.reviews.filter(status='APPROVED').order_by('-created_at', '-id')
    
    filter_form = ReviewFilterForm(request.GET or None)
    if filter_form.is_valid():
        if rating := filter_form.cleaned_data.get('rating'):
            reviews = reviews.filter(rating=rating)
        
        sort = filter_form.cleaned_data.get('sort', 'newest')
        if sort == 'newest':
            reviews = reviews.order_by('-created_at', '-id')
        elif sort == 'oldest':
            reviews = reviews.order_by('created_at', 'id')
        elif sort == 'highest':
            reviews = reviews.order_by('-rating', '-created_at')
        elif sort == 'lowest':
            reviews = reviews.order_by('rating', '-created_at')
        elif sort == 'helpful':
            reviews = reviews.order_by('-helpful_count', '-created_at')
    
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
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
        try:
            review.toggle_helpful(request.user)
            return JsonResponse({
                'helpful_count': review.helpful_count,
                'is_helpful': review.is_helpful(request.user)
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@login_required
def my_review_history(request):
    """View for user's review history"""
    reviews = Review.objects.filter(user=request.user).order_by('-created_at', '-id')
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

# ============ ADMIN REVIEW VIEWS ============

@staff_member_required
def admin_reviews(request):
    """Admin view for managing all reviews"""
    reviews = Review.objects.all().order_by('-created_at', '-id')
    
    status_filter = request.GET.get('status', 'all')
    rating_filter = request.GET.get('rating', 'all')
    search_query = request.GET.get('search', '').strip()
    
    if status_filter != 'all':
        reviews = reviews.filter(status=status_filter)
    
    if rating_filter != 'all':
        reviews = reviews.filter(rating=rating_filter)
    
    if search_query and len(search_query) >= 2:
        reviews = reviews.filter(
            Q(comment__icontains=search_query) |
            Q(title__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(resource__name__icontains=search_query)
        )
    
    paginator = Paginator(reviews, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    total = Review.objects.count()
    pending = Review.objects.filter(status='PENDING').count()
    approved = Review.objects.filter(status='APPROVED').count()
    rejected = Review.objects.filter(status='REJECTED').count()
    
    resources = Resource.objects.filter(reviews__isnull=False).distinct().order_by('name')
    
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
        
        try:
            if action == 'approve':
                review.moderate('APPROVED', request.user, None)
                messages.success(request, f'Review #{review.id} has been approved.')
                send_review_approved_email(review)
                
            elif action == 'reject':
                if not reason:
                    messages.error(request, 'Please provide a reason for rejection.')
                    return redirect('bookings:admin_review_detail', review_id=review.id)
                review.moderate('REJECTED', request.user, reason)
                messages.success(request, f'Review #{review.id} has been rejected.')
                send_review_rejected_email(review)
                
            elif action == 'reject-approved':
                if not reason:
                    messages.error(request, 'Please provide a reason for rejection.')
                    return redirect('bookings:admin_review_detail', review_id=review.id)
                review.moderate('REJECTED', request.user, reason)
                messages.success(request, f'Review #{review.id} has been rejected and removed from public view.')
                send_review_rejected_email(review)
                
            elif action == 'delete':
                review.delete()
                messages.success(request, 'Review has been deleted.')
                return redirect('bookings:admin_reviews')
                
        except Exception as e:
            messages.error(request, f'Error processing review: {str(e)}')
        
        return redirect('bookings:admin_reviews')
    
    context = {
        'review': review,
        'review_status_choices': Review.STATUS_CHOICES,
    }
    return render(request, 'bookings/admin/admin_review_detail.html', context)

@staff_member_required
def admin_bulk_action_reviews(request):
    """Bulk action for reviews"""
    if request.method != 'POST':
        return redirect('bookings:admin_reviews')  # ✅ Fixed
    
    review_ids = request.POST.getlist('review_ids')
    action = request.POST.get('action')
    reason = request.POST.get('moderation_reason', '')
    
    if not review_ids:
        messages.error(request, 'No reviews selected.')
        return redirect('bookings:admin_reviews')  # ✅ Fixed
    
    reviews = Review.objects.filter(id__in=review_ids)
    count = reviews.count()
    
    try:
        if action == 'approve':
            for review in reviews:
                review.moderate('APPROVED', request.user, None)
                send_review_approved_email(review)
            messages.success(request, f'{count} reviews have been approved.')
            
        elif action == 'reject':
            if not reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return redirect('bookings:admin_reviews')  # ✅ Fixed
            for review in reviews:
                review.moderate('REJECTED', request.user, reason)
                send_review_rejected_email(review)
            messages.success(request, f'{count} reviews have been rejected.')
            
        elif action == 'delete':
            for review in reviews:
                review.delete()
            messages.success(request, f'{count} reviews have been deleted.')
            
        else:
            messages.error(request, 'Invalid action selected.')
            
    except Exception as e:
        messages.error(request, f'Error performing bulk action: {str(e)}')
    
    return redirect('bookings:admin_reviews')  # ✅ Fixed

# ============ EQUIPMENT RENTAL VIEWS ============

@login_required
def equipment_list(request):
    """List all equipment with filtering and pagination"""
    equipment_list = Equipment.objects.all().order_by('-created_at', 'id')
    
    status_filter = request.GET.get('status')
    if status_filter:
        equipment_list = equipment_list.filter(status=status_filter)
    
    category_filter = request.GET.get('category')
    if category_filter:
        equipment_list = equipment_list.filter(category_id=category_filter)

    owner_filter = request.GET.get('owner')
    if owner_filter:
        equipment_list = equipment_list.filter(owner_id=owner_filter)
    
    search_query = request.GET.get('search', '').strip()
    if search_query and len(search_query) >= 2:
        equipment_list = equipment_list.filter(
            models.Q(name__icontains=search_query) |
            models.Q(serial_number__icontains=search_query) |
            models.Q(asset_tag__icontains=search_query)
        )
    
    paginator = Paginator(equipment_list, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    total_equipment = Equipment.objects.count()
    available_count = Equipment.objects.filter(status='AVAILABLE').count()
    rented_count = Equipment.objects.filter(status='RENTED').count()
    maintenance_count = Equipment.objects.filter(status='MAINTENANCE').count()
    
    context = {
        'equipment_list': page_obj,
        'status_choices': Equipment.STATUS_CHOICES,
        'categories': EquipmentCategory.objects.all().order_by('name'),
        'current_status': status_filter,
        'current_category': category_filter,
        'search_query': search_query,
        'total_equipment': total_equipment,
        'available_count': available_count,
        'rented_count': rented_count,
        'maintenance_count': maintenance_count,
    }
    return render(request, 'bookings/equipment_list.html', context)

@login_required
def equipment_detail(request, equipment_id):
    """Show equipment details and rental history"""
    equipment = get_object_or_404(Equipment, id=equipment_id)
    
    recently_viewed = request.session.get('recently_viewed_equipment', [])
    if equipment_id not in recently_viewed:
        recently_viewed.insert(0, equipment_id)
        recently_viewed = recently_viewed[:10]
        request.session['recently_viewed_equipment'] = recently_viewed
    
    rentals = equipment.rentals.all().order_by('-checkout_date', '-id')[:10]
    maintenance_records = equipment.maintenance_records.all().order_by('-scheduled_date', '-id')[:10]
    
    context = {
        'equipment': equipment,
        'rentals': rentals,
        'maintenance_records': maintenance_records,
    }
    return render(request, 'bookings/equipment_detail.html', context)

@login_required
def rent_equipment(request):
    """Handle equipment checkout via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    equipment_id = request.POST.get('equipment_id')
    expected_return_date_str = request.POST.get('expected_return_date')
    condition_notes = request.POST.get('condition_notes', '')
    
    if not equipment_id or not expected_return_date_str:
        return JsonResponse({'error': 'Missing required fields'}, status=400)
    
    try:
        expected_return_date = timezone.datetime.fromisoformat(expected_return_date_str)
        if timezone.is_naive(expected_return_date):
            expected_return_date = timezone.make_aware(expected_return_date)
        
        with transaction.atomic():
            rental = EquipmentService.check_out_equipment(
                equipment_id=equipment_id,
                user_id=request.user.id,
                expected_return_date=expected_return_date,
                condition_notes=condition_notes
            )
        
        try:
            from .services.notification_service import NotificationService
            NotificationService.send_rental_confirmation(rental)
        except Exception as e:
            print(f"Notification error: {e}")
        
        return JsonResponse({
            'success': True,
            'rental_id': rental.id,
            'message': f'Equipment successfully rented until {rental.expected_return_date.strftime("%Y-%m-%d %H:%M")}'
        })
    
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': 'An error occurred. Please try again.'}, status=500)

@login_required
def return_equipment(request):
    """Handle equipment check-in via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    rental_id = request.POST.get('rental_id')
    condition_notes = request.POST.get('condition_notes', '')
    
    if not rental_id:
        return JsonResponse({'error': 'Missing rental ID'}, status=400)
    
    try:
        rental = EquipmentRental.objects.get(id=rental_id)
        
        if rental.rented_by != request.user and not request.user.is_staff:
            return JsonResponse({'error': 'You do not have permission to return this equipment'}, status=403)
        
        if rental.status == 'CHECKED_IN':
            return JsonResponse({'error': 'This equipment has already been returned'}, status=400)
        
        with transaction.atomic():
            updated_rental = EquipmentService.check_in_equipment(
                rental_id=rental_id,
                user_id=request.user.id,
                condition_notes=condition_notes
            )
        
        return JsonResponse({
            'success': True,
            'message': 'Equipment successfully returned',
            'rental_id': updated_rental.id
        })
    
    except EquipmentRental.DoesNotExist:
        return JsonResponse({'error': 'Rental record not found'}, status=404)
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def my_rentals(request):
    """Show the current user's equipment rentals with statistics"""
    all_rentals = EquipmentRental.objects.filter(rented_by=request.user).order_by('-checkout_date', '-id')
    
    total_rentals = all_rentals.count()
    active_rentals = all_rentals.filter(status='CHECKED_OUT').count()
    returned_rentals = all_rentals.filter(status='CHECKED_IN').count()
    overdue_rentals = all_rentals.filter(
        status='CHECKED_OUT', 
        expected_return_date__lt=timezone.now()
    ).count()
    lost_rentals = all_rentals.filter(status='LOST').count()
    damaged_rentals = all_rentals.filter(status='DAMAGED').count()
    
    rentals = all_rentals
    
    status_filter = request.GET.get('status')
    if status_filter:
        if status_filter == 'OVERDUE':
            rentals = rentals.filter(
                status='CHECKED_OUT',
                expected_return_date__lt=timezone.now()
            )
        else:
            rentals = rentals.filter(status=status_filter)
    
    search_query = request.GET.get('search', '').strip()
    if search_query and len(search_query) >= 2:
        rentals = rentals.filter(
            models.Q(equipment__name__icontains=search_query) |
            models.Q(equipment__serial_number__icontains=search_query)
        )
    
    sort_by = request.GET.get('sort', '-checkout_date')
    if sort_by == 'checkout_date':
        rentals = rentals.order_by('checkout_date', 'id')
    elif sort_by == 'expected_return_date':
        rentals = rentals.order_by('expected_return_date', 'id')
    elif sort_by == 'equipment__name':
        rentals = rentals.order_by('equipment__name', 'id')
    else:
        rentals = rentals.order_by('-checkout_date', '-id')
    
    context = {
        'rentals': rentals,
        'total_rentals': total_rentals,
        'active_rentals': active_rentals,
        'returned_rentals': returned_rentals,
        'overdue_count': overdue_rentals,
        'lost_rentals': lost_rentals,
        'damaged_rentals': damaged_rentals,
        'current_status_filter': status_filter,
        'search_query': search_query,
        'sort_by': sort_by,
        'now': timezone.now(),
    }
    return render(request, 'bookings/my_rentals.html', context)

# ============ MAINTENANCE VIEWS ============

@login_required
def equipment_maintenance(request):
    """View for managing equipment maintenance"""
    if request.user.is_staff:
        equipment_list = Equipment.objects.all().order_by('name', 'id')
        maintenance_records = MaintenanceRecord.objects.all().order_by('-scheduled_date', '-id')[:50]
    else:
        equipment_list = Equipment.objects.filter(owner=request.user).order_by('name', 'id')
        maintenance_records = MaintenanceRecord.objects.filter(
            equipment__owner=request.user
        ).order_by('-scheduled_date', '-id')[:50]
    
    if request.method == 'POST':
        equipment_id = request.POST.get('equipment_id')
        maintenance_type = request.POST.get('maintenance_type')
        title = request.POST.get('title')
        description = request.POST.get('description')
        scheduled_date_str = request.POST.get('scheduled_date')
        cost = request.POST.get('cost')
        vendor = request.POST.get('vendor', '')
        
        # Validate equipment ownership
        equipment = get_object_or_404(Equipment, id=equipment_id)
        if not request.user.is_staff and equipment.owner != request.user:
            messages.error(request, 'You do not have permission to schedule maintenance for this equipment.')
            return redirect('bookings:equipment_maintenance')  # ✅ Fixed with namespace
        
        if all([equipment_id, maintenance_type, title, description, scheduled_date_str]):
            try:
                scheduled_date = timezone.datetime.strptime(scheduled_date_str, '%Y-%m-%d').date()
                
                with transaction.atomic():
                    maintenance = EquipmentService.schedule_maintenance(
                        equipment_id=equipment_id,
                        maintenance_type=maintenance_type,
                        title=title,
                        description=description,
                        scheduled_date=scheduled_date,
                        user_id=request.user.id,
                        cost=cost if cost else None,
                        vendor=vendor
                    )
                
                # Send notification
                try:
                    from .services.notification_service import NotificationService
                    NotificationService.send_maintenance_scheduled(maintenance)
                except Exception as e:
                    print(f"Notification error: {e}")
                
                messages.success(request, f'Maintenance scheduled for {maintenance.equipment.name}')
                return redirect('bookings:equipment_maintenance')  # ✅ Fixed with namespace
            
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'An error occurred: {str(e)}')
        else:
            messages.error(request, 'Please fill in all required fields')
    
    # Calculate maintenance statistics
    if request.user.is_staff:
        total_records = MaintenanceRecord.objects.count()
        scheduled_count = MaintenanceRecord.objects.filter(status='SCHEDULED').count()
        in_progress_count = MaintenanceRecord.objects.filter(status='IN_PROGRESS').count()
        completed_count = MaintenanceRecord.objects.filter(status='COMPLETED').count()
        cancelled_count = MaintenanceRecord.objects.filter(status='CANCELLED').count()
    else:
        user_equipment_ids = Equipment.objects.filter(owner=request.user).values_list('id', flat=True)
        total_records = MaintenanceRecord.objects.filter(equipment__id__in=user_equipment_ids).count()
        scheduled_count = MaintenanceRecord.objects.filter(
            equipment__id__in=user_equipment_ids,
            status='SCHEDULED'
        ).count()
        in_progress_count = MaintenanceRecord.objects.filter(
            equipment__id__in=user_equipment_ids,
            status='IN_PROGRESS'
        ).count()
        completed_count = MaintenanceRecord.objects.filter(
            equipment__id__in=user_equipment_ids,
            status='COMPLETED'
        ).count()
        cancelled_count = MaintenanceRecord.objects.filter(
            equipment__id__in=user_equipment_ids,
            status='CANCELLED'
        ).count()
    
    context = {
        'equipment_list': equipment_list,
        'maintenance_records': maintenance_records,
        'maintenance_types': MaintenanceRecord.MAINTENANCE_TYPES,
        'total_records': total_records,
        'scheduled_count': scheduled_count,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'cancelled_count': cancelled_count,
        'is_staff': request.user.is_staff,
    }
    return render(request, 'bookings/equipment_maintenance.html', context)

@login_required
def maintenance_detail(request, maintenance_id):
    """View for displaying a single maintenance record"""
    try:
        maintenance = MaintenanceRecord.objects.select_related(
            'equipment', 
            'equipment__owner', 
            'performed_by'
        ).get(id=maintenance_id)
    except MaintenanceRecord.DoesNotExist:
        messages.error(request, 'Maintenance record not found.')
        return redirect('bookings:equipment_maintenance')
    
    # Check if user can view this maintenance
    if not request.user.is_staff and maintenance.equipment.owner != request.user:
        messages.error(request, 'You do not have permission to view this maintenance record.')
        return redirect('bookings:equipment_maintenance')
    
    # Check if user can complete (staff or equipment owner)
    can_complete = (request.user.is_staff or maintenance.equipment.owner == request.user)
    
    # Check if user can edit (staff or equipment owner)
    can_edit = request.user.is_staff or maintenance.equipment.owner == request.user
    
    # Check if user is the owner
    is_owner = maintenance.equipment.owner == request.user
    
    context = {
        'maintenance': maintenance,
        'equipment': maintenance.equipment,
        'can_complete': can_complete,
        'can_edit': can_edit,
        'is_owner': is_owner,
    }
    return render(request, 'bookings/maintenance_detail.html', context)

@login_required
def complete_maintenance(request):
    """Handle completing maintenance via AJAX - Staff OR Equipment Owner"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    maintenance_id = request.POST.get('maintenance_id')
    notes = request.POST.get('notes', '')
    
    if not maintenance_id:
        return JsonResponse({'error': 'Missing maintenance ID'}, status=400)
    
    try:
        with transaction.atomic():
            maintenance = MaintenanceRecord.objects.select_for_update().get(id=maintenance_id)
            
            is_authorized = request.user.is_staff or maintenance.equipment.owner == request.user
            
            if not is_authorized:
                return JsonResponse({
                    'error': 'You do not have permission to complete this maintenance.'
                }, status=403)
            
            if maintenance.status == 'COMPLETED':
                return JsonResponse({'error': 'This maintenance is already completed'}, status=400)
            
            if maintenance.status == 'CANCELLED':
                return JsonResponse({'error': 'This maintenance has been cancelled'}, status=400)
            
            maintenance.status = 'COMPLETED'
            maintenance.completed_date = timezone.now().date()
            if notes:
                maintenance.notes = (maintenance.notes + '\n' + notes).strip() if maintenance.notes else notes
            maintenance.save()
            
            equipment = maintenance.equipment
            equipment.status = 'AVAILABLE'
            equipment.save()
            
            try:
                from .services.notification_service import NotificationService
                if maintenance.equipment.owner and maintenance.equipment.owner != request.user:
                    NotificationService.send_maintenance_completed(maintenance)
            except Exception as e:
                print(f"Notification error: {e}")
            
            completed_by = "You" if not request.user.is_staff else f"Staff ({request.user.username})"
            
            return JsonResponse({
                'success': True,
                'message': f'Maintenance for "{equipment.name}" completed successfully by {completed_by}!'
            })
    
    except MaintenanceRecord.DoesNotExist:
        return JsonResponse({'error': 'Maintenance record not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# ============ USER EQUIPMENT MANAGEMENT VIEWS ============

@login_required
def my_equipment(request):
    """View for users to see and manage their own equipment"""
    equipment_list = Equipment.objects.filter(owner=request.user).order_by('-created_at', 'id')
    
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        equipment_list = equipment_list.filter(status=status_filter)
    
    total = Equipment.objects.filter(owner=request.user).count()
    available = Equipment.objects.filter(owner=request.user, status='AVAILABLE').count()
    rented = Equipment.objects.filter(owner=request.user, status='RENTED').count()
    maintenance = Equipment.objects.filter(owner=request.user, status='MAINTENANCE').count()
    retired = Equipment.objects.filter(owner=request.user, status='RETIRED').count()
    lost = Equipment.objects.filter(owner=request.user, status='LOST').count()
    
    current_count = equipment_list.count()
    
    context = {
        'equipment_list': equipment_list,
        'total': total,
        'available': available,
        'rented': rented,
        'maintenance': maintenance,
        'retired': retired,
        'lost': lost,
        'current_filter': status_filter,
        'current_count': current_count,
        'status_choices': Equipment.STATUS_CHOICES,
    }
    return render(request, 'bookings/my_equipment.html', context)

@login_required
def create_equipment(request):
    """View for users to create new equipment"""
    if request.method == 'POST':
        form = EquipmentForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                equipment = form.save(commit=False)
                if not equipment.owner:
                    equipment.owner = request.user
                equipment.status = 'AVAILABLE'
                equipment.save()
                messages.success(request, f'Equipment "{equipment.name}" created successfully!')
                return redirect('bookings:my_equipment')  # ✅ Fixed with namespace
            except Exception as e:
                messages.error(request, f'Error creating equipment: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = EquipmentForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create Equipment',
        'button_text': 'Create Equipment',
    }
    return render(request, 'bookings/equipment_form.html', context)

@login_required
def edit_equipment(request, equipment_id):
    """View for users to edit their own equipment"""
    equipment = get_object_or_404(Equipment, id=equipment_id)
    
    # Check ownership
    if equipment.owner != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to edit this equipment.')
        return redirect('bookings:my_equipment')  # ✅ Fixed with namespace
    
    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=equipment, user=request.user)
        if form.is_valid():
            try:
                equipment = form.save(commit=False)
                if not request.user.is_staff:
                    equipment.owner = Equipment.objects.get(id=equipment_id).owner
                equipment.save()
                messages.success(request, f'Equipment "{equipment.name}" updated successfully!')
                return redirect('bookings:my_equipment')  # ✅ Fixed with namespace
            except Exception as e:
                messages.error(request, f'Error updating equipment: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = EquipmentForm(instance=equipment, user=request.user)
    
    context = {
        'form': form,
        'equipment': equipment,
        'title': 'Edit Equipment',
        'button_text': 'Update Equipment',
    }
    return render(request, 'bookings/equipment_form.html', context)

@login_required
def delete_equipment(request, equipment_id):
    """View for users to delete their own equipment"""
    equipment = get_object_or_404(Equipment, id=equipment_id)
    
    # Check ownership
    if equipment.owner != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to delete this equipment.')
        return redirect('bookings:my_equipment')  # ✅ Fixed with namespace
    
    # Check if equipment is currently rented
    if equipment.status == 'RENTED':
        messages.error(request, f'Cannot delete "{equipment.name}" because it is currently rented.')
        return redirect('bookings:my_equipment')  # ✅ Fixed with namespace
    
    if request.method == 'POST':
        equipment_name = equipment.name
        try:
            equipment.delete()
            messages.success(request, f'Equipment "{equipment_name}" deleted successfully.')
        except Exception as e:
            messages.error(request, f'Error deleting equipment: {str(e)}')
        return redirect('bookings:my_equipment')  # ✅ Fixed with namespace
    
    context = {
        'equipment': equipment,
    }
    return render(request, 'bookings/equipment_confirm_delete.html', context)

@login_required
def equipment_dashboard(request):
    """User dashboard with equipment stats and quick actions"""
    owned_equipment = Equipment.objects.filter(owner=request.user)
    user_rentals = EquipmentRental.objects.filter(rented_by=request.user)
    
    total_owned = owned_equipment.count()
    available_count = owned_equipment.filter(status='AVAILABLE').count()
    rented_count = owned_equipment.filter(status='RENTED').count()
    maintenance_count = owned_equipment.filter(status='MAINTENANCE').count()
    
    active_rentals = user_rentals.filter(status='CHECKED_OUT')
    overdue_count = active_rentals.filter(
        expected_return_date__lt=timezone.now()
    ).count()
    total_rentals = user_rentals.count()
    
    recently_viewed_ids = request.session.get('recently_viewed_equipment', [])
    recently_viewed = Equipment.objects.filter(id__in=recently_viewed_ids).order_by('-created_at')[:5]
    
    quick_return_rentals = active_rentals.order_by('expected_return_date', 'id')[:5]
    
    upcoming_maintenance = MaintenanceRecord.objects.filter(
        equipment__owner=request.user,
        status='SCHEDULED',
        scheduled_date__gte=timezone.now().date()
    ).select_related('equipment').order_by('scheduled_date', 'id')[:5]
    
    recent_rentals = user_rentals.order_by('-checkout_date', '-id')[:3]
    recent_maintenance = MaintenanceRecord.objects.filter(
        equipment__owner=request.user
    ).order_by('-created_at', '-id')[:3]
    
    context = {
        'total_owned': total_owned,
        'available_count': available_count,
        'rented_count': rented_count,
        'maintenance_count': maintenance_count,
        'active_rentals_count': active_rentals.count(),
        'overdue_count': overdue_count,
        'total_rentals': total_rentals,
        'recently_viewed': recently_viewed,
        'quick_return_rentals': quick_return_rentals,
        'upcoming_maintenance': upcoming_maintenance,
        'recent_rentals': recent_rentals,
        'recent_maintenance': recent_maintenance,
        'status_choices': Equipment.STATUS_CHOICES,
    }
    
    return render(request, 'bookings/equipment_dashboard.html', context)

# ============ SEARCH VIEWS ============

@login_required
def equipment_search(request):
    """Advanced equipment search view"""
    search_data = SearchService.search_equipment(request)
    filter_options = SearchService.get_filter_options()
    
    search_query = request.GET.get('search', '').strip()
    suggestions = []
    if search_query and len(search_query) >= 2:
        suggestions = SearchService.get_search_suggestions(search_query)
    
    context = {
        'results': search_data['results'],
        'metadata': search_data['metadata'],
        'filter_options': filter_options,
        'suggestions': suggestions,
        'search_query': search_query,
        'selected_category': request.GET.get('category', ''),
        'selected_status': request.GET.get('status', ''),
        'selected_condition': request.GET.get('condition', ''),
        'selected_location': request.GET.get('location', ''),
        'min_price': request.GET.get('min_price', ''),
        'max_price': request.GET.get('max_price', ''),
        'start_date': request.GET.get('start_date', ''),
        'end_date': request.GET.get('end_date', ''),
        'sort_by': request.GET.get('sort', 'name'),
    }
    
    return render(request, 'bookings/equipment_search.html', context)

@login_required
def search_suggestions(request):
    """API endpoint for search autocomplete"""
    query = request.GET.get('q', '').strip()
    suggestions = SearchService.get_search_suggestions(query)
    return JsonResponse({'suggestions': suggestions})

@login_required
def save_search(request):
    """Save current search"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    search_name = request.POST.get('name', '').strip()
    if not search_name:
        return JsonResponse({'error': 'Search name is required'}, status=400)
    
    try:
        saved_search, created = SearchService.save_search(
            user=request.user,
            name=search_name,
            request=request
        )
        
        return JsonResponse({
            'success': True,
            'created': created,
            'search_id': saved_search.id,
            'message': f'Search "{search_name}" {"created" if created else "updated"} successfully!'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_saved_searches(request):
    """Get all saved searches for the user"""
    searches = SearchService.get_saved_searches(request.user)
    data = []
    for search in searches:
        data.append({
            'id': search.id,
            'name': search.name,
            'search_query': search.search_query,
            'filters': search.filters,
            'sort_by': search.sort_by,
            'per_page': search.per_page,
            'is_favorite': search.is_favorite,
            'created_at': search.created_at.strftime('%Y-%m-%d %H:%M'),
            'last_used': search.last_used.strftime('%Y-%m-%d %H:%M') if search.last_used else None,
            'url': search.get_search_url(),
        })
    return JsonResponse({'searches': data})

@login_required
def delete_saved_search(request, search_id):
    """Delete a saved search"""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        SearchService.delete_saved_search(request.user, search_id)
        return JsonResponse({'success': True, 'message': 'Search deleted successfully'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def toggle_search_favorite(request, search_id):
    """Toggle favorite status of a saved search"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        is_favorite = SearchService.toggle_favorite(request.user, search_id)
        return JsonResponse({
            'success': True,
            'is_favorite': is_favorite,
            'message': 'Favorite status updated'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def export_search_results(request):
    """Export search results"""
    format_type = request.GET.get('format', 'csv')
    
    response = SearchService.export_search_results(request)
    if response:
        return response
    
    return JsonResponse({'error': 'Invalid export format'}, status=400)

# ============ BOOKING EXPORT VIEWS ============

@login_required
def export_bookings(request):
    """Export bookings in various formats"""
    format_type = request.GET.get('format', 'csv')
    bookings = Booking.objects.filter(customer=request.user).order_by('-start_time', '-id')
    
    if format_type == 'csv':
        return export_bookings_csv(request, bookings)
    elif format_type == 'json':
        return export_bookings_json(request, bookings)
    elif format_type == 'pdf':
        return export_bookings_pdf(request, bookings)
    else:
        messages.error(request, 'Invalid export format')
        return redirect('my_bookings')

@login_required
def export_bookings_csv(request, bookings):
    """Export bookings as CSV"""
    response = HttpResponse(content_type='text/csv')
    filename = f"my_bookings_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    writer.writerow([
        'ID', 'Resource', 'Start Time', 'End Time', 'Duration (hours)', 
        'Status', 'Notes', 'Created At'
    ])
    
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

@login_required
def export_bookings_json(request, bookings):
    """Export bookings as JSON"""
    data = []
    for booking in bookings:
        data.append({
            'id': booking.id,
            'resource': booking.resource.name,
            'start_time': booking.start_time.isoformat(),
            'end_time': booking.end_time.isoformat(),
            'duration_hours': booking.get_duration(),
            'status': booking.get_status_display(),
            'status_code': booking.status,
            'notes': booking.notes or '',
            'created_at': booking.created_at.isoformat(),
        })
    
    response = HttpResponse(
        json.dumps(data, indent=2),
        content_type='application/json'
    )
    filename = f"my_bookings_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
def export_bookings_pdf(request, bookings):
    """Export bookings as PDF"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
    except ImportError:
        return export_bookings_csv(request, bookings)
    
    response = HttpResponse(content_type='application/pdf')
    filename = f"my_bookings_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(A4))
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    
    elements.append(Paragraph(f"My Bookings - {request.user.username}", title_style))
    elements.append(Paragraph(f"Generated on {timezone.now().strftime('%B %d, %Y at %H:%M')}", styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    
    stats = f"Total Bookings: {bookings.count()} | Upcoming: {bookings.filter(start_time__gte=timezone.now(), status__in=['PENDING', 'CONFIRMED']).count()} | Completed: {bookings.filter(status='COMPLETED').count()}"
    elements.append(Paragraph(stats, styles['Normal']))
    elements.append(Spacer(1, 0.1*inch))
    
    data = [['ID', 'Resource', 'Start Time', 'End Time', 'Duration', 'Status', 'Notes']]
    
    for booking in bookings[:50]:
        data.append([
            str(booking.id),
            booking.resource.name[:25],
            booking.start_time.strftime('%Y-%m-%d %H:%M'),
            booking.end_time.strftime('%Y-%m-%d %H:%M'),
            f"{booking.get_duration()}h",
            booking.get_status_display(),
            booking.notes[:30] if booking.notes else ''
        ])
    
    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(table)
    doc.build(elements)
    return response

# ============ RESERVATION VIEWS ============

@login_required
def reservation_list(request):
    """View all reservations"""
    if request.user.is_staff:
        reservations = EquipmentReservation.objects.all().order_by('-created_at', '-id')
    else:
        owned_equipment_ids = Equipment.objects.filter(owner=request.user).values_list('id', flat=True)
        reservations = EquipmentReservation.objects.filter(
            Q(user=request.user) | Q(equipment__owner=request.user)
        ).order_by('-created_at', '-id').distinct()
    
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        reservations = reservations.filter(status=status_filter)
    
    if request.user.is_staff:
        total = EquipmentReservation.objects.count()
        pending = EquipmentReservation.objects.filter(status='PENDING').count()
        confirmed = EquipmentReservation.objects.filter(status='CONFIRMED').count()
        cancelled = EquipmentReservation.objects.filter(status='CANCELLED').count()
        expired = EquipmentReservation.objects.filter(status='EXPIRED').count()
        completed = EquipmentReservation.objects.filter(status='COMPLETED').count()
    else:
        total = reservations.count()
        pending = reservations.filter(status='PENDING').count()
        confirmed = reservations.filter(status='CONFIRMED').count()
        cancelled = reservations.filter(status='CANCELLED').count()
        expired = reservations.filter(status='EXPIRED').count()
        completed = reservations.filter(status='COMPLETED').count()
    
    context = {
        'reservations': reservations,
        'status_filter': status_filter,
        'status_choices': EquipmentReservation.STATUS_CHOICES,
        'total': total,
        'pending': pending,
        'confirmed': confirmed,
        'cancelled': cancelled,
        'expired': expired,
        'completed': completed,
        'is_staff': request.user.is_staff,
        'is_equipment_owner': not request.user.is_staff,
    }
    return render(request, 'bookings/reservations/list.html', context)

@login_required
def create_reservation(request):
    """Create a new reservation"""
    if request.method == 'POST':
        equipment_id = request.POST.get('equipment_id')
        start_date_str = request.POST.get('start_date')
        end_date_str = request.POST.get('end_date')
        purpose = request.POST.get('purpose', '')
        notes = request.POST.get('notes', '')
        
        if not all([equipment_id, start_date_str, end_date_str]):
            messages.error(request, 'Please fill in all required fields')
            return redirect('bookings:create_reservation')  # ✅ Fixed
        
        try:
            start_date = timezone.datetime.fromisoformat(start_date_str)
            end_date = timezone.datetime.fromisoformat(end_date_str)
            
            if timezone.is_naive(start_date):
                start_date = timezone.make_aware(start_date)
            if timezone.is_naive(end_date):
                end_date = timezone.make_aware(end_date)
            
            with transaction.atomic():
                reservation = ReservationService.create_reservation(
                    equipment_id=equipment_id,
                    user=request.user,
                    start_date=start_date,
                    end_date=end_date,
                    purpose=purpose,
                    notes=notes
                )
            
            messages.success(request, f'Reservation created for {reservation.equipment.name}')
            return redirect('bookings:reservation_detail', reservation_id=reservation.id)  # ✅ Fixed with namespace
        
        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    default_start = timezone.now() + timedelta(days=1)
    default_end = default_start + timedelta(days=1)
    
    available_equipment = ReservationService.get_available_equipment(
        default_start, default_end
    )
    
    context = {
        'available_equipment': available_equipment,
        'default_start': default_start,
        'default_end': default_end,
        'all_equipment': Equipment.objects.filter(status__in=['AVAILABLE', 'RENTED']).order_by('name', 'id'),
    }
    return render(request, 'bookings/reservations/create.html', context)

@login_required
def reservation_detail(request, reservation_id):
    """View reservation details"""
    reservation = get_object_or_404(EquipmentReservation, id=reservation_id)
    
    can_view = (
        request.user.is_staff or 
        reservation.user == request.user or 
        reservation.equipment.owner == request.user
    )
    
    if not can_view:
        messages.error(request, 'You do not have permission to view this reservation')
        return redirect('bookings:reservation_list')  # ✅ Fixed with namespace
    
    can_confirm = (
        (request.user.is_staff or reservation.equipment.owner == request.user) and 
        reservation.status == 'PENDING'
    )
    
    can_cancel = reservation.can_cancel() and (
        request.user.is_staff or 
        reservation.user == request.user or 
        reservation.equipment.owner == request.user
    )
    
    context = {
        'reservation': reservation,
        'can_cancel': can_cancel,
        'can_confirm': can_confirm,
        'is_staff': request.user.is_staff,
        'is_owner': reservation.equipment.owner == request.user,
        'is_reserver': reservation.user == request.user,
    }
    return render(request, 'bookings/reservations/detail.html', context)

@login_required
def cancel_reservation_view(request, reservation_id):
    """Cancel a reservation"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        with transaction.atomic():
            reservation = EquipmentReservation.objects.select_for_update().get(id=reservation_id)
            
            is_authorized = (
                request.user.is_staff or 
                reservation.user == request.user or 
                reservation.equipment.owner == request.user
            )
            
            if not is_authorized:
                messages.error(request, 'You do not have permission to cancel this reservation.')
                return redirect('bookings:reservation_detail', reservation_id=reservation_id)  # ✅ Fixed
            
            if not reservation.can_cancel():
                messages.error(request, f'Cannot cancel reservation with status: {reservation.get_status_display()}')
                return redirect('bookings:reservation_detail', reservation_id=reservation_id)  # ✅ Fixed
            
            reservation.cancel()
            
            try:
                from .services.notification_service import NotificationService
                NotificationService.send_reservation_cancelled(reservation)
            except Exception as e:
                print(f"Notification error: {e}")
            
            messages.success(request, f'Reservation for {reservation.equipment.name} cancelled successfully!')
            return redirect('bookings:reservation_list')  # ✅ Fixed
        
    except Exception as e:
        messages.error(request, str(e))
        return redirect('bookings:reservation_detail', reservation_id=reservation_id)  # ✅ Fixed

@login_required
def confirm_reservation_view(request, reservation_id):
    """Confirm a reservation (Staff OR Equipment Owner)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        with transaction.atomic():
            reservation = EquipmentReservation.objects.select_for_update().get(id=reservation_id)
            
            is_authorized = request.user.is_staff or reservation.equipment.owner == request.user
            
            if not is_authorized:
                messages.error(request, 'You do not have permission to confirm this reservation.')
                return redirect('bookings:reservation_detail', reservation_id=reservation_id)  # ✅ Fixed
            
            if reservation.status != 'PENDING':
                messages.error(request, f'Cannot confirm reservation with status: {reservation.get_status_display()}')
                return redirect('bookings:reservation_detail', reservation_id=reservation_id)  # ✅ Fixed
            
            if reservation.is_expired():
                messages.error(request, 'This reservation has expired')
                return redirect('bookings:reservation_detail', reservation_id=reservation_id)  # ✅ Fixed
            
            conflict = EquipmentReservation.objects.filter(
                equipment=reservation.equipment,
                start_date__lt=reservation.end_date,
                end_date__gt=reservation.start_date,
                status__in=['PENDING', 'CONFIRMED']
            ).exclude(id=reservation_id).exists()
            
            if conflict:
                messages.error(request, 'A conflicting reservation has been made since this was created')
                return redirect('bookings:reservation_detail', reservation_id=reservation_id)  # ✅ Fixed
            
            reservation.confirm()
            
            try:
                from .services.notification_service import NotificationService
                NotificationService.send_reservation_confirmed(reservation)
            except Exception as e:
                print(f"Notification error: {e}")
            
            messages.success(request, f'Reservation for {reservation.equipment.name} confirmed successfully!')
            return redirect('bookings:reservation_detail', reservation_id=reservation_id)  # ✅ Fixed
        
    except Exception as e:
        messages.error(request, str(e))
        return redirect('bookings:reservation_detail', reservation_id=reservation_id)  # ✅ Fixed

@login_required
def get_available_equipment_ajax(request):
    """AJAX endpoint to get available equipment for date range"""
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    if not start_date_str or not end_date_str:
        return JsonResponse({'error': 'Missing dates'}, status=400)
    
    try:
        start_date = timezone.datetime.fromisoformat(start_date_str)
        end_date = timezone.datetime.fromisoformat(end_date_str)
        
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
        if timezone.is_naive(end_date):
            end_date = timezone.make_aware(end_date)
        
        available = ReservationService.get_available_equipment(start_date, end_date)
        
        data = [{
            'id': eq.id,
            'name': eq.name,
            'serial_number': eq.serial_number,
            'status': eq.status,
            'condition': eq.condition,
            'category': eq.category.name if eq.category else None,
        } for eq in available]
        
        return JsonResponse({'equipment': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def reservation_calendar(request):
    """Calendar view for reservations"""
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    
    calendar_data = ReservationService.get_calendar_data(year, month)
    
    reservations = EquipmentReservation.objects.filter(
        start_date__year=year,
        start_date__month=month
    ).select_related('equipment', 'user').order_by('start_date', 'id')
    
    status_counts = {
        'PENDING': reservations.filter(status='PENDING').count(),
        'CONFIRMED': reservations.filter(status='CONFIRMED').count(),
        'CANCELLED': reservations.filter(status='CANCELLED').count(),
        'COMPLETED': reservations.filter(status='COMPLETED').count(),
        'EXPIRED': reservations.filter(status='EXPIRED').count(),
    }
    
    context = {
        'calendar_data': calendar_data,
        'reservations': reservations,
        'year': year,
        'month': month,
        'month_name': calendar_data['month_name'],
        'prev_month': month - 1 if month > 1 else 12,
        'prev_year': year if month > 1 else year - 1,
        'next_month': month + 1 if month < 12 else 1,
        'next_year': year if month < 12 else year + 1,
        'status_counts': status_counts,
        'status_choices': EquipmentReservation.STATUS_CHOICES,
    }
    return render(request, 'bookings/reservations/calendar.html', context)

@login_required
def export_single_booking_pdf(request, booking_id):
    """Export a single booking as PDF with full details"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Check permission: only customer, staff, or resource owner can export
    if booking.customer != request.user and not request.user.is_staff and booking.resource.owner != request.user:
        messages.error(request, 'You do not have permission to export this booking.')
        return redirect('bookings:my_bookings')
    
    response = HttpResponse(content_type='application/pdf')
    safe_name = booking.resource.name.replace('/', '_').replace(' ', '_')[:50]
    response['Content-Disposition'] = f'attachment; filename="booking_{booking.id}_{safe_name}.pdf"'
    
    doc = SimpleDocTemplate(response, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    title_style = styles['Title']
    elements.append(Paragraph("Booking Details", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    header_data = [
        ['Booking ID', f'#{booking.id}'],
        ['Resource', booking.resource.name],
        ['Customer', booking.customer.username],
        ['Status', booking.get_status_display()],
        ['Created', booking.created_at.strftime('%B %d, %Y at %H:%M')],
    ]
    header_table = Table(header_data, colWidths=[1.5*inch, 4*inch])
    header_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*inch))
    
    time_data = [
        ['Start Time', booking.start_time.strftime('%B %d, %Y at %H:%M')],
        ['End Time', booking.end_time.strftime('%B %d, %Y at %H:%M')],
        ['Duration', f'{booking.get_duration()} hours'],
    ]
    time_table = Table(time_data, colWidths=[1.5*inch, 4*inch])
    time_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(time_table)
    elements.append(Spacer(1, 0.2*inch))
    
    elements.append(Paragraph("Resource Information", styles['Heading2']))
    elements.append(Spacer(1, 0.1*inch))
    
    resource_data = [
        ['Name', booking.resource.name],
        ['Description', booking.resource.description or 'No description'],
        ['Category', booking.resource.category.name if booking.resource.category else 'Uncategorized'],
        ['Location', booking.resource.location or 'Not specified'],
        ['Max Capacity', str(booking.resource.max_capacity)],
        ['Price per Hour', f'${booking.resource.price_per_hour}' if booking.resource.price_per_hour else 'Free'],
        ['Owner', booking.resource.owner.username if booking.resource.owner else 'No owner'],
    ]
    resource_table = Table(resource_data, colWidths=[1.5*inch, 4*inch])
    resource_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(resource_table)
    elements.append(Spacer(1, 0.2*inch))
    
    if booking.resource.is_meeting_room():
        mr = booking.resource.meeting_room
        elements.append(Paragraph("Meeting Room Details", styles['Heading2']))
        elements.append(Spacer(1, 0.1*inch))
        
        room_data = [
            ['Room Number', mr.room_number or 'Not specified'],
            ['Building', mr.building_name or 'Not specified'],
            ['Floor', str(mr.floor_number)],
            ['Seating Capacity', str(mr.seating_capacity)],
            ['Features', ', '.join(mr.get_features_list()) or 'None'],
        ]
        room_table = Table(room_data, colWidths=[1.5*inch, 4*inch])
        room_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(room_table)
        elements.append(Spacer(1, 0.2*inch))
    
    if booking.notes:
        elements.append(Paragraph("Booking Notes", styles['Heading2']))
        elements.append(Paragraph(booking.notes, styles['Normal']))
    
    doc.build(elements)
    return response

@login_required
def export_single_booking_html(request, booking_id):
    """Export a single booking as HTML"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Check permission: only customer, staff, or resource owner can export
    if booking.customer != request.user and not request.user.is_staff and booking.resource.owner != request.user:
        messages.error(request, 'You do not have permission to export this booking.')
        return redirect('bookings:my_bookings')
    
    context = {
        'booking': booking,
        'resource': booking.resource,
        'category': booking.resource.category,
        'meeting_room': booking.resource.meeting_room if booking.resource.is_meeting_room() else None,
        'amenities': booking.resource.meeting_room.amenities.all() if booking.resource.is_meeting_room() else None,
        'now': timezone.now(),
    }
    
    html_content = render_to_string('bookings/booking_detail_export.html', context)
    
    response = HttpResponse(html_content, content_type='text/html')
    safe_name = booking.resource.name.replace('/', '_').replace(' ', '_')[:50]
    response['Content-Disposition'] = f'attachment; filename="booking_{booking.id}_{safe_name}.html"'
    return response

@login_required
def booking_detail(request, booking_id):
    """View full booking details"""
    booking = get_object_or_404(Booking, id=booking_id, customer=request.user)
    
    if booking.customer != request.user:
        messages.error(request, 'You do not have permission to view this booking.')
        return redirect('my_bookings')
    
    context = {
        'booking': booking,
        'resource': booking.resource,
        'category': booking.resource.category,
        'meeting_room': booking.resource.meeting_room if booking.resource.is_meeting_room() else None,
        'amenities': booking.resource.meeting_room.amenities.all() if booking.resource.is_meeting_room() else None,
        'has_image': booking.resource.has_image(),
        'image_url': booking.resource.get_image_url(),
        'can_cancel': booking.can_cancel(),
        'is_past': booking.is_past(),
        'is_upcoming': booking.is_upcoming(),
        'now': timezone.now(),
    }
    return render(request, 'bookings/booking_detail.html', context)


@login_required
def rental_detail(request, rental_id):
    """View for displaying a single rental record"""
    try:
        rental = EquipmentRental.objects.select_related('equipment', 'rented_by').get(id=rental_id)
    except EquipmentRental.DoesNotExist:
        messages.error(request, 'Rental record not found.')
        return redirect('my_rentals')
    
    # Check if user has permission to view this rental
    if rental.rented_by != request.user and not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this rental.')
        return redirect('my_rentals')
    
    # Check if user can return this equipment (staff or the renter)
    can_return = (
        request.user.is_staff or 
        rental.rented_by == request.user
    ) and rental.status == 'CHECKED_OUT'
    
    context = {
        'rental': rental,
        'equipment': rental.equipment,
        'can_return': can_return,
        'is_overdue': rental.is_overdue(),
        'days_rented': rental.days_rented(),
        'now': timezone.now(),
    }
    return render(request, 'bookings/rental_detail.html', context)