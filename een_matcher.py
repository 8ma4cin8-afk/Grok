import imaplib
import email
import os
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
        email_ids = messages[0].split()[-30:]  

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
                "body": body[:12000],
                "date": msg["Date"]
            })
        mail.logout()
        return emails
    except Exception as e:
        print(f"BŁĄD pobierania: {e}")
        return []


def analyze_with_grok(profile_text, subject):
    prompt = f"""Jesteś ekspertem EEN. Przeanalizuj poniższy profil partneringowy i przygotuj praktyczny, rozbudowany raport matchingowy dla regionu Dolny Śląsk + Opolszczyzna.

Temat maila: {subject}

Treść profilu:
{profile_text}

Przygotuj raport w czytelnej formie (nie JSON)."""
    
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
            timeout=90
        )
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
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
        print("Raport wysłany")
    except Exception as e:
        print(f"Błąd wysyłki: {e}")


def main():
    print(f"[{datetime.now()}] Start EEN Matcher")
    emails = fetch_new_emails()

    report = f"🔍 RAPORT EEN MATCHING\nData: {datetime.now().strftime('%Y-%m-%d %H:%M')}\nLiczba maili: {len(emails)}\n\n"

    for e in emails:
        subject_lower = e["subject"].lower()
        print(f"Znaleziony mail: {e['subject']}")

        # Rozszerzone filtrowanie
        if any(k in subject_lower for k in ["enterprise", "profiles query", "business request", "only requests", "only offers", "technological", "eu-corporate", "partnering"]):
            print(f"→ Analizuję profil: {e['subject']}")
            analysis = analyze_with_grok(e["body"], e["subject"])
            report += f"{'='*80}\n"
            report += f"Temat: {e['subject']}\n"
            report += f"Data: {e['date']}\n\n"
            report += analysis + "\n\n"
        else:
            report += f"Pominięty mail: {e['subject']}\n\n"

    send_report(report)
    print("Zakończono przetwarzanie.")


if __name__ == "__main__":
    main()
