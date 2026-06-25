from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from .models import Resource, Category, UserProfile
from .models import MeetingRoom, Amenity
from .models import Review
from .models import Equipment, EquipmentCategory
import os

class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, required=True, help_text='Required. Enter a valid email address.')
    
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

class ResourceForm(forms.ModelForm):
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
            'image', 'image_url',           # Main resource images
            'room_photo', 'floor_plan',     # Meeting room specific images
        ]
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
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
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
            'room_photo': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'form-control'
            }),
            'floor_plan': forms.FileInput(attrs={
                'accept': 'image/*',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make fields optional
        optional_fields = ['category', 'location', 'max_capacity', 'price_per_hour', 
                          'image', 'image_url', 'room_photo', 'floor_plan',
                          'contact_email', 'contact_phone', 'website', 'tags']
        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
        
        # Configure category field
        if 'category' in self.fields:
            self.fields['category'].empty_label = 'Select a category (optional)'
        
        # Set default contact email to user's email if editing
        if self.instance and self.instance.pk:
            # For edit mode, we could populate from a separate Contact model
            pass
        
        # Add help text to fields
        self.fields['name'].help_text = 'A clear, descriptive name for your resource'
        self.fields['description'].help_text = 'Maximum 1000 characters. Be specific about what you offer.'
        self.fields['max_capacity'].help_text = 'How many people can use this resource at once?'
        self.fields['price_per_hour'].help_text = 'Set to 0.00 for free resources'
        self.fields['image'].help_text = 'Upload a main image for your resource (max 5MB)'
        self.fields['image_url'].help_text = 'Optional: Link to an external image URL'
        self.fields['room_photo'].help_text = 'Upload a photo of the meeting room (max 5MB)'
        self.fields['floor_plan'].help_text = 'Upload a floor plan of the meeting room (max 5MB)'
        
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
                raise ValidationError('A resource with this name already exists. Please choose a different name.')
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
            # Remove spaces and special characters for validation
            import re
            clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
            if not clean_phone.isdigit():
                raise ValidationError('Please enter a valid phone number (digits only).')
        return phone
    
    def clean_image(self):
        """Validate main image file"""
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (max 5MB)
            if image.size > 5 * 1024 * 1024:
                raise ValidationError('Image file size cannot exceed 5MB.')
            
            # Check file extension
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            ext = os.path.splitext(image.name)[1].lower()
            if ext not in valid_extensions:
                raise ValidationError(f"Unsupported file extension. Please use: {', '.join(valid_extensions)}")
        return image
    
    def clean_room_photo(self):
        """Validate room photo file"""
        room_photo = self.cleaned_data.get('room_photo')
        if room_photo:
            # Check file size (max 5MB)
            if room_photo.size > 5 * 1024 * 1024:
                raise ValidationError('Room photo file size cannot exceed 5MB.')
            
            # Check file extension
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            ext = os.path.splitext(room_photo.name)[1].lower()
            if ext not in valid_extensions:
                raise ValidationError(f"Unsupported file extension. Please use: {', '.join(valid_extensions)}")
        return room_photo
    
    def clean_floor_plan(self):
        """Validate floor plan file"""
        floor_plan = self.cleaned_data.get('floor_plan')
        if floor_plan:
            # Check file size (max 5MB)
            if floor_plan.size > 5 * 1024 * 1024:
                raise ValidationError('Floor plan file size cannot exceed 5MB.')
            
            # Check file extension
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            ext = os.path.splitext(floor_plan.name)[1].lower()
            if ext not in valid_extensions:
                raise ValidationError(f"Unsupported file extension. Please use: {', '.join(valid_extensions)}")
        return floor_plan

class ResourceStatusForm(forms.ModelForm):
    """Form for admins to update resource status"""
    
    class Meta:
        model = Resource
        fields = ['status']

class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""
    
    class Meta:
        model = Category
        fields = ['name', 'description', 'icon', 'color', 'max_booking_duration', 'min_booking_duration', 'requires_approval', 'booking_fee']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe this category...'}),
            'icon': forms.TextInput(attrs={'placeholder': 'fa-building, fa-laptop, fa-users, etc.'}),
            'color': forms.TextInput(attrs={'type': 'color', 'style': 'padding: 4px; height: 45px;'}),
            'max_booking_duration': forms.NumberInput(attrs={'min': 1, 'placeholder': 'e.g., 4'}),
            'min_booking_duration': forms.NumberInput(attrs={'min': 1, 'placeholder': 'e.g., 1'}),
            'booking_fee': forms.NumberInput(attrs={'min': 0, 'step': 0.01, 'placeholder': '0.00'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.required = field_name in ['name']

class UserProfileForm(forms.ModelForm):
    """Form for editing user profile"""
    
    class Meta:
        model = UserProfile
        fields = ['bio', 'phone_number', 'location', 'profile_picture', 
                  'website', 'twitter', 'linkedin', 'github',
                  'email_notifications', 'booking_reminders']
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
        if phone:
            import re
            clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
            if not clean_phone.isdigit():
                raise ValidationError('Please enter a valid phone number.')
            if len(clean_phone) < 10:
                raise ValidationError('Phone number must be at least 10 digits.')
        return phone
    
    def clean_profile_picture(self):
        """Validate profile picture"""
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            if picture.size > 2 * 1024 * 1024:
                raise ValidationError('Profile picture cannot exceed 2MB.')
            
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            ext = os.path.splitext(picture.name)[1].lower()
            if ext not in valid_extensions:
                raise ValidationError(f"Unsupported file extension. Please use: {', '.join(valid_extensions)}")
        return picture

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

class MeetingRoomForm(forms.ModelForm):
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
        super().__init__(*args, **kwargs)
        self.fields['rating'].required = True
        self.fields['title'].required = False
        self.fields['comment'].required = True
        
        # Style the radio buttons
        self.fields['rating'].widget.attrs.update({'class': 'rating-input'})

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

class EquipmentForm(forms.ModelForm):
    """Form for creating and editing equipment"""
    
    owner = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('username'),
        required=False,
        empty_label="Select an owner (optional)",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Equipment
        fields = [
            'name', 'category', 'description', 'serial_number', 
            'asset_tag', 'barcode', 'condition', 'location',
            'purchase_date', 'purchase_price', 'warranty_expiry',
            'notes', 'owner'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Equipment name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description of the equipment'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unique serial number'}),
            'asset_tag': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asset tag (optional)'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Barcode (optional)'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Current location'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.01'}),
            'warranty_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Additional notes'}),
        }
        labels = {
            'serial_number': 'Serial Number *',
            'condition': 'Condition',
            'owner': 'Equipment Owner',
        }
        help_texts = {
            'serial_number': 'Must be unique for each equipment item',
            'asset_tag': 'Optional internal tracking number',
        }
    
    def __init__(self, *args, **kwargs):
        # Get the user from kwargs before calling super()
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Make serial_number required
        self.fields['serial_number'].required = True
        
        # Add empty option for category
        self.fields['category'].queryset = EquipmentCategory.objects.all().order_by('name')
        self.fields['category'].empty_label = 'Select a category...'
        
        # Set owner field based on user permissions
        if self.user:
            if not self.user.is_staff:
                # Regular users can only see their own equipment
                self.fields['owner'].queryset = User.objects.filter(id=self.user.id)
                
                # If editing existing equipment, preserve the current owner
                if self.instance and self.instance.pk:
                    # Keep the existing owner
                    self.fields['owner'].initial = self.instance.owner
                    # Hide the field (regular users can't change owner)
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
                raise forms.ValidationError('Equipment with this serial number already exists.')
        return serial_number
    
    def clean_purchase_price(self):
        """Validate purchase price is positive"""
        price = self.cleaned_data.get('purchase_price')
        if price is not None and price < 0:
            raise forms.ValidationError('Purchase price cannot be negative.')
        return price