
Waystack - Django Booking Engine

A comprehensive, production-ready booking engine built with Django. This application allows users to book resources (rooms, equipment, services) with real-time availability checking, double-booking prevention, and a full-featured user management system.

Features

User Features
- **User Authentication** - Login, Signup, and Password Reset with email notifications
- **User Profiles** - Customizable profiles with profile pictures, bio, social links, and preferences
- **Booking History** - Complete booking history with filtering and search capabilities
- **Booking Dashboard** - View, filter, and cancel your bookings
- **Booking Notes** - Add notes to your bookings
- **Booking Reminders** - Automatic email reminders for upcoming bookings

Resource Management
- **Create Resources** - Users can create their own resources
- **Edit Resources** - Update your resource details
- **Delete Resources** - Remove resources you created
- **Resource Images** - Upload and display images for resources
- **Resource Categories** - Categorize resources with custom colors and icons
- **Resource Status** - Pending, Approved, Rejected, Inactive (with admin moderation)
- **Category-specific Rules** - Set booking rules per category (min/max duration, approval, fees)

Booking System
- **Real-time Availability** - Check availability by date and time
- **Hourly Slots** - Book hourly slots (9 AM - 5 PM)
- **Double-Booking Prevention** - Database-level locking with `select_for_update()`
- **AJAX-powered UI** - Smooth, interactive user experience
- **Nairobi Timezone** - All times displayed in Nairobi (UTC+3)

Admin Features
- **Admin Dashboard** - Manage all resources and bookings
- **Resource Moderation** - Approve, reject, or deactivate resources
- **Category Management** - Create and manage resource categories
- **User Management** - Manage users and their permissions
- **Bulk Actions** - Quick status updates for resources

UI/UX
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Custom Font** - Mona Sans variable font for modern typography
- **Zero Border-radius Design** - Clean, flat design aesthetic
- **Interactive Elements** - Hover effects, transitions, and animations
- **Auto-dismiss Messages** - Notifications that disappear after a few seconds
- **Status Badges** - Visual indicators for resource and booking statuses

Security Features
- **Double-Booking Prevention** - Uses database-level locking
- **CSRF Protection** - Django's built-in CSRF middleware
- **Password Validation** - Django's password validators
- **User Authentication** - Session-based authentication
- **SQL Injection Protection** - Django's ORM protection
- **Role-Based Access** - Admin and regular user permissions

## **Real-World Use Cases**

### **1. Meeting Room Booking**

- Employees book conference rooms
    
- View availability on calendar
    
- Avoid double-booking
    
- Add meeting notes
    

### **2. Equipment Rental**

- Rent out equipment (projectors, laptops)
    
- Track availability
    
- Set pricing per hour/day
    
- Manage rental history
    

### **3. Service Booking**

- Book tutoring sessions
    
- Schedule consultations
    
- Set capacity limits
    
- Add special requests
    

### **4. Event Space Booking**

- Reserve event venues
    
- Set capacity limits
    
- View availability calendar
    
- Track bookings

Quick Start

Prerequisites
- Python 3.11+
- pip
- Git

Installation

1. **Clone the repository:**
```bash
git clone https://github.com/YOUR_USERNAME/booking-engine.git
cd booking-engine
```

2. **Create and activate virtual environment:**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Run migrations:**
```bash
python manage.py makemigrations
python manage.py migrate
```

5. **Create a superuser:**
```bash
python manage.py createsuperuser
```

6. **Run the development server:**
```bash
python manage.py runserver
```

7. **Visit**: `http://127.0.0.1:8000` in your browser

Creating Categories
Before creating resources, you need to create categories:
1. Log in as admin
2. Go to Admin Dashboard → Categories
3. Create categories like "Meeting Rooms", "Equipment", "Services"

Project Structure

```
booking-engine/
├── booking_engine/              # Project settings
│   ├── settings.py              # Configuration
│   └── urls.py                  # Main URLs
├── bookings/                    # Main application
│   ├── migrations/              # Database migrations
│   ├── templates/               # HTML templates
│   │   ├── bookings/            # Main templates
│   │   │   ├── base.html        # Base template with navigation
│   │   │   ├── resource_list.html
│   │   │   ├── resource_detail.html
│   │   │   ├── resource_form.html
│   │   │   ├── my_resources.html
│   │   │   ├── my_bookings.html
│   │   │   ├── profile.html
│   │   │   ├── edit_profile.html
│   │   │   ├── booking_history.html
│   │   │   ├── admin_manage_resources.html
│   │   │   └── manage_categories.html
│   │   └── registration/        # Auth templates
│   │       ├── login.html
│   │       ├── signup.html
│   │       └── password_reset_*.html
│   ├── static/                  # Static files
│   │   └── bookings/
│   │       ├── fonts/           # Mona Sans font
│   │       └── images/          # Default images
│   ├── admin.py                 # Admin interface
│   ├── models.py                # Database models
│   ├── views.py                 # View functions
│   ├── services.py              # Business logic
│   ├── forms.py                 # Forms
│   └── urls.py                  # App URLs
├── media/                       # User uploaded files
├── manage.py                    # Django management script
├── requirements.txt             # Dependencies
├── README.md                    # This file
└── LICENSE                      # MIT License
```

