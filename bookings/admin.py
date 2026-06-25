from django.contrib import admin
from .models import (
    Resource, Booking, Category, UserProfile, 
    Equipment, EquipmentCategory, EquipmentRental, MaintenanceRecord,
    Review
)

# ============ RESOURCE MANAGEMENT ============

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']

@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'owner', 'status', 'created_at']
    list_filter = ['status', 'category', 'created_at']
    search_fields = ['name', 'description', 'owner__username']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'owner')
        }),
        ('Details', {
            'fields': ('image', 'status', 'price_per_hour', 'location')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['resource', 'customer', 'start_time', 'end_time', 'status', 'created_at']
    list_filter = ['status', 'start_time', 'created_at']
    search_fields = ['resource__name', 'customer__username', 'notes']
    readonly_fields = ['created_at']
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

# ============ USER PROFILE ============

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at']
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Profile Information', {
            'fields': ('bio',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )

# ============ EQUIPMENT RENTAL SYSTEM ============

@admin.register(EquipmentCategory)
class EquipmentCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'serial_number', 'category', 'owner', 'status', 'condition', 'location', 'created_at']
    list_filter = ['status', 'condition', 'category', 'owner', 'created_at']
    search_fields = ['name', 'serial_number', 'asset_tag', 'barcode', 'owner__username', 'owner__email']
    readonly_fields = ['created_at', 'updated_at']
    autocomplete_fields = ['owner']
    list_editable = ['status', 'condition']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'description', 'location')
        }),
        ('Owner Information', {
            'fields': ('owner',),
            'classes': ('wide',),
            'description': 'Select the user who owns this equipment. If left blank, the equipment will have no owner.'
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
    
    def assign_owner(self, request, queryset):
        """Admin action to assign owner to selected equipment"""
        if 'apply' in request.POST:
            owner_id = request.POST.get('owner')
            if owner_id:
                from django.contrib.auth.models import User
                owner = User.objects.get(id=owner_id)
                updated = queryset.update(owner=owner)
                self.message_user(request, f'Owner assigned to {updated} equipment items.')
                return
        
        from django.shortcuts import render
        from django.contrib.auth.models import User
        
        users = User.objects.all()
        return render(request, 'admin/assign_owner.html', {
            'queryset': queryset,
            'users': users,
        })
    
    assign_owner.short_description = "Assign owner to selected equipment"
    actions = ['assign_owner']

@admin.register(EquipmentRental)
class EquipmentRentalAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'rented_by', 'checkout_date', 'expected_return_date', 'status']
    list_filter = ['status', 'checkout_date', 'expected_return_date']
    search_fields = ['equipment__name', 'equipment__serial_number', 'rented_by__username']
    readonly_fields = ['checkout_date', 'created_at']  # Only fields that exist
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

@admin.register(MaintenanceRecord)
class MaintenanceRecordAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'maintenance_type', 'status', 'scheduled_date']
    list_filter = ['maintenance_type', 'status', 'scheduled_date']
    search_fields = ['equipment__name', 'equipment__serial_number', 'title', 'description']
    readonly_fields = ['created_at']
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
            'fields': ('notes', 'created_at')
        }),
    )

# ============ REVIEWS ============

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'resource', 'rating', 'status', 'created_at']
    list_filter = ['status', 'rating', 'created_at']
    search_fields = ['title', 'comment', 'user__username', 'resource__name']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Review Information', {
            'fields': ('user', 'resource', 'status')
        }),
        ('Content', {
            'fields': ('title', 'comment', 'rating')
        }),
        ('Moderation', {
            'fields': ('moderated_by', 'moderation_reason', 'moderated_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )