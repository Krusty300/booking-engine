from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from .models import Resource, Category, UserProfile
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
            'max_capacity', 'price_per_hour', 'image', 'image_url',
            # We'll save extra fields to a JSON field or separate model later
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
            'image_url': forms.URLInput(attrs={
                'placeholder': 'https://example.com/image.jpg',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make fields optional
        optional_fields = ['category', 'location', 'max_capacity', 'price_per_hour', 'image', 'image_url', 
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
        """Validate image file"""
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