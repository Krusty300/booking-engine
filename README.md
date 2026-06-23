Django Booking Engine


A comprehensive, production-ready booking engine built with Django. This application allows users to book resources (rooms, equipment, services) with real-time availability checking and double-booking prevention.


Features

User Features

* User Authentication - Login, Signup, and Password Reset
* Resource Management - Browse and book available resources
* Real-time Availability - Check availability by date and time
* Booking Notes - Add notes to your bookings
* Booking Dashboard - View, filter, and cancel your bookings
* Email Notifications - Password reset emails (ready for production)

Technical Features

* Double-Booking Prevention - Database-level locking with `select\_for\_update()`
* AJAX-powered UI - Smooth, interactive user experience
* Responsive Design - Works on desktop, tablet, and mobile
* Custom Font - Mona Sans variable font for modern typography
* SQLite Database - Easy setup, ready for PostgreSQL in production


Quick Start

Prerequisites

\- Python 3.11+

\- pip

\- Git



Installation



1\. Clone the repository:

```bash

git clone https://github.com/YOUR\_USERNAME/booking-engine.git

cd booking-engine

Create and activate virtual environment:

bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
Install dependencies:

bash
pip install -r requirements.txt
Run migrations:

bash
python manage.py makemigrations
python manage.py migrate
Create a superuser:

bash
python manage.py createsuperuser
Run the development server:

bash
python manage.py runserver
Visit http://127.0.0.1:8000 in your browser

Project Structure
text
booking-engine/
├── booking_engine/          # Project settings
├── bookings/               # Main application
│   ├── migrations/         # Database migrations
│   ├── templates/          # HTML templates
│   ├── static/             # Static files (CSS, fonts)
│   ├── admin.py            # Admin interface
│   ├── models.py           # Database models
│   ├── views.py            # View functions
│   ├── services.py         # Business logic
│   ├── forms.py           # Forms
│   └── urls.py            # URL routing
├── manage.py               # Django management script
└── db.sqlite3             # SQLite database



Core Models

Resource
name - Resource name
description - Resource description
created_at - Creation timestamp
Booking
resource - Foreign key to Resource
customer - Foreign key to User
start_time - Booking start time
end_time - Booking end time
status - PENDING, CONFIRMED, CANCELLED, COMPLETED
notes - Optional notes
created_at / updated_at - Timestamps


Security Features
Double-Booking Prevention - Uses database-level locking
CSRF Protection - Django's built-in CSRF middleware
Password Validation - Django's password validators
User Authentication - Session-based authentication
SQL Injection Protection - Django's ORM protection


Technologies Used
Backend: Django 4.2
Frontend: HTML5, CSS3, JavaScript (Vanilla)
Database: SQLite (development), ready for PostgreSQL
Font: Mona Sans variable font
Version Control: Git



Contributing
Fork the repository
Create a feature branch (git checkout -b feature/AmazingFeature)
Commit your changes (git commit -m 'Add some AmazingFeature')
Push to the branch (git push origin feature/AmazingFeature)
Open a Pull Request
License
This project is open source and available under the MIT License.



Author
Your Name
GitHub: @Krusty300



Built with ❤️ using Django

