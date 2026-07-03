from django.contrib import admin
from django.contrib.auth.models import User
from django import forms
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Resource, Booking, Category, UserProfile, 
    Equipment, EquipmentCategory, EquipmentRental, MaintenanceRecord,
    Review, MeetingRoom, Amenity, AnalyticsEvent, DailyAnalytics, SavedSearch
)

# ============ CUSTOM ADMIN FORMS ============

class ResourceAdminForm(forms.ModelForm):
    """Custom form for Resource admin with better widgets"""
    
    class Meta:
        model = Resource
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'cols': 80}),
        }

# ============ INLINES ============

class BookingInline(admin.TabularInline):
    """Inline for bookings in resource admin"""
    model = Booking
    extra = 0
    fields = ['customer', 'start_time', 'end_time', 'status']
    readonly_fields = ['created_at']
    autocomplete_fields = ['customer']

class ReviewInline(admin.TabularInline):
    """Inline for reviews in resource admin"""
    model = Review
    extra = 0
    fields = ['user', 'rating', 'status']
    readonly_fields = ['created_at']
    autocomplete_fields = ['user']

class MaintenanceRecordInline(admin.TabularInline):
    """Inline for maintenance records in equipment admin"""
    model = MaintenanceRecord
    extra = 0
    fields = ['maintenance_type', 'status', 'scheduled_date', 'completed_date']
    readonly_fields = ['created_at']

class EquipmentRentalInline(admin.TabularInline):
    """Inline for rentals in equipment admin"""
    model = EquipmentRental
    extra = 0
    fields = ['rented_by', 'checkout_date', 'expected_return_date', 'status']
    readonly_fields = ['checkout_date']
    autocomplete_fields = ['rented_by']

class MeetingRoomInline(admin.StackedInline):
    """Inline for meeting room features in resource admin"""
    model = MeetingRoom
    extra = 0
    fields = [
        'room_number', 'floor_number', 'building_name',
        'seating_capacity', 'standing_capacity', 'classroom_capacity', 'theater_capacity',
        'has_projector', 'has_whiteboard', 'has_video_conferencing', 'has_phone',
        'has_smart_tv', 'has_audio_system', 'has_wifi', 'has_air_conditioning',
        'is_accessible', 'amenities', 'room_size_sqft', 'natural_light', 'has_window',
        'default_setup_time', 'default_teardown_time',
        'floor_plan', 'room_photo', 'notes'
    ]

# ============ AMENITY ADMIN ============

