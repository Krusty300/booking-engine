from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from datetime import datetime

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
    
    # Category-specific booking rules
    max_booking_duration = models.PositiveIntegerField(blank=True, null=True, help_text="Maximum booking duration in hours")
    min_booking_duration = models.PositiveIntegerField(blank=True, null=True, help_text="Minimum booking duration in hours")
    requires_approval = models.BooleanField(default=False, help_text="Does this category require admin approval for bookings?")
    booking_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Additional fee for bookings in this category")
    
    # Metadata
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
    
    def get_icon_display(self):
        """Return the icon with proper HTML markup"""
        if self.icon:
            return f'<i class="{self.icon}"></i>'
        return ''

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
    
    # Category relationship
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='resources',
        help_text="Select a category for this resource"
    )
    
    # Image field
    image = models.ImageField(
        upload_to='resources/', 
        blank=True, 
        null=True,
        validators=[validate_image_size],
        help_text="Upload an image of your resource (max 5MB)"
    )
    
    # Keep image_url for backward compatibility
    image_url = models.URLField(blank=True, null=True, help_text="Optional: Link to an image URL")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    def get_image_url(self):
        """Get the image URL (prefer uploaded image over URL)"""
        if self.image:
            return self.image.url
        elif self.image_url:
            return self.image_url
        return '/static/bookings/images/default-resource.png'
    
    def has_image(self):
        """Check if the resource has an image"""
        return bool(self.image) or bool(self.image_url)
    
    def can_edit(self, user):
        """Check if a user can edit this resource"""
        return user.is_authenticated and (user == self.owner or user.is_staff)
    
    def can_delete(self, user):
        """Check if a user can delete this resource"""
        return user.is_authenticated and (user == self.owner or user.is_staff)
    
    def is_approved(self):
        """Check if the resource is approved"""
        return self.status == 'APPROVED'
    
    def is_public(self):
        """Check if the resource is visible to everyone"""
        return self.status in ['APPROVED']
    
    def get_category_rules(self):
        """Get category-specific booking rules"""
        if self.category:
            return {
                'max_duration': self.category.max_booking_duration,
                'min_duration': self.category.min_booking_duration,
                'requires_approval': self.category.requires_approval,
                'booking_fee': self.category.booking_fee,
            }
        return {}

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


class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='profile'
    )
    
    # Personal Information
    bio = models.TextField(max_length=500, blank=True, null=True, help_text="Tell us about yourself")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    
    # Profile Picture
    profile_picture = models.ImageField(
        upload_to='profile_pictures/', 
        blank=True, 
        null=True,
        help_text="Upload a profile picture"
    )
    
    # Social Links
    website = models.URLField(blank=True, null=True, help_text="Your personal website or portfolio")
    twitter = models.CharField(max_length=50, blank=True, null=True, help_text="Twitter username")
    linkedin = models.CharField(max_length=50, blank=True, null=True, help_text="LinkedIn username")
    github = models.CharField(max_length=50, blank=True, null=True, help_text="GitHub username")
    
    # Preferences
    email_notifications = models.BooleanField(default=True, help_text="Receive email notifications")
    booking_reminders = models.BooleanField(default=True, help_text="Receive booking reminders")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile of {self.user.username}"
    
    def get_full_name(self):
        """Get user's full name or username"""
        if self.user.get_full_name():
            return self.user.get_full_name()
        return self.user.username
    
    def get_profile_picture_url(self):
        """Get profile picture URL or default avatar"""
        if self.profile_picture:
            return self.profile_picture.url
        return '/static/bookings/images/default-avatar.png'
    
    def get_booking_stats(self):
        """Get booking statistics for the user"""
        from django.utils import timezone
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


# Create signal to automatically create profile when user is created
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile whenever a User is created"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile whenever the User is saved"""
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)
