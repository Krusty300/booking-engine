from django.urls import path
from . import views

urlpatterns = [
    # Resource listing and booking
    path('', views.resource_list, name='resource_list'),
    path('resource/<int:resource_id>/', views.resource_detail, name='resource_detail'),
    
    # User resource management
    path('my-resources/', views.my_resources, name='my_resources'),
    path('resource/create/', views.create_resource, name='create_resource'),
    path('resource/<int:resource_id>/edit/', views.edit_resource, name='edit_resource'),
    path('resource/<int:resource_id>/delete/', views.delete_resource, name='delete_resource'),

    # User profile
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('booking-history/', views.booking_history, name='booking_history'),
    
    # Admin resource management
    path('manage-resources/', views.admin_manage_resources, name='admin_manage_resources'),
    path('manage-resource/<int:resource_id>/status/', views.admin_update_resource_status, name='admin_update_resource_status'),
    
    # Booking management
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    
    # Authentication
    path('signup/', views.signup, name='signup'),
    
    # API endpoints
    path('api/available-times/', views.get_available_times, name='get_available_times'),
    path('api/book/', views.book_slot, name='book_slot'),
    
    # Category management (admin only)
    path('categories/', views.manage_categories, name='manage_categories'),
    path('category/create/', views.create_category, name='create_category'),
    path('category/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('category/<int:category_id>/delete/', views.delete_category, name='delete_category'),

]