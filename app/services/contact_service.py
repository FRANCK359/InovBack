from flask_mail import Message
from app import mail
from flask import current_app
from threading import Thread

class ContactService:

    @staticmethod
    def send_async_email(app, msg):
        """Send email asynchronously"""
        with app.app_context():
            mail.send(msg)

    @staticmethod
    def send_notification_email(contact_message):
        """Send notification about new contact message"""
        if not current_app.config.get('MAIL_SERVER'):
            current_app.logger.warning("Email not configured - skipping notification")
            return
        
        subject = f"New contact message: {contact_message['subject']}"
        recipients = [current_app.config.get('MAIL_DEFAULT_SENDER')]
        
        msg = Message(
            subject=subject,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER'),
            recipients=recipients
        )
        
        msg.body = f"""
You have received a new contact message:

From: {contact_message['name']} <{contact_message['email']}>
Subject: {contact_message['subject']}
Message:
{contact_message['message']}

Received at: {contact_message['created_at']}
"""
        # Send email in background thread
        Thread(target=ContactService.send_async_email, args=(current_app._get_current_object(), msg)).start()
