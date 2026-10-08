"""
Presentation, order queries and guarded email delivery (utils.py)
-------------------------------------
Handles frontend data presentation. 
"""

import re
from datetime import datetime
import smtplib
import ssl
import os
from pathlib import Path
from dataclasses import dataclass
from uuid import uuid4
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import render_template, current_app, flash
from database import get_db_connection
from order_search import canonical_order_type, normalize_text

def format_date(d_str):
    if not d_str: return ""
    try:
        clean_date = str(d_str).split()[0].split('T')[0]
        parsed = datetime.strptime(clean_date, '%Y-%m-%d')
        return f'{parsed.month:02d}/{parsed.day:02d}/{parsed.year:04d}'
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


def clean_int(val):
    if val in [None, '', 'nan', 'NaN']: return ""
    try:
        return str(int(float(val)))
    except:
        return str(val)

@dataclass(frozen=True)
class EmailResult:
    status: str
    preview_path: str | None = None

    def __bool__(self):
        return self.status == 'sent'


def email_feedback(results, failure_message):
    statuses = {getattr(result, 'status', 'sent' if result else 'failed') for result in results}
    if 'failed' in statuses:
        flash(failure_message, 'warning')
    if 'preview' in statuses:
        flash('Email preview saved locally. No email was sent.', 'info')
    if 'test' in statuses:
        flash('Email delivered to the configured test inbox only.', 'info')
    if 'disabled' in statuses:
        flash('Email is disabled. No email was sent.', 'info')


def _single_email(value):
    # No recipient lists, display-name parsing, or extra header fields.
    if not isinstance(value, str) or not re.fullmatch(r'[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+', value):
        raise ValueError('A single email address is required.')
    return value


def send_email(to_email, subject, template_name, **kwargs):
    """Preview locally by default. Delivery requires an explicit test/live mode."""
    if to_email is None or (isinstance(to_email, str) and not to_email.strip()):
        return EmailResult('skipped')
    try:
        mode = current_app.config.get('EMAIL_MODE', 'preview')
        if mode == 'disabled':
            return EmailResult('disabled')
        if mode not in {'preview', 'test', 'live'}:
            raise ValueError('Unknown email mode; delivery blocked.')
        if template_name not in {'order_received', 'pickup_ready', 'pickup_reminder'}:
            raise ValueError('Unknown email template.')
        html_body = render_template(f'emails/{template_name}.html', **kwargs)
        if mode == 'preview':
            folder = Path(current_app.config.get('EMAIL_PREVIEW_DIR', 'data/email_previews')).resolve()
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            # A separate preview shell escapes metadata and does not request remote assets.
            preview = render_template('emails/preview.html', subject=subject,
                                      intended_recipient=to_email, email_html=html_body)
            path = folder / f'{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex}.html'
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(preview)
            current_app.logger.info('Email preview saved locally; no delivery attempted.')
            return EmailResult('preview', str(path))

        # Gate before connecting or authenticating, even if credentials already exist.
        if mode == 'live' and current_app.config.get('EMAIL_LIVE_ENABLED') is not True:
            raise ValueError('Live email has not been enabled.')
        recipient = _single_email(current_app.config.get('MAIL_TEST_RECIPIENT') if mode == 'test' else to_email)
        sender = _single_email(current_app.config.get('MAIL_DEFAULT_SENDER'))
        required = ('MAIL_SERVER', 'MAIL_PORT', 'MAIL_USERNAME', 'MAIL_PASSWORD')
        if not all(current_app.config.get(key) for key in required):
            raise ValueError('Mail settings are incomplete.')
        msg = MIMEMultipart('alternative')
        msg['Subject'] = ('[TEST] ' if mode == 'test' else '') + subject
        msg['From'] = sender
        msg['To'] = recipient
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))
        with smtplib.SMTP(current_app.config['MAIL_SERVER'], current_app.config['MAIL_PORT'], timeout=10) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(current_app.config['MAIL_USERNAME'], current_app.config['MAIL_PASSWORD'])
            refused = server.sendmail(sender, [recipient], msg.as_string())
            if refused:
                raise ValueError('Mail server refused the recipient.')
        return EmailResult('test' if mode == 'test' else 'sent')
    except Exception as exc:
        # Do not put email contents, recipient addresses, or SMTP credentials in logs.
        current_app.logger.warning('Email not delivered (%s).', type(exc).__name__)
        return EmailResult('failed')

def fetch_all_orders():
    """
    Executes the master join query, cleans formats (dates, phones, ints),
    and returns a list of dictionaries ready for any frontend view.
    """
    conn = get_db_connection()
    query = '''
    SELECT 
        o.*,
        c.contact_name,
        c.contact_email,
        c.contact_phone_number,
        p.pedal_partner_name,
        s.shop_location,
        r.recipient_name,
        r.age AS recipient_age,
        r.height AS recipient_height,
        r.bike_style_preference AS recipient_bike_style_preference,
        r.bike_type_first_choice AS recipient_bike_type_first_choice,
        r.bike_type_second_choice AS recipient_bike_type_second_choice,
        o.pickup_date AS date_picked_up
    FROM orders o
    LEFT JOIN contacts c ON o.contact_id = c.contact_id
    LEFT JOIN recipients r ON o.recipient_id = r.recipient_id
    LEFT JOIN shops s ON o.shop_name = s.shop_name
    LEFT JOIN pedal_partners p ON o.pedal_partner_id = p.pedal_partner_id;
    '''
    raw_items = conn.execute(query).fetchall()
    conn.close()

    items = []
    for row in raw_items:
        row_dict = dict(row)
        raw_values = [str(value) for value in row_dict.values() if value is not None]
        row_dict['order_date_iso'] = row_dict.get('order_date') or ''
        row_dict['pickup_date_iso'] = row_dict.get('date_picked_up') or ''
        row_dict['order_type'] = canonical_order_type(row_dict.get('order_type'))
        for field in ('age', 'height', 'bike_style_preference'):
            if row_dict.get('recipient_' + field) is not None:
                row_dict[field] = row_dict['recipient_' + field]
        for field in ('bike_type_first_choice', 'bike_type_second_choice'):
            row_dict[field] = row_dict.get(field) or row_dict.get('recipient_' + field)
        
        # Fallback for legacy records missing a status
        if not row_dict.get('order_status'):
            row_dict['order_status'] = 'Completed' if row_dict.get('date_picked_up') else 'Open'
            
        # Clean formatting directly at the source
        row_dict['contact_phone_number'] = format_phone(row_dict.get('contact_phone_number'))
        row_dict['order_date'] = format_date(row_dict.get('order_date'))
        row_dict['date_picked_up'] = format_date(row_dict.get('date_picked_up'))
        row_dict['age'] = clean_int(row_dict.get('age'))
        row_dict['bike_tag'] = clean_int(row_dict.get('bike_tag'))
        display_values = [str(value) for value in row_dict.values() if value is not None]
        if row_dict['order_type'] == 'Speciality':
            display_values.append('Specialty')
        row_dict['_search_text'] = normalize_text(' '.join(raw_values + display_values))
        
        items.append(row_dict)
        
    return items
