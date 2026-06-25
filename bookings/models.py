from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone

def validate_image_size(value):
    """Validate that the image file is not too large"""
    filesize = value.size
    if filesize > settings.MAX_UPLOAD_SIZE:
        raise ValidationError(f"Maximum file size is 5MB. Your file is {filesize / 1048576:.1f}MB.")
    return value

class Category(models.Model):
    """Resource category for organizing and filtering resources"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Font Awesome icon class (e.g., 'fa-building')")
    color = models.CharField(max_length=7, default='#007bff', help_text="Hex color code (e.g., #007bff)")
    
    max_booking_duration = models.PositiveIntegerField(blank=True, null=True, help_text="Maximum booking duration in hours")
    min_booking_duration = models.PositiveIntegerField(blank=True, null=True, help_text="Minimum booking duration in hours")
    requires_approval = models.BooleanField(default=False, help_text="Does this category require admin approval for bookings?")
    booking_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Additional fee for bookings in this category")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

class Amenity(models.Model):
    """Amenities available for meeting rooms"""
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True, null=True, help_text="Font Awesome icon class")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Amenities"
        ordering = ['name']
    
    def __str__(self):
        return self.name

class MeetingRoom(models.Model):
    """Extended meeting room features"""
    resource = models.OneToOneField(
        'Resource', 
        on_delete=models.CASCADE, 
        related_name='meeting_room'
    )
    
    # Room identification
    room_number = models.CharField(max_length=20, blank=True, null=True)
    floor_number = models.IntegerField(default=1)
    building_name = models.CharField(max_length=100, blank=True, null=True)
    
    # Capacity tracking
    seating_capacity = models.IntegerField(default=0, help_text="Seating capacity")
    standing_capacity = models.IntegerField(default=0, help_text="Standing capacity")
    classroom_capacity = models.IntegerField(default=0, help_text="Classroom setup capacity")
    theater_capacity = models.IntegerField(default=0, help_text="Theater setup capacity")
    
    # Room features (booleans)
    has_projector = models.BooleanField(default=False)
    has_whiteboard = models.BooleanField(default=False)
    has_video_conferencing = models.BooleanField(default=False)
    has_phone = models.BooleanField(default=False)
    has_smart_tv = models.BooleanField(default=False)
    has_audio_system = models.BooleanField(default=False)
    has_wifi = models.BooleanField(default=True)
    has_air_conditioning = models.BooleanField(default=True)
    is_accessible = models.BooleanField(default=True, help_text="Wheelchair accessible")
    
    # Amenities (Many-to-Many)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='meeting_rooms')
    
    # Room specifications
    room_size_sqft = models.IntegerField(null=True, blank=True, help_text="Room size in square feet")
    natural_light = models.BooleanField(default=False)
    has_window = models.BooleanField(default=True)
    
    # Setup time
    default_setup_time = models.IntegerField(default=15, help_text="Default setup time in minutes")
    default_teardown_time = models.IntegerField(default=15, help_text="Default teardown time in minutes")
    
    # Documents
    floor_plan = models.ImageField(upload_to='floor_plans/', blank=True, null=True)
    room_photo = models.ImageField(upload_to='room_photos/', blank=True, null=True)
    
    # Additional info
    notes = models.TextField(blank=True, help_text="Any additional notes about the room")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.resource.name} (Room {self.room_number or 'N/A'})"
    
    def get_capacity_display(self):
        """Get a formatted string of all capacities"""
        capacities = []
        if self.seating_capacity:
            capacities.append(f"Seating: {self.seating_capacity}")
        if self.standing_capacity:
            capacities.append(f"Standing: {self.standing_capacity}")
        if self.classroom_capacity:
            capacities.append(f"Classroom: {self.classroom_capacity}")
        if self.theater_capacity:
            capacities.append(f"Theater: {self.theater_capacity}")
        return " | ".join(capacities) if capacities else "No capacity data"
    
    def get_amenities_list(self):
        """Get list of amenity names"""
        return [amenity.name for amenity in self.amenities.all()]
    
    def get_features_list(self):
        """Get list of available features"""
        features = []
        if self.has_projector:
            features.append('Projector')
        if self.has_whiteboard:
            features.append('Whiteboard')
        if self.has_video_conferencing:
            features.append('Video Conferencing')
        if self.has_phone:
            features.append('Phone')
        if self.has_smart_tv:
            features.append('Smart TV')
        if self.has_audio_system:
            features.append('Audio System')
        if self.has_wifi:
            features.append('WiFi')
        if self.has_air_conditioning:
            features.append('Air Conditioning')
        return features
    
    def get_max_capacity(self):
        """Get the maximum capacity across all types"""
        return max(
            self.seating_capacity or 0,
            self.standing_capacity or 0,
            self.classroom_capacity or 0,
            self.theater_capacity or 0
        )


class Resource(models.Model):
    """A bookable resource (e.g., a tutor, a room, equipment)"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('INACTIVE', 'Inactive'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='resources',
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='APPROVED'
    )
    location = models.CharField(max_length=200, blank=True, null=True)
    max_capacity = models.PositiveIntegerField(default=1, help_text="Maximum number of people that can book this resource")
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, null=True, blank=True)
    
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='resources',
        help_text="Select a category for this resource"
    )
    
    # ADD THIS IMAGE FIELD
    image = models.ImageField(
        upload_to='resources/', 
        blank=True, 
        null=True,
        validators=[validate_image_size],
        help_text="Upload an image of your resource (max 5MB)"
    )
    
    # Keep image_url for backward compatibility
    image_url = models.URLField(blank=True, null=True, help_text="Optional: Link to an image URL")
    
    # Meeting room specific images (these can be separate or use the main image)
    room_photo = models.ImageField(
        upload_to='room_photos/', 
        blank=True, 
        null=True,
        help_text="Upload a photo of the room"
    )
    floor_plan = models.ImageField(
        upload_to='floor_plans/', 
        blank=True, 
        null=True,
        help_text="Upload a floor plan of the room"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    def get_image_url(self):
        if self.image:
            return self.image.url
        elif self.image_url:
            return self.image_url
        return '/static/bookings/images/default-resource.png'
    
    def has_image(self):
        return bool(self.image) or bool(self.image_url)
    
    def can_edit(self, user):
        return user.is_authenticated and (user == self.owner or user.is_staff)
    
    def can_delete(self, user):
        return user.is_authenticated and (user == self.owner or user.is_staff)
    
    def is_approved(self):
        return self.status == 'APPROVED'
    
    def is_public(self):
        return self.status in ['APPROVED']
    
    def get_category_rules(self):
        if self.category:
            return {
                'max_duration': self.category.max_booking_duration,
                'min_duration': self.category.min_booking_duration,
                'requires_approval': self.category.requires_approval,
                'booking_fee': self.category.booking_fee,
            }
        return {}
    
    def is_meeting_room(self):
        """Check if this resource has meeting room features"""
        return hasattr(self, 'meeting_room')
    
    def get_meeting_room(self):
        """Get the meeting room instance if it exists"""
        if self.is_meeting_room():
            return self.meeting_room
        return None

    def get_average_rating(self):
        """Get average rating for the resource"""
        approved_reviews = self.reviews.filter(status='APPROVED')
        if approved_reviews.exists():
            total = approved_reviews.aggregate(models.Avg('rating'))['rating__avg']
            return round(total, 1)
        return 0

    def get_rating_count(self):
        """Get total number of ratings"""
        return self.reviews.filter(status='APPROVED').count()

    def get_rating_distribution(self):
        """Get distribution of ratings"""
        distribution = {}
        for i in range(1, 6):
            distribution[i] = self.reviews.filter(
                status='APPROVED', 
                rating=i
            ).count()
        return distribution

    def get_recent_reviews(self, limit=5):
        """Get recent approved reviews"""
        return self.reviews.filter(status='APPROVED')[:limit]


class Booking(models.Model):
    """A booking for a specific resource at a specific time"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    ]
    
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, related_name='bookings')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['resource', 'start_time', 'end_time'],
                name='unique_booking_slot'
            )
        ]
        indexes = [
            models.Index(fields=['resource', 'start_time']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.resource.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_duration(self):
        """Get booking duration in hours"""
        duration = (self.end_time - self.start_time).total_seconds() / 3600
        return round(duration, 1)
    
    def get_status_icon(self):
        """Get status icon for display"""
        icons = {
            'PENDING': '⏳',
            'CONFIRMED': '✅',
            'CANCELLED': '❌',
            'COMPLETED': '📌',
        }
        return icons.get(self.status, '📋')
    
    def get_status_color(self):
        """Get status color for display"""
        colors = {
            'PENDING': '#ffc107',
            'CONFIRMED': '#28a745',
            'CANCELLED': '#dc3545',
            'COMPLETED': '#17a2b8',
        }
        return colors.get(self.status, '#6c757d')
    
    def can_cancel(self):
        """Check if booking can be cancelled"""
        if self.status in ['CANCELLED', 'COMPLETED']:
            return False
        if self.start_time <= timezone.now():
            return False
        return True
    
    def is_upcoming(self):
        """Check if booking is upcoming"""
        return self.start_time > timezone.now() and self.status in ['PENDING', 'CONFIRMED']
    
    def is_past(self):
        """Check if booking is past"""
        return self.start_time <= timezone.now() and self.status != 'CANCELLED'

class Review(models.Model):
    """Review and rating for resources"""
    
    RATING_CHOICES = [
        (1, '⭐ 1 - Poor'),
        (2, '⭐⭐ 2 - Fair'),
        (3, '⭐⭐⭐ 3 - Good'),
        (4, '⭐⭐⭐⭐ 4 - Very Good'),
        (5, '⭐⭐⭐⭐⭐ 5 - Excellent'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    resource = models.ForeignKey(
        Resource, 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='reviews'
    )
    booking = models.OneToOneField(
        Booking, 
        on_delete=models.CASCADE, 
        related_name='review',
        null=True, 
        blank=True,
        help_text="The booking this review is for"
    )
    
    # Rating and review
    rating = models.IntegerField(choices=RATING_CHOICES)
    title = models.CharField(max_length=200, blank=True, null=True)
    comment = models.TextField(max_length=1000, blank=True, null=True)
    
    # Review metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_verified = models.BooleanField(
        default=False, 
        help_text="Verified purchase - user actually booked this resource"
    )
    
    # Moderation fields (NEW)
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='moderated_reviews',
        help_text="Admin who moderated this review"
    )
    moderation_reason = models.TextField(
        blank=True, 
        null=True,
        help_text="Reason for rejection (visible to user)"
    )
    moderated_at = models.DateTimeField(null=True, blank=True)
    
    # Helpful votes
    helpful_count = models.IntegerField(default=0)
    helpful_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='helpful_reviews',
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'resource']
        indexes = [
            models.Index(fields=['resource', 'rating']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['moderated_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.resource.name} - {self.rating}⭐"
    
    def get_rating_stars(self):
        return '⭐' * self.rating + '☆' * (5 - self.rating)
    
    def get_rating_percentage(self):
        return (self.rating / 5) * 100
    
    def is_helpful(self, user):
        return self.helpful_users.filter(id=user.id).exists() if user.is_authenticated else False
    
    def toggle_helpful(self, user):
        if user.is_authenticated:
            if self.is_helpful(user):
                self.helpful_users.remove(user)
                self.helpful_count -= 1
            else:
                self.helpful_users.add(user)
                self.helpful_count += 1
            self.save()
            return True
        return False
    
    def moderate(self, status, admin_user, reason=None):
        """Moderate a review"""
        self.status = status
        self.moderated_by = admin_user
        self.moderated_at = timezone.now()
        if reason:
            self.moderation_reason = reason
        self.save()
        return self


class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    
    bio = models.TextField(max_length=500, blank=True, null=True, help_text="Tell us about yourself")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', 
        blank=True, 
        null=True,
        help_text="Upload a profile picture"
    )
    
    website = models.URLField(blank=True, null=True, help_text="Your personal website or portfolio")
    twitter = models.CharField(max_length=50, blank=True, null=True, help_text="Twitter username")
    linkedin = models.CharField(max_length=50, blank=True, null=True, help_text="LinkedIn username")
    github = models.CharField(max_length=50, blank=True, null=True, help_text="GitHub username")
    
    email_notifications = models.BooleanField(default=True, help_text="Receive email notifications")
    booking_reminders = models.BooleanField(default=True, help_text="Receive booking reminders")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile of {self.user.username}"
    
    def get_full_name(self):
        if self.user.get_full_name():
            return self.user.get_full_name()
        return self.user.username
    
    def get_profile_picture_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        return '/static/bookings/images/default-avatar.png'
    
    def get_booking_stats(self):
        bookings = Booking.objects.filter(customer=self.user)
        return {
            'total': bookings.count(),
            'upcoming': bookings.filter(
                start_time__gte=timezone.now(),
                status__in=['PENDING', 'CONFIRMED']
            ).count(),
            'completed': bookings.filter(status='COMPLETED').count(),
            'cancelled': bookings.filter(status='CANCELLED').count(),
        }
    
    class Meta:
        verbose_name_plural = "User Profiles"


# ============ ANALYTICS MODELS ============

class AnalyticsEvent(models.Model):
    """Track user events for analytics"""
    EVENT_TYPES = [
        ('VIEW', 'Page View'),
        ('BOOKING', 'Booking Created'),
        ('CANCEL', 'Booking Cancelled'),
        ('SEARCH', 'Search Performed'),
        ('LOGIN', 'User Login'),
        ('SIGNOUT', 'User Signout'),
        ('RESOURCE_CREATE', 'Resource Created'),
        ('RESOURCE_EDIT', 'Resource Edited'),
        ('RESOURCE_DELETE', 'Resource Deleted'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    url = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} by {self.user or 'Anonymous'} at {self.created_at}"

class DailyAnalytics(models.Model):
    """Daily aggregated analytics"""
    date = models.DateField(unique=True)
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    total_bookings = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    page_views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Daily Analytics"
    
    def __str__(self):
        return f"Analytics for {self.date}"

class EquipmentCategory(models.Model):
    """Category for equipment (e.g., 'Audio', 'Video', 'Computers')"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Font awesome icon class")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Equipment Categories"

    def __str__(self):
        return self.name

