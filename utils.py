"""
Uilities for formatting data in frontend (utils.py)
-------------------------------------
Handles frontend data presentation. 
"""

import re
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template, current_app

def format_date(d_str):
    if not d_str: return ""
    try:
        clean_date = str(d_str).split()[0].split('T')[0]
        return datetime.strptime(clean_date, '%Y-%m-%d').strftime('%m/%d/%Y')
    except:
        return d_str 

def format_phone(phone):
    """
    Convert:
        1234567890 or 1234567890.0 -> (123) 456-7890
    """
    if not phone or phone in ['nan', 'NaN']:
        return ""

    # Catch floats (like 1234567890.0) and convert them to clean strings
    try:
        phone_str = str(int(float(phone)))
    except (ValueError, TypeError):
        phone_str = str(phone)

    # Strip any remaining non-digits (like hyphens or parentheses if already formatted)
    digits = re.sub(r"\D", "", phone_str)

    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    
    # Return the cleaned string, not the raw float, as a fallback
    return phone_str


def unformat_phone(phone):
    """
    Convert:
        (123) 456-7890 -> 1234567890
        123-456-7890  -> 1234567890
        1234567890    -> 1234567890
    """
    if not phone:
        return ""

    digits = re.sub(r"\D", "", str(phone))

    if len(digits) == 10:
        return digits
    return phone

def clean_int(val):
    if val in [None, '', 'nan', 'NaN']: return ""
    try:
        return str(int(float(val)))
    except:
        return str(val)

def group_order_data(items):
    """
    Groups individual bike records into families/orders based on email and date.
    Why: The DB stores one row per bike, but the frontend needs to render one card per order.
    """
    groups = {}
    for item in items:
        key = f"{item['contact_email']}_{item['order_date']}"
        if key not in groups:
            groups[key] = {
                'contact_name': item['contact_name'],
                'contact_phone': format_phone(item['contact_phone_number']),
                'contact_email': item['contact_email'],
                'pedal_partner': item['pedal_partner_name'],
                'order_date': format_date(item['order_date']),
                'order_type': item.get('order_type', 'Standard'),
                'shop_name': item['shop_name'],
                'total_bikes': 0,
                'recipients': []
            }
        groups[key]['total_bikes'] += 1
        item['age'] = clean_int(item['age'])
        item['bike_tag'] = clean_int(item['bike_tag'])
        item['date_picked_up'] = format_date(item['date_picked_up'])
        groups[key]['recipients'].append(item)
    return list(groups.values())

def send_email(to_email, subject, template_name, **kwargs):
    """
    Constructs and sends an HTML email via Gmail SMTP.
    Note: Currently hardcoded to send to the default sender for testing purposes.
    """
    test_recipient = current_app.config['MAIL_DEFAULT_SENDER'] 
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
    msg['To'] = test_recipient 

    html_body = render_template(f"emails/{template_name}.html", **kwargs)
    part = MIMEText(html_body, 'html')
    msg.attach(part)

    try:
        server = smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'])
        server.starttls()
        server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
        server.sendmail(current_app.config['MAIL_DEFAULT_SENDER'], test_recipient, msg.as_string())
        server.quit()
        print(f"Email sent successfully to {test_recipient}")
    except Exception as e:
        print(f"Failed to send email: {e}")