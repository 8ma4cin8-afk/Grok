import imaplib
import email
import os
from datetime import datetime
from email.header import decode_header
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

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
        email_ids = messages[0].split()[-20:]

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
                    if part.get_content_type() in ["text/plain", "text/html"]:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode(errors="ignore")
                            break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            emails.append({
                "subject": subject,
                "body": body[:15000],
                "date": msg["Date"]
            })
        mail.logout()
        return emails
    except Exception as e:
        print(f"BŁĄD pobierania maili: {e}")
        return []


def analyze_with_grok(profile_text, subject):
    prompt = f"""Przeanalizuj poniższy profil EEN i przygotuj praktyczny raport matchingowy dla Dolnego Śląska i Opolszczyzny.

Temat: {subject}

Treść:
{profile_text}

Napisz czytelny, konkretny raport z oceną potencjału, sugestiami typów firm i gotowym fragmentem wiadomości do firmy."""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-4.3",          # <-- zmienione na aktualny model
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000
            },
            timeout=120
        )

        print(f"Status API: {response.status_code}")

        if response.status_code != 200:
            print("Pełna odpowiedź błędu:", response.text)
            return f"BŁĄD API ({response.status_code}): {response.text[:500]}"

        result = response.json()
        
        # Lepsze debugowanie
        if "choices" not in result:
            print("Brak 'choices' w odpowiedzi:", json.dumps(result, indent=2)[:1000])
            return "BŁĄD: Nieprawidłowa struktura odpowiedzi z Grok"

        return result["choices"][0]["message"]["content"]

    except Exception as e:
        print(f"Wyjątek przy wywołaniu Grok: {e}")
        return f"BŁĄD GROK: {str(e)}"


def send_report(report_content):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = REPORT_TO
    msg['Subject'] = f"Raport EEN Matching - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    msg.attach(MIMEText(report_content, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Raport wysłany pomyślnie")
    except Exception as e:
        print(f"Błąd wysyłania: {e}")


def main():
    print(f"[{datetime.now()}] Start EEN Matcher")
    emails = fetch_new_emails()
    print(f"Znaleziono {len(emails)} nowych maili")

    report = f"🔍 RAPORT EEN MATCHING\nData: {datetime.now().strftime('%Y-%m-%d %H:%M')}\nLiczba maili: {len(emails)}\n\n"

    for e in emails:
        subject_lower = e["subject"].lower()
        print(f"Mail: {e['subject']}")

        if any(k in subject_lower for k in ["profile", "enterprise", "business", "request", "offer", "query", "partnering"]):
            analysis = analyze_with_grok(e["body"], e["subject"])
            report += f"{'='*80}\nTemat: {e['subject']}\nData: {e['date']}\n\n{analysis}\n\n"
        else:
            report += f"Pominięty: {e['subject']}\n\n"

    send_report(report)
    print("Zakończono.")

if __name__ == "__main__":
    main()
