import imaplib
import email
import os
import json
from datetime import datetime
from email.header import decode_header
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ================== KONFIGURACJA ==================
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GROK_API_KEY = os.getenv("GROK_API_KEY")
REPORT_TO = "marcin.jablonski@pwr.edu.pl"

# =================================================

def fetch_new_emails():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        _, messages = mail.search(None, 'UNSEEN')
        email_ids = messages[0].split()[-15:]  # ostatnie 15 maili

        emails = []
        for eid in email_ids:
            _, msg_data = mail.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            emails.append({
                "subject": subject,
                "body": body[:8000],  # limit dla Grok
                "date": msg["Date"]
            })

        mail.logout()
        return emails
    except Exception as e:
        print(f"Błąd pobierania maili: {e}")
        return []


def analyze_with_grok(profile_text):
    prompt = f"""Jesteś bardzo dobrym ekspertem matchmakingu EEN. 

Przeanalizuj poniższy profil i przygotuj **rozbudowany, praktyczny raport** dla konsultanta z Dolnego Śląska i Opolszczyzny.

Profil:
{profile_text}

Zrób analizę w formacie JSON:
{{
  "profile_id": "...",
  "score": 8,
  "potential": "Wysoki/Średni/Niski",
  "partner_type": "krótki opis typu firmy",
  "justification": "szczegółowe uzasadnienie",
  "search_keywords": ["słowo1", "słowo2", ...],
  "email_template": "Szanowni Państwo,\\n\\n..."
}}

Bądź konkretny i praktyczny."""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}"},
            json={
                "model": "grok-4",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000
            },
            timeout=60
        )
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Błąd Grok: {str(e)}"


def send_report(report_content):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = REPORT_TO
    msg['Subject'] = f"Raport EEN Matching - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    msg.attach(MIMEText(report_content, 'plain'))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Raport wysłany pomyślnie")
    except Exception as e:
        print(f"Błąd wysyłania: {e}")


def main():
    print("Uruchamiam EEN Matcher...")
    emails = fetch_new_emails()

    if not emails:
        print("Brak nowych maili EEN")
        return

    report = f"🔍 RAPORT EEN MATCHING\nData: {datetime.now().strftime('%Y-%m-%d %H:%M')}\nLiczba nowych maili: {len(emails)}\n\n"

    for e in emails:
        if any(x in e["subject"] for x in ["Enterprise Europe Network", "EU-CORPORATE-NOTIFICATION-SYSTEM", "Business request", "Only Requests"]):
            print(f"Analizuję: {e['subject']}")
            analysis = analyze_with_grok(e["body"])
            report += f"{'='*60}\n"
            report += f"Temat: {e['subject']}\n"
            report += analysis + "\n\n"

    send_report(report)
    print("Zakończono przetwarzanie.")


if __name__ == "__main__":
    main()