@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Amenity Information', {
            'fields': ('name', 'icon', 'description', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

# ============ RESOURCE MANAGEMENT ============

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon_display', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def icon_display(self, obj):
        if obj.icon:
            return format_html('<i class="{}"></i> {}', obj.icon, obj.icon)
        return '-'
    icon_display.allow_html = True
    icon_display.short_description = 'Icon'

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    form = ResourceAdminForm
    list_display = ['name', 'category', 'owner', 'status', 'view_on_site', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['name', 'description', 'owner__username', 'owner__email']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['owner', 'category']
    inlines = [BookingInline, ReviewInline, MeetingRoomInline]
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'owner')
        }),
        ('Details', {
            'fields': ('image', 'image_url', 'status', 'price_per_hour', 'location', 'max_capacity')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def view_on_site(self, obj):
        url = reverse('bookings:resource_detail', kwargs={'resource_id': obj.id})  # ✅ Fixed
        return format_html('<a href="{}" target="_blank">🔍 View</a>', url)
    view_on_site.short_description = 'Preview'
    
    actions = ['approve_resources', 'reject_resources', 'deactivate_resources']
    
    def approve_resources(self, request, queryset):
        updated = queryset.update(status='APPROVED')
        self.message_user(request, f'{updated} resources approved.')
    approve_resources.short_description = "Approve selected resources"
    
    def reject_resources(self, request, queryset):
        updated = queryset.update(status='REJECTED')
        self.message_user(request, f'{updated} resources rejected.')
    reject_resources.short_description = "Reject selected resources"
    
    def deactivate_resources(self, request, queryset):
        updated = queryset.update(status='INACTIVE')
        self.message_user(request, f'{updated} resources deactivated.')
    deactivate_resources.short_description = "Deactivate selected resources"

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['resource', 'customer', 'start_time', 'end_time', 'status', 'duration', 'created_at']
    list_filter = ['status', 'start_time', 'created_at']
    search_fields = ['resource__name', 'customer__username', 'customer__email', 'notes']
    readonly_fields = ['created_at']
    autocomplete_fields = ['resource', 'customer']
    list_editable = ['status']
    date_hierarchy = 'start_time'
    fieldsets = (
        ('Booking Details', {
            'fields': ('resource', 'customer', 'status')
        }),
        ('Time', {
            'fields': ('start_time', 'end_time')
        }),
        ('Additional', {
            'fields': ('notes', 'created_at')
        }),
    )
    
    def duration(self, obj):
        return f"{obj.get_duration()} hours"
    duration.short_description = 'Duration'
    
    actions = ['mark_as_confirmed', 'mark_as_cancelled', 'mark_as_completed']
    
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='CONFIRMED')
        self.message_user(request, f'{updated} bookings marked as confirmed.')
    mark_as_confirmed.short_description = "Mark selected bookings as Confirmed"
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(status='CANCELLED')
        self.message_user(request, f'{updated} bookings cancelled.')
    mark_as_cancelled.short_description = "Mark selected bookings as Cancelled"
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(status='COMPLETED')
        self.message_user(request, f'{updated} bookings marked as completed.')
    mark_as_completed.short_description = "Mark selected bookings as Completed"

# ============ USER PROFILE ============

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'location', 'created_at']
    list_filter = ['created_at', 'email_notifications']
    search_fields = ['user__username', 'user__email', 'phone_number', 'location']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['user']
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Profile Information', {
            'fields': ('bio', 'phone_number', 'location', 'profile_picture')
        }),
        ('Social Links', {
            'fields': ('website', 'twitter', 'linkedin', 'github')
        }),
        ('Preferences', {
            'fields': ('email_notifications', 'booking_reminders', 'rental_reminders',
                      'reservation_notifications', 'maintenance_alerts')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

# ============ EQUIPMENT RENTAL SYSTEM ============

@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'equipment_count', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    
    def equipment_count(self, obj):
        return obj.equipment.count()
    equipment_count.short_description = 'Equipment Count'

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'serial_number', 'category', 'owner', 'status', 
        'condition', 'location', 'view_equipment', 'created_at'
    ]
    list_filter = [
        'status', 'condition', 'category', 
        ('owner', admin.RelatedOnlyFieldListFilter),
        'created_at'
    ]
    search_fields = [
        'name', 'serial_number', 'asset_tag', 'barcode', 
        'owner__username', 'owner__email'
    ]
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['owner', 'category']
    list_editable = ['status', 'condition']
    inlines = [MaintenanceRecordInline, EquipmentRentalInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'description', 'location')
        }),
        ('Owner Information', {
            'fields': ('owner',),
            'classes': ('wide',),
            'description': 'Select the user who owns this equipment.'
        }),
        ('Tracking', {
            'fields': ('serial_number', 'asset_tag', 'barcode')
        }),
        ('Status', {
            'fields': ('status', 'condition')
        }),
        ('Purchase Information', {
            'fields': ('purchase_date', 'purchase_price', 'warranty_expiry')
        }),
        ('Additional', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )
    
    def view_equipment(self, obj):
        url = reverse('bookings:equipment_detail', kwargs={'equipment_id': obj.id})  # ✅ Fixed
        return format_html('<a href="{}" target="_blank">🔍 View</a>', url)
    view_equipment.short_description = 'Preview'
    
    actions = [
        'mark_as_available', 'mark_as_rented', 'mark_as_maintenance',
        'mark_as_retired', 'mark_as_lost'
    ]
    
    def mark_as_available(self, request, queryset):
        updated = queryset.update(status='AVAILABLE')
        self.message_user(request, f'{updated} equipment marked as available.')
    mark_as_available.short_description = "Mark selected equipment as Available"
    
    def mark_as_rented(self, request, queryset):
        updated = queryset.update(status='RENTED')
        self.message_user(request, f'{updated} equipment marked as rented.')
    mark_as_rented.short_description = "Mark selected equipment as Rented Out"
    
    def mark_as_maintenance(self, request, queryset):
        updated = queryset.update(status='MAINTENANCE')
        self.message_user(request, f'{updated} equipment marked for maintenance.')
    mark_as_maintenance.short_description = "Mark selected equipment as Under Maintenance"
    
    def mark_as_retired(self, request, queryset):
        updated = queryset.update(status='RETIRED')
        self.message_user(request, f'{updated} equipment retired.')
    mark_as_retired.short_description = "Mark selected equipment as Retired"
    
    def mark_as_lost(self, request, queryset):
        updated = queryset.update(status='LOST')
        self.message_user(request, f'{updated} equipment marked as lost.')
    mark_as_lost.short_description = "Mark selected equipment as Lost"

