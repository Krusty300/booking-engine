import os
import re
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    Resource, Category, UserProfile, MeetingRoom, Review, 
    Equipment, EquipmentCategory, EquipmentImage, Booking
)

# ============ VALIDATION MIXINS ============

class ImageValidationMixin:
    """Mixin for validating image uploads"""
    
    def validate_image_file(self, file, max_size_mb=5):
        """Validate image file size and type"""
        if not file:
            return file
        
        max_size = max_size_mb * 1024 * 1024
        if file.size > max_size:
            raise ValidationError(f'Image file size cannot exceed {max_size_mb}MB.')
        
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in valid_extensions:
            raise ValidationError(
                f"Unsupported file extension. Please use: {', '.join(valid_extensions)}"
            )
        
        return file


class PhoneValidationMixin:
    """Mixin for validating phone numbers"""
    
    def validate_phone_number(self, phone):
        """Validate phone number format"""
        if phone:
            clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
            if not clean_phone.isdigit():
                raise ValidationError('Please enter a valid phone number (digits only).')
            if len(clean_phone) < 10:
                raise ValidationError('Phone number must be at least 10 digits.')
        return phone


# ============ AUTHENTICATION FORMS ============

class SignUpForm(UserCreationForm):
    """User registration form with email validation"""
    
    email = forms.EmailField(
        max_length=254, 
        required=True, 
        help_text='Required. Enter a valid email address.'
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email address is already registered.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


# ============ RESOURCE FORMS ============

class ResourceForm(forms.ModelForm, ImageValidationMixin):
    """Enhanced form for creating and editing resources"""
    
    # Additional fields for better UX
    contact_email = forms.EmailField(
        required=False,
        help_text='Email for booking inquiries (defaults to your account email)',
        widget=forms.EmailInput(attrs={'placeholder': 'contact@example.com'})
    )
    contact_phone = forms.CharField(
        required=False,
        help_text='Phone number for booking inquiries',
        widget=forms.TextInput(attrs={'placeholder': '+254 700 000 000'})
    )
    website = forms.URLField(
        required=False,
        help_text='Website or social media link',
        widget=forms.URLInput(attrs={'placeholder': 'https://example.com'})
    )
    tags = forms.CharField(
        required=False,
        help_text='Comma-separated tags (e.g., wifi, projector, accessible)',
        widget=forms.TextInput(attrs={'placeholder': 'wifi, projector, accessible'})
    )
    terms_accepted = forms.BooleanField(
        required=True,
        label='I agree to the terms and conditions',
        error_messages={'required': 'You must accept the terms to continue.'}
    )
    
    class Meta:
        model = Resource
        fields = [
            'name', 'description', 'category', 'location', 
            'max_capacity', 'price_per_hour', 
            'image', 'image_url',
        ]
        labels = {
            'name': 'Resource Name *',
            'description': 'Description *',
            'category': 'Category',
            'location': 'Location',
            'max_capacity': 'Maximum Capacity',
            'price_per_hour': 'Price per Hour',
            'image': 'Main Image',
            'image_url': 'Image URL (Alternative)',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g., Executive Conference Room',
                'class': 'form-control',
                'data-counter': 'name-counter'
            }),
            'description': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Describe your resource in detail... Include amenities, features, and any special notes.',
                'class': 'form-control',
                'data-counter': 'description-counter',
                'maxlength': '1000'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={
                'placeholder': 'e.g., Nairobi, Kenya',
                'class': 'form-control',
                'id': 'location-input'
            }),
            'max_capacity': forms.NumberInput(attrs={
                'min': 1,
                'max': 100,
                'placeholder': '1',
                'class': 'form-control'
            }),
            'price_per_hour': forms.NumberInput(attrs={
                'min': 0,
                'step': 0.01,
                'placeholder': '0.00',
                'class': 'form-control'
            }),
            'image': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'form-control'
            }),
            'image_url': forms.URLInput(attrs={
                'placeholder': 'https://example.com/image.jpg',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make fields optional
        optional_fields = [
            'category', 'location', 'max_capacity', 'price_per_hour', 
            'image', 'image_url', 'contact_email', 'contact_phone', 
            'website', 'tags'
        ]
        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
        
        # Configure category field
        if 'category' in self.fields:
            self.fields['category'].empty_label = 'Select a category (optional)'
        
        # Add help text to fields
        self.fields['name'].help_text = 'A clear, descriptive name for your resource'
        self.fields['description'].help_text = 'Maximum 1000 characters. Be specific about what you offer.'
        self.fields['max_capacity'].help_text = 'How many people can use this resource at once?'
        self.fields['price_per_hour'].help_text = 'Set to 0.00 for free resources'
        self.fields['image'].help_text = 'Upload a main image for your resource (max 5MB)'
        self.fields['image_url'].help_text = 'Optional: Link to an external image URL'
        
        # Add CSS classes for styling
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'
    
    def clean_name(self):
        """Validate resource name"""
        name = self.cleaned_data.get('name')
        if name:
            if len(name) < 3:
                raise ValidationError('Resource name must be at least 3 characters long.')
            # Check for duplicate names (case-insensitive)
            existing = Resource.objects.filter(name__iexact=name)
            if self.instance and self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(
                    'A resource with this name already exists. Please choose a different name.'
                )
        return name
    
    def clean_description(self):
        """Validate description length"""
        description = self.cleaned_data.get('description')
        if description and len(description) > 1000:
            raise ValidationError('Description cannot exceed 1000 characters.')
        return description
    
    def clean_max_capacity(self):
        """Validate capacity"""
        capacity = self.cleaned_data.get('max_capacity')
        if capacity and capacity < 1:
            raise ValidationError('Capacity must be at least 1 person.')
        if capacity and capacity > 100:
            raise ValidationError('Capacity cannot exceed 100 people.')
        return capacity
    
    def clean_price_per_hour(self):
        """Validate price"""
        price = self.cleaned_data.get('price_per_hour')
        if price is not None and price < 0:
            raise ValidationError('Price cannot be negative.')
        return price
    
    def clean_contact_phone(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('contact_phone')
        if phone:
            import re
            clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
            if not clean_phone.isdigit():
                raise ValidationError('Please enter a valid phone number (digits only).')
        return phone
    
    def clean_image(self):
        """Validate main image file"""
        image = self.cleaned_data.get('image')
        return self.validate_image_file(image)


class ResourceStatusForm(forms.ModelForm):
    """Form for admins to update resource status"""
    
    class Meta:
        model = Resource
        fields = ['status']


# ============ CATEGORY FORMS ============

class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""
    
    class Meta:
        model = Category
        fields = [
            'name', 'description', 'icon', 'color', 
            'max_booking_duration', 'min_booking_duration', 
            'requires_approval', 'booking_fee'
        ]
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 3, 
                'placeholder': 'Describe this category...'
            }),
            'icon': forms.TextInput(attrs={
                'placeholder': 'fa-building, fa-laptop, fa-users, etc.'
            }),
            'color': forms.TextInput(attrs={
                'type': 'color', 
                'style': 'padding: 4px; height: 45px;'
            }),
            'max_booking_duration': forms.NumberInput(attrs={
                'min': 1, 
                'placeholder': 'e.g., 4'
            }),
            'min_booking_duration': forms.NumberInput(attrs={
                'min': 1, 
                'placeholder': 'e.g., 1'
            }),
            'booking_fee': forms.NumberInput(attrs={
                'min': 0, 
                'step': 0.01, 
                'placeholder': '0.00'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.required = field_name in ['name']


# ============ USER PROFILE FORMS ============

class UserProfileForm(forms.ModelForm, ImageValidationMixin, PhoneValidationMixin):
    """Form for editing user profile"""
    
    class Meta:
        model = UserProfile
        fields = [
            'bio', 'phone_number', 'location', 'profile_picture', 
            'website', 'twitter', 'linkedin', 'github',
            'email_notifications', 'booking_reminders', 
            'rental_reminders', 'reservation_notifications', 
            'maintenance_alerts'
        ]
        widgets = {
            'bio': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Tell us about yourself...',
                'class': 'form-control'
            }),
            'phone_number': forms.TextInput(attrs={
                'placeholder': '+254 700 000 000',
                'class': 'form-control'
            }),
            'location': forms.TextInput(attrs={
                'placeholder': 'Nairobi, Kenya',
                'class': 'form-control'
            }),
            'website': forms.URLInput(attrs={
                'placeholder': 'https://yourwebsite.com',
                'class': 'form-control'
            }),
            'twitter': forms.TextInput(attrs={
                'placeholder': '@username',
                'class': 'form-control'
            }),
            'linkedin': forms.TextInput(attrs={
                'placeholder': 'linkedin.com/in/username',
                'class': 'form-control'
            }),
            'github': forms.TextInput(attrs={
                'placeholder': 'github.com/username',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['bio', 'phone_number', 'location']:
                field.required = False
            if field_name == 'profile_picture':
                field.help_text = "Upload a profile picture (JPG, PNG). Max 2MB."
    
    def clean_phone_number(self):
        """Validate phone number format"""
        phone = self.cleaned_data.get('phone_number')
        return self.validate_phone_number(phone)
    
    def clean_profile_picture(self):
        """Validate profile picture"""
        picture = self.cleaned_data.get('profile_picture')
        return self.validate_image_file(picture, max_size_mb=2)


class UserSettingsForm(forms.ModelForm):
    """Form for updating user account settings"""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False
        
    def clean_email(self):
        """Validate email uniqueness"""
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError('This email is already in use by another account.')
        return email


# ============ MEETING ROOM FORMS ============

class MeetingRoomForm(forms.ModelForm, ImageValidationMixin):
    """Form for meeting room specific features"""
    
    class Meta:
        model = MeetingRoom
        fields = [
            'room_number', 'floor_number', 'building_name',
            'seating_capacity', 'standing_capacity', 'classroom_capacity', 'theater_capacity',
            'has_projector', 'has_whiteboard', 'has_video_conferencing', 'has_phone',
            'has_smart_tv', 'has_audio_system', 'has_wifi', 'has_air_conditioning',
            'is_accessible', 'amenities', 'room_size_sqft', 'natural_light', 'has_window',
            'default_setup_time', 'default_teardown_time',
            'floor_plan', 'room_photo',
            'notes'
        ]
        widgets = {
            'room_number': forms.TextInput(attrs={'placeholder': 'e.g., 101'}),
            'floor_number': forms.NumberInput(attrs={'min': 0, 'placeholder': '1'}),
            'building_name': forms.TextInput(attrs={'placeholder': 'e.g., Main Building'}),
            'seating_capacity': forms.NumberInput(attrs={'min': 0, 'placeholder': '0'}),
            'standing_capacity': forms.NumberInput(attrs={'min': 0, 'placeholder': '0'}),
            'classroom_capacity': forms.NumberInput(attrs={'min': 0, 'placeholder': '0'}),
            'theater_capacity': forms.NumberInput(attrs={'min': 0, 'placeholder': '0'}),
            'default_setup_time': forms.NumberInput(attrs={'min': 0, 'placeholder': '15'}),
            'default_teardown_time': forms.NumberInput(attrs={'min': 0, 'placeholder': '15'}),
            'room_size_sqft': forms.NumberInput(attrs={'min': 0, 'placeholder': '0'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any additional notes...'}),
            'amenities': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'room_photo': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'}),
            'floor_plan': forms.FileInput(attrs={'accept': 'image/*', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['amenities']:
                field.required = False
            if field_name == 'room_photo':
                field.help_text = "Upload a photo of the room (JPG, PNG, GIF). Max 5MB."
            if field_name == 'floor_plan':
                field.help_text = "Upload a floor plan (JPG, PNG, GIF). Max 5MB."
    
    def clean(self):
        """Cross-field validation with default capacity"""
        cleaned_data = super().clean()
        
        # Check if this is a POST request with data
        if self.data:
            seating = cleaned_data.get('seating_capacity', 0)
            standing = cleaned_data.get('standing_capacity', 0)
            classroom = cleaned_data.get('classroom_capacity', 0)
            theater = cleaned_data.get('theater_capacity', 0)
            
            # If no capacities are set, set a default seating capacity
            if not any([seating, standing, classroom, theater]):
                cleaned_data['seating_capacity'] = 1
        
        return cleaned_data
    
    def clean_floor_plan(self):
        """Validate floor plan file"""
        floor_plan = self.cleaned_data.get('floor_plan')
        return self.validate_image_file(floor_plan)
    
    def clean_room_photo(self):
        """Validate room photo file"""
        room_photo = self.cleaned_data.get('room_photo')
        return self.validate_image_file(room_photo)


# ============ REVIEW FORMS ============

class ReviewForm(forms.ModelForm):
    """Form for submitting a review"""
    
    class Meta:
        model = Review
        fields = ['rating', 'title', 'comment']
        widgets = {
            'rating': forms.RadioSelect(choices=Review.RATING_CHOICES),
            'title': forms.TextInput(attrs={
                'placeholder': 'Summarize your experience...',
                'class': 'form-control',
                'maxlength': 200
            }),
            'comment': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Share your detailed experience...',
                'class': 'form-control',
                'maxlength': 1000
            }),
        }
        labels = {
            'rating': 'Your Rating',
            'title': 'Review Title',
            'comment': 'Your Review',
        }
    
    def __init__(self, *args, **kwargs):
        self.resource = kwargs.pop('resource', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['rating'].required = True
        self.fields['title'].required = False
        self.fields['comment'].required = True
        
        # Style the radio buttons
        self.fields['rating'].widget.attrs.update({'class': 'rating-input'})
        
        # Check if user has already reviewed this resource
        if self.user and self.resource:
            if Review.objects.filter(user=self.user, resource=self.resource).exists():
                self.fields['comment'].widget.attrs['disabled'] = True
                self.fields['rating'].widget.attrs['disabled'] = True
                self.fields['comment'].help_text = "You have already reviewed this resource."


class ReviewFilterForm(forms.Form):
    """Form for filtering reviews"""
    rating = forms.ChoiceField(
        choices=[('', 'All Ratings')] + [(i, f'{i} ⭐') for i in range(1, 6)],
        required=False
    )
    sort = forms.ChoiceField(
        choices=[
            ('newest', 'Newest First'),
            ('oldest', 'Oldest First'),
            ('highest', 'Highest Rating'),
            ('lowest', 'Lowest Rating'),
            ('helpful', 'Most Helpful'),
        ],
        required=False
    )


# ============ EQUIPMENT FORMS ============

class EquipmentForm(forms.ModelForm, ImageValidationMixin):
    """Form for creating and editing equipment with image support"""
    
    owner = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('username'),
        required=False,
        empty_label="Select an owner (optional)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # ============ NEW IMAGE FIELDS ============
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text="Upload a photo of the equipment (max 5MB)"
    )
    
    remove_image = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Check this box to remove the current image"
    )
    # ============ END NEW IMAGE FIELDS ============
    
    class Meta:
        model = Equipment
        fields = [
            'name', 'category', 'description', 'serial_number', 
            'asset_tag', 'barcode', 'condition', 'status', 'location',
            'purchase_date', 'purchase_price', 'warranty_expiry',
            'notes', 'owner', 'image', 'image_url'  # Added image fields
        ]
        labels = {
            'serial_number': 'Serial Number *',
            'condition': 'Condition',
            'owner': 'Equipment Owner',
            'status': 'Status',
            'image': 'Equipment Photo',
            'image_url': 'Image URL (Alternative)',
        }
        help_texts = {
            'serial_number': 'Must be unique for each equipment item',
            'asset_tag': 'Optional internal tracking number',
            'barcode': 'Optional barcode for scanning',
            'condition': 'Current physical condition of the equipment',
            'location': 'Physical location of the equipment',
            'purchase_price': 'Original purchase price',
            'warranty_expiry': 'When does the warranty expire?',
            'status': 'Current status of the equipment',
            'image': 'Upload a photo of the equipment (JPG, PNG, GIF, WebP). Max 5MB.',
            'image_url': 'Link to an external image (if you don\'t want to upload)',
        }
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Equipment name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Description of the equipment'
            }),
            'serial_number': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Unique serial number'
            }),
            'asset_tag': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Asset tag (optional)'
            }),
            'barcode': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Barcode (optional)'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Current location'
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'form-control', 
                'placeholder': '0.00', 
                'step': '0.01'
            }),
            'warranty_expiry': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2, 
                'placeholder': 'Additional notes'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'image_url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://example.com/equipment-image.jpg'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        # Get the user from kwargs
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make serial_number required
        self.fields['serial_number'].required = True
        
        # Configure category field
        self.fields['category'].queryset = EquipmentCategory.objects.all().order_by('name')
        self.fields['category'].empty_label = 'Select a category...'
        
        # Configure status field - only show if user is staff
        if self.user and not self.user.is_staff:
            self.fields['status'].widget = forms.HiddenInput()
            if not self.instance or not self.instance.pk:
                self.fields['status'].initial = 'AVAILABLE'
        
        # Set owner field based on user permissions
        if self.user:
            if not self.user.is_staff:
                # Regular users can only see their own equipment
                self.fields['owner'].queryset = User.objects.filter(id=self.user.id)
                
                if self.instance and self.instance.pk:
                    # Keep the existing owner
                    self.fields['owner'].initial = self.instance.owner
                    self.fields['owner'].widget = forms.HiddenInput()
                else:
                    # New equipment - set owner to current user
                    self.fields['owner'].initial = self.user
                    self.fields['owner'].widget = forms.HiddenInput()
            else:
                # Staff can assign any owner
                self.fields['owner'].queryset = User.objects.all().order_by('username')
                self.fields['owner'].empty_label = 'Select an owner (optional)'
                if self.instance and self.instance.pk:
                    self.fields['owner'].initial = self.instance.owner
        
        # ============ NEW: Image field configuration ============
        # Add image preview if editing
        if self.instance and self.instance.pk and self.instance.has_image():
            current_image_url = self.instance.get_image_url()
            self.fields['image'].help_text = (
                f'Current image: <a href="{current_image_url}" target="_blank">'
                f'<img src="{current_image_url}" style="max-height: 100px; max-width: 100%; border-radius: 4px; margin-top: 5px;" /></a><br>'
                f'Upload a new image to replace it.'
            )
            self.fields['remove_image'].label = "Remove current image"
            self.fields['remove_image'].help_text = "Check this box to delete the current image"
        
        # Hide remove_image if no image exists
        if not self.instance or not self.instance.pk or not self.instance.has_image():
            self.fields['remove_image'].widget = forms.HiddenInput()
            self.fields['remove_image'].required = False
        
        # ============ END NEW: Image field configuration ============
        
        # Add CSS classes for all visible fields
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.HiddenInput):
                if 'class' not in field.widget.attrs:
                    field.widget.attrs['class'] = 'form-control'
    
    def clean_owner(self):
        """Preserve owner when editing"""
        # If the owner field is not in the data (hidden for regular users)
        if 'owner' not in self.data and self.instance and self.instance.pk:
            # Keep the existing owner
            return self.instance.owner
        return self.cleaned_data.get('owner')
    
    def clean_serial_number(self):
        """Validate serial number uniqueness"""
        serial_number = self.cleaned_data.get('serial_number')
        if serial_number:
            # Check if serial number exists (excluding current instance)
            existing = Equipment.objects.filter(serial_number=serial_number)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('Equipment with this serial number already exists.')
        return serial_number
    
    def clean_asset_tag(self):
        """Validate asset tag uniqueness"""
        asset_tag = self.cleaned_data.get('asset_tag')
        if asset_tag:
            existing = Equipment.objects.filter(asset_tag=asset_tag)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError('Equipment with this asset tag already exists.')
        return asset_tag
    
    def clean_purchase_price(self):
        """Validate purchase price is positive"""
        price = self.cleaned_data.get('purchase_price')
        if price is not None and price < 0:
            raise ValidationError('Purchase price cannot be negative.')
        return price
    
    def clean_purchase_date(self):
        """Validate purchase date is not in the future"""
        date = self.cleaned_data.get('purchase_date')
        if date and date > timezone.now().date():
            raise ValidationError('Purchase date cannot be in the future.')
        return date
    
    def clean_warranty_expiry(self):
        """Validate warranty expiry is after purchase date"""
        expiry = self.cleaned_data.get('warranty_expiry')
        purchase_date = self.cleaned_data.get('purchase_date')
        if expiry and purchase_date and expiry <= purchase_date:
            raise ValidationError('Warranty expiry must be after purchase date.')
        return expiry
    
    # ============ NEW: Image validation methods ============
    def clean_image(self):
        """Validate and process uploaded image"""
        image = self.cleaned_data.get('image')
        if image:
            # Validate file size
            max_size = 5 * 1024 * 1024
            if image.size > max_size:
                raise ValidationError('Image file size cannot exceed 5MB.')
            
            # Validate file type
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            import os
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in valid_extensions:
                raise ValidationError(
                    f"Unsupported file extension. Please use: {', '.join(valid_extensions)}"
                )
            
            # Validate image dimensions (optional - check if image is too large)
            try:
                from PIL import Image
                img = Image.open(image)
                width, height = img.size
                # Optional: Check minimum dimensions
                if width < 200 or height < 200:
                    raise ValidationError('Image must be at least 200x200 pixels.')
                # Optional: Check maximum dimensions
                if width > 4096 or height > 4096:
                    raise ValidationError('Image cannot exceed 4096x4096 pixels.')
            except ImportError:
                # PIL not installed, skip dimension validation
                pass
            except Exception:
                # Invalid image file
                raise ValidationError('Invalid image file. Please upload a valid image.')
        
        # Check if image removal is requested
        remove_image = self.cleaned_data.get('remove_image')
        if remove_image and self.instance and self.instance.pk:
            # If remove_image is checked, don't require a new image
            # The view will handle the removal
            pass
        
        return image
    
    def clean(self):
        """Cross-field validation for images"""
        cleaned_data = super().clean()
        image = cleaned_data.get('image')
        image_url = cleaned_data.get('image_url')
        remove_image = cleaned_data.get('remove_image')
        
        # If removing image, don't require a new one
        if remove_image:
            return cleaned_data
        
        # If no image and no image_url and no existing image, that's fine
        # Images are optional
        return cleaned_data
    # ============ END NEW: Image validation methods ============


