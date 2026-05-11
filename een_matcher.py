import imaplib
import email
import os
from datetime import datetime
from email.header import decode_header
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import re
import json

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GROK_API_KEY = os.getenv("GROK_API_KEY")
REPORT_TO = "marcin.jablonski@pwr.edu.pl"

def main():
    print("=== START EEN MATCHER ===")
    
    # Test wysyłki
    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = REPORT_TO
    msg['Subject'] = f"Test Raport EEN - {datetime.now().strftime('%H:%M')}"

    body = f"""Test raportu EEN Matching
Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Skrypt działa i wysyła maile.
Jeśli widzisz tę wiadomość - automatyzacja jest aktywna."""

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Testowy mail wysłany pomyślnie!")
    except Exception as e:
        print(f"BŁĄD wysyłki: {e}")

if __name__ == "__main__":
    main()