class Equipment(models.Model):
    """Individual equipment item with serial number tracking"""
    STATUS_CHOICES = [
        ('AVAILABLE', 'Available'),
        ('RENTED', 'Rented Out'),
        ('MAINTENANCE', 'Under Maintenance'),
        ('RETIRED', 'Retired'),
        ('LOST', 'Lost'),
    ]

    CONDITION_CHOICES = [
        ('EXCELLENT', 'Excellent'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor'),
        ('NEEDS_REPAIR', 'Needs Repair'),
    ]

    # Basic info
    name = models.CharField(max_length=200)
    category = models.ForeignKey(EquipmentCategory, on_delete=models.SET_NULL, null=True, related_name='equipment')
    description = models.TextField(blank=True)
    
    # Tracking
    serial_number = models.CharField(max_length=100, unique=True, db_index=True)
    asset_tag = models.CharField(max_length=50, unique=True, blank=True, null=True)
    barcode = models.CharField(max_length=100, blank=True, null=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='GOOD')
    
    # Purchase info
    purchase_date = models.DateField(null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    
    # Location
    location = models.CharField(max_length=200, blank=True, help_text="Current location of equipment")
    
    # Additional info
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ============ NEW: OWNER FIELD ============
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_owned',
        help_text="User who owns/created this equipment"
    )

    class Meta:
        verbose_name_plural = "Equipment"
        indexes = [
            models.Index(fields=['serial_number']),
            models.Index(fields=['status']),
            models.Index(fields=['category']),
            models.Index(fields=['owner']),  # Add index for owner field
        ]

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

    def is_available(self):
        """Check if equipment is available for rental"""
        return self.status == 'AVAILABLE'

    def can_be_rented(self):
        """Check if equipment can be rented (not in maintenance or retired)"""
        return self.status in ['AVAILABLE', 'RENTED']
    
    def is_owned_by(self, user):
        """Check if a user owns this equipment"""
        if not user.is_authenticated:
            return False
        return self.owner == user
    
    def can_manage(self, user):
        """Check if a user can manage this equipment (owner or staff)"""
        if not user.is_authenticated:
            return False
        return user.is_staff or self.is_owned_by(user)

class EquipmentRental(models.Model):
    """Rental record for equipment check-in/check-out"""
    STATUS_CHOICES = [
        ('CHECKED_OUT', 'Checked Out'),
        ('CHECKED_IN', 'Checked In'),
        ('OVERDUE', 'Overdue'),
        ('LOST', 'Lost'),
        ('DAMAGED', 'Damaged'),
    ]

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='rentals')
    rented_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='equipment_rentals')
    checked_out_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='checked_out_rentals')
    checked_in_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='checked_in_rentals')

    # Dates
    checkout_date = models.DateTimeField(auto_now_add=True)
    expected_return_date = models.DateTimeField()
    actual_return_date = models.DateTimeField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CHECKED_OUT')
    
    # Notes
    condition_on_checkout = models.TextField(blank=True, help_text="Condition notes when rented")
    condition_on_return = models.TextField(blank=True, help_text="Condition notes when returned")
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-checkout_date']
        indexes = [
            models.Index(fields=['equipment', 'status']),
            models.Index(fields=['rented_by', 'status']),
            models.Index(fields=['expected_return_date']),
        ]

    def __str__(self):
        return f"{self.equipment.name} - {self.rented_by.username} ({self.checkout_date.strftime('%Y-%m-%d')})"

    def is_overdue(self):
        """Check if rental is overdue"""
        if self.status == 'CHECKED_IN':
            return False
        return timezone.now() > self.expected_return_date

    def days_rented(self):
        """Calculate days rented"""
        if self.actual_return_date:
            return (self.actual_return_date - self.checkout_date).days
        return (timezone.now() - self.checkout_date).days

    def save(self, *args, **kwargs):
        # Update equipment status when rental is created
        if self.status == 'CHECKED_OUT' and not self.pk:
            self.equipment.status = 'RENTED'
            self.equipment.save()
        
        # Update equipment status when rental is checked in
        if self.status == 'CHECKED_IN' and self.pk:
            self.equipment.status = 'AVAILABLE'
            self.equipment.save()
        
        super().save(*args, **kwargs)

class MaintenanceRecord(models.Model):
    """Track maintenance and repairs for equipment"""
    MAINTENANCE_TYPES = [
        ('ROUTINE', 'Routine Maintenance'),
        ('REPAIR', 'Repair'),
        ('INSPECTION', 'Inspection'),
        ('CALIBRATION', 'Calibration'),
        ('UPGRADE', 'Upgrade'),
        ('OTHER', 'Other'),
    ]

    STATUS_CHOICES = [
        ('SCHEDULED', 'Scheduled'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]

    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE, related_name='maintenance_records')
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')
    
    # Details
    title = models.CharField(max_length=200)
    description = models.TextField()
    cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Dates
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    
    # Performed by
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='maintenance_performed')
    vendor = models.CharField(max_length=200, blank=True, help_text="External vendor if applicable")
    
    # Notes
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-scheduled_date']

    def __str__(self):
        return f"{self.equipment.name} - {self.get_maintenance_type_display()} ({self.scheduled_date})"

    def complete_maintenance(self):
        """Mark maintenance as completed"""
        self.status = 'COMPLETED'
        self.completed_date = timezone.now().date()
        self.equipment.status = 'AVAILABLE'
        self.equipment.save()
        self.save()


# ============ SIGNALS ============

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)