class EquipmentImageForm(forms.ModelForm, ImageValidationMixin):
    """Form for uploading and managing equipment gallery images"""
    
    class Meta:
        model = EquipmentImage
        fields = ['image', 'caption', 'is_primary', 'order']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'caption': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional caption...'
            }),
            'is_primary': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'placeholder': '0'
            }),
        }
        labels = {
            'image': 'Image *',
            'caption': 'Caption',
            'is_primary': 'Set as Primary Image',
            'order': 'Display Order',
        }
        help_texts = {
            'image': 'Upload an image for the equipment gallery (max 5MB)',
            'caption': 'Optional description for this image',
            'is_primary': 'Make this the main image for the equipment',
            'order': 'Display order (lower numbers appear first)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['image'].required = True
        
        # If editing, show current image
        if self.instance and self.instance.pk and self.instance.image:
            self.fields['image'].help_text = (
                f'Current image: <a href="{self.instance.image.url}" target="_blank">View</a>'
            )
            self.fields['image'].required = False
    
    def clean_image(self):
        """Validate uploaded image"""
        image = self.cleaned_data.get('image')
        return self.validate_image_file(image)


# ============ BOOKING FORMS ============

class BookingForm(forms.ModelForm):
    """Form for creating a booking"""
    
    class Meta:
        model = Booking
        fields = ['resource', 'start_time', 'end_time', 'notes']
        widgets = {
            'resource': forms.Select(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special requests or notes...'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter resources based on user permissions
        if self.user:
            if not self.user.is_staff:
                self.fields['resource'].queryset = Resource.objects.filter(
                    status='APPROVED'
                ).order_by('name')
        
        # Make notes optional
        self.fields['notes'].required = False
    
    def clean(self):
        """Validate booking times"""
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        resource = cleaned_data.get('resource')
        
        if start_time and end_time:
            if end_time <= start_time:
                raise ValidationError('End time must be after start time.')
            
            if start_time < timezone.now():
                raise ValidationError('Cannot book in the past.')
            
            # Check for overlapping bookings
            if resource:
                overlapping = Booking.objects.filter(
                    resource=resource,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                    status__in=['PENDING', 'CONFIRMED']
                )
                if self.instance and self.instance.pk:
                    overlapping = overlapping.exclude(pk=self.instance.pk)
                
                if overlapping.exists():
                    raise ValidationError('This time slot is already booked.')
        
        return cleaned_data