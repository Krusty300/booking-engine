from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

def send_review_submitted_email(review):
    """Send email notification when a review is submitted"""
    subject = f'New Review Submitted for {review.resource.name}'
    message = f"""
    A new review has been submitted for {review.resource.name}.
    
    Title: {review.title}
    Rating: {review.rating} stars
    Comment: {review.comment}
    
    Please log in to the admin panel to moderate this review.
    """
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [settings.ADMINS[0][1]] if settings.ADMINS else [],
        fail_silently=True,
    )

def send_review_approved_email(review):
    """Send email notification when a review is approved"""
    subject = f'Your Review for {review.resource.name} has been Approved'
    message = f"""
    Your review for {review.resource.name} has been approved and is now visible to the public.
    
    Title: {review.title}
    Rating: {review.rating} stars
    
    Thank you for your contribution!
    """
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [review.user.email],
        fail_silently=True,
    )

def send_review_rejected_email(review):
    """Send email notification when a review is rejected"""
    subject = f'Your Review for {review.resource.name} has been Rejected'
    message = f"""
    Your review for {review.resource.name} has been rejected.
    
    Title: {review.title}
    Rating: {review.rating} stars
    Reason: {review.moderation_reason or 'Not specified'}
    
    If you have any questions, please contact the administrator.
    """
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [review.user.email],
        fail_silently=True,
    )