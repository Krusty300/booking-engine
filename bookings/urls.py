from django.urls import path
from . import views

urlpatterns = [
    # ============ AUTHENTICATION ============
    path('signup/', views.signup, name='signup'),

    # ============ RESOURCE LISTING AND BOOKING ============
    path('', views.resource_list, name='resource_list'),
    path('resource/<int:resource_id>/', views.resource_detail, name='resource_detail'),
    
    # ============ USER RESOURCE MANAGEMENT ============
    path('my-resources/', views.my_resources, name='my_resources'),
    path('resource/create/', views.create_resource, name='create_resource'),
    path('resource/<int:resource_id>/edit/', views.edit_resource, name='edit_resource'),
    path('resource/<int:resource_id>/delete/', views.delete_resource, name='delete_resource'),

    # ============ USER PROFILE ============
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('booking-history/', views.booking_history, name='booking_history'),
    
    # ============ ADMIN RESOURCE MANAGEMENT ============
    path('manage-resources/', views.admin_manage_resources, name='admin_manage_resources'),
    path('manage-resource/<int:resource_id>/status/', views.admin_update_resource_status, name='admin_update_resource_status'),
    path('analytics/', views.admin_dashboard, name='admin_dashboard'),
    path('analytics/data/', views.analytics_data, name='analytics_data'),
    
    # ============ BOOKING MANAGEMENT ============
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('cancel-booking/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('my-bookings/export/', views.export_bookings, name='export_bookings'),
    
    # ============ CATEGORY MANAGEMENT (Admin Only) ============
    path('categories/', views.manage_categories, name='manage_categories'),
    path('category/create/', views.create_category, name='create_category'),
    path('category/<int:category_id>/edit/', views.edit_category, name='edit_category'),
    path('category/<int:category_id>/delete/', views.delete_category, name='delete_category'),

    # ============ EQUIPMENT RENTAL SYSTEM ============
    path('equipment/', views.equipment_list, name='equipment_list'),
    path('equipment/<int:equipment_id>/', views.equipment_detail, name='equipment_detail'),
    path('my-rentals/', views.my_rentals, name='my_rentals'),
    path('equipment/rent/', views.rent_equipment, name='rent_equipment'),
    path('equipment/return/', views.return_equipment, name='return_equipment'),
    path('equipment-maintenance/', views.equipment_maintenance, name='equipment_maintenance'),
    path('equipment-maintenance/complete/', views.complete_maintenance, name='complete_maintenance'),
    path('equipment-maintenance/<int:maintenance_id>/', views.maintenance_detail, name='maintenance_detail'),
    path('equipment-dashboard/', views.equipment_dashboard, name='equipment_dashboard'),
    path('equipment/', views.equipment_list, name='equipment_list'),
    path('equipment/<int:equipment_id>/', views.equipment_detail, name='equipment_detail'), 

    # ============ USER EQUIPMENT MANAGEMENT ============
    path('my-equipment/', views.my_equipment, name='my_equipment'),
    path('equipment/create/', views.create_equipment, name='create_equipment'),
    path('equipment/<int:equipment_id>/edit/', views.edit_equipment, name='edit_equipment'),
    path('equipment/<int:equipment_id>/delete/', views.delete_equipment, name='delete_equipment'),
    
    # ============ CALENDAR VIEW ============
    path('calendar/', views.CalendarView.as_view(), name='calendar_view'),

    # ============ REVIEWS ============
    path('resource/<int:resource_id>/write-review/', views.write_review, name='write_review'),
    path('review/<int:review_id>/edit/', views.edit_review, name='edit_review'),
    path('review/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    path('my-reviews/', views.my_reviews, name='my_reviews'),
    path('my-review-history/', views.my_review_history, name='my_review_history'),
    path('resource/<int:resource_id>/reviews/', views.resource_reviews, name='resource_reviews'),
    path('api/review/<int:review_id>/helpful/', views.toggle_review_helpful, name='toggle_review_helpful'),

    # ============ ADMIN REVIEW MANAGEMENT ============
    path('reviews-admin/', views.admin_reviews, name='admin_reviews'),
    path('reviews-admin/<int:review_id>/', views.admin_review_detail, name='admin_review_detail'),
    path('reviews-admin/bulk-action/', views.admin_bulk_action_reviews, name='admin_bulk_action_reviews'),
    
    # ============ API ENDPOINTS ============
    path('api/available-times/', views.get_available_times, name='get_available_times'),
    path('api/book/', views.book_slot, name='book_slot'),
]