@admin.register(EquipmentRental)
class EquipmentRentalAdmin(admin.ModelAdmin):
    list_display = [
        'equipment', 'rented_by', 'checkout_date', 'expected_return_date', 
        'status', 'is_overdue', 'days_rented'
    ]
    list_filter = ['status', 'checkout_date', 'expected_return_date']
    search_fields = ['equipment__name', 'equipment__serial_number', 'rented_by__username']
    readonly_fields = ['checkout_date', 'created_at', 'actual_return_date']
    autocomplete_fields = ['equipment', 'rented_by', 'checked_out_by', 'checked_in_by']
    date_hierarchy = 'checkout_date'
    
    fieldsets = (
        ('Rental Information', {
            'fields': ('equipment', 'rented_by', 'status')
        }),
        ('Dates', {
            'fields': ('checkout_date', 'expected_return_date', 'actual_return_date')
        }),
        ('Check-in/Check-out Staff', {
            'fields': ('checked_out_by', 'checked_in_by')
        }),
        ('Condition Notes', {
            'fields': ('condition_on_checkout', 'condition_on_return')
        }),
        ('Additional', {
            'fields': ('notes', 'created_at')
        }),
    )
    
    def is_overdue(self, obj):
        return obj.is_overdue()
    is_overdue.boolean = True
    is_overdue.short_description = 'Overdue'
    
    def days_rented(self, obj):
        return obj.days_rented()
    days_rented.short_description = 'Days Rented'

@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = [
        'equipment', 'maintenance_type', 'status', 'scheduled_date', 
        'completed_date', 'cost'
    ]
    list_filter = ['maintenance_type', 'status', 'scheduled_date']
    search_fields = ['equipment__name', 'equipment__serial_number', 'title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['equipment', 'performed_by']
    date_hierarchy = 'scheduled_date'
    
    fieldsets = (
        ('Maintenance Information', {
            'fields': ('equipment', 'maintenance_type', 'status', 'title', 'description')
        }),
        ('Cost & Dates', {
            'fields': ('cost', 'scheduled_date', 'completed_date')
        }),
        ('Performed By', {
            'fields': ('performed_by', 'vendor')
        }),
        ('Additional', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )

# ============ REVIEWS ============

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'user', 'resource', 'rating', 'status', 
        'is_verified', 'helpful_count', 'created_at'
    ]
    list_filter = ['status', 'rating', 'created_at', 'is_verified']
    search_fields = ['title', 'comment', 'user__username', 'user__email', 'resource__name']
    readonly_fields = ['created_at', 'helpful_count']
    autocomplete_fields = ['user', 'resource', 'booking', 'moderated_by']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Review Information', {
            'fields': ('user', 'resource', 'booking', 'status')
        }),
        ('Content', {
            'fields': ('title', 'comment', 'rating')
        }),
        ('Verification', {
            'fields': ('is_verified', 'helpful_count', 'helpful_users')
        }),
        ('Moderation', {
            'fields': ('moderated_by', 'moderation_reason', 'moderated_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['approve_reviews', 'reject_reviews', 'delete_reviews']
    
    def approve_reviews(self, request, queryset):
        from django.utils import timezone
        for review in queryset:
            review.moderate('APPROVED', request.user, None)
        self.message_user(request, f'{queryset.count()} reviews approved.')
    approve_reviews.short_description = "Approve selected reviews"
    
    def reject_reviews(self, request, queryset):
        from django.utils import timezone
        for review in queryset:
            review.moderate('REJECTED', request.user, None)
        self.message_user(request, f'{queryset.count()} reviews rejected.')
    reject_reviews.short_description = "Reject selected reviews"
    
    def delete_reviews(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'{count} reviews deleted.')
    delete_reviews.short_description = "Delete selected reviews"

# ============ MEETING ROOM ============

@admin.register(MeetingRoom)
class MeetingRoomAdmin(admin.ModelAdmin):
    list_display = ['resource', 'room_number', 'building_name', 'seating_capacity', 'floor_number']
    list_filter = ['building_name', 'floor_number', 'has_projector', 'has_wifi']
    search_fields = ['resource__name', 'room_number', 'building_name']
    autocomplete_fields = ['resource', 'amenities']
    filter_horizontal = ['amenities']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Room Information', {
            'fields': ('resource', 'room_number', 'floor_number', 'building_name')
        }),
        ('Capacity', {
            'fields': ('seating_capacity', 'standing_capacity', 'classroom_capacity', 'theater_capacity')
        }),
        ('Features', {
            'fields': ('has_projector', 'has_whiteboard', 'has_video_conferencing', 'has_phone',
                      'has_smart_tv', 'has_audio_system', 'has_wifi', 'has_air_conditioning',
                      'is_accessible', 'amenities')
        }),
        ('Room Details', {
            'fields': ('room_size_sqft', 'natural_light', 'has_window',
                      'default_setup_time', 'default_teardown_time')
        }),
        ('Media', {
            'fields': ('floor_plan', 'room_photo')
        }),
        ('Additional', {
            'fields': ('notes',)
        }),
    )

# ============ ANALYTICS ============

@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'user', 'created_at']
    list_filter = ['event_type', 'created_at']
    search_fields = ['user__username', 'url']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

@admin.register(DailyAnalytics)
class DailyAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_users', 'active_users', 'new_users', 'total_bookings']
    list_filter = ['date']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'

# ============ SAVED SEARCH ============

@admin.register(SavedSearch)
class SavedSearchAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'is_favorite', 'last_used', 'created_at']
    list_filter = ['is_favorite', 'created_at']
    search_fields = ['name', 'user__username', 'search_query']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['user']