Core Models

Category
- `name` - Category name
- `slug` - URL-friendly identifier
- `description` - Category description
- `icon` - Font Awesome icon class
- `color` - Hex color code
- `max_booking_duration` - Maximum hours per booking
- `min_booking_duration` - Minimum hours per booking
- `requires_approval` - Admin approval required for bookings
- `booking_fee` - Additional fee for bookings

Resource
- `name` - Resource name
- `description` - Resource description
- `owner` - User who created the resource
- `status` - PENDING, APPROVED, REJECTED, INACTIVE
- `category` - Foreign key to Category
- `location` - Resource location
- `max_capacity` - Maximum people per booking
- `price_per_hour` - Cost per hour
- `image` - Uploaded image
- `image_url` - External image URL

Booking
- `resource` - Foreign key to Resource
- `customer` - Foreign key to User
- `start_time` - Booking start time
- `end_time` - Booking end time
- `status` - PENDING, CONFIRMED, CANCELLED, COMPLETED
- `notes` - Optional booking notes

UserProfile
- `user` - One-to-one relationship with User
- `bio` - User bio
- `phone_number` - Contact number
- `location` - User location
- `profile_picture` - Uploaded avatar
- `website`, `twitter`, `linkedin`, `github` - Social links
- `email_notifications` - Email preference
- `booking_reminders` - Reminder preference

Pages Overview

| Page | URL | Description |
|------|-----|-------------|
| Home | `/` | List of available resources with category filters |
| Resource Detail | `/resource/<id>/` | View resource details and book slots |
| My Resources | `/my-resources/` | Manage your created resources |
| Create Resource | `/resource/create/` | Create a new resource |
| Edit Resource | `/resource/<id>/edit/` | Edit your resource |
| My Bookings | `/my-bookings/` | View and manage your bookings |
| Profile | `/profile/` | View your profile and stats |
| Edit Profile | `/profile/edit/` | Update your profile |
| Booking History | `/booking-history/` | Full booking history with filters |
| Admin Resources | `/manage-resources/` | Admin: Manage all resources |
| Categories | `/categories/` | Admin: Manage categories |

Admin Features

Access Admin Panel
```bash
# Login at /admin/ with superuser credentials
# Or use the Admin dropdown in the navigation
```

Admin Capabilities
- Approve/Reject resources
- Change resource status
- Create/Edit/Delete categories
- View all resources and bookings
- Manage users

Technologies Used

Backend
- **Django 4.2** - Python web framework
- **SQLite** - Development database (PostgreSQL ready for production)
- **Pillow** - Image processing

Frontend
- **HTML5** - Semantic markup
- **CSS3** - Custom styling (zero border-radius)
- **JavaScript** - Vanilla JS for interactivity
- **Mona Sans** - Variable font

Tools
- **Git** - Version control
- **GitHub** - Repository hosting

Screenshots

Homepage with Category Filters
```
[Add screenshot: resource_list.png]
```

Resource Detail with Availability
```
[Add screenshot: resource_detail.png]
```

Booking History with Filters
```
[Add screenshot: booking_history.png]
```

User Profile
```
[Add screenshot: profile.png]
```

Admin Dashboard
```
[Add screenshot: admin_dashboard.png]
```

Future Enhancements

- [ ]  Email notifications for booking confirmations
- [ ]  Calendar view for availability
- [ ]  Payment integration (Stripe/PayPal)
- [ ]  Mobile app REST API
- [ ]  Real-time notifications with WebSockets
- [ ]  Admin analytics dashboard
- [ ]  Multi-language support
- [ ]  Two-factor authentication
- [ ]  Resource reviews and ratings
- [ ]  Booking waitlist feature
- [ ]  Advanced search and filtering
- [ ]  Dark mode support

Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

License

This project is open source and available under the MIT License.

Project Author
GitHub: https://github.com/Krusty300/Waystar-Booking-Engine


Acknowledgments

- Django Community for the amazing framework
- Mona Sans font for the beautiful typography
- All contributors and users of this project


Built using Django
