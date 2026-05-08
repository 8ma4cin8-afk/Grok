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
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            emails.append({
                "subject": subject,
                "body": body[:10000],
                "date": msg["Date"]
            })
        mail.logout()
        return emails
    except Exception as e:
        print(f"BŁĄD pobierania maili: {e}")
        return []


def analyze_with_grok(profile_text, subject):
    prompt = f"""Profil EEN:
Temat: {subject}

Treść:
{profile_text[:8000]}

Przeanalizuj ten profil i przygotuj praktyczny raport matchingowy dla Dolnego Śląska i Opolszczyzny.
Zwróć wynik jako zwykły tekst (niekoniecznie JSON)."""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}"},
            json={
                "model": "grok-4",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1800
            },
            timeout=90
        )
        
        if response.status_code != 200:
            return f"Błąd API Grok: {response.status_code} - {response.text}"
            
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
        print("Raport wysłany pomyślnie")
    except Exception as e:
        print(f"Błąd wysyłania maila: {e}")


def main():
    print(f"[{datetime.now()}] Uruchamiam EEN Matcher...")
    emails = fetch_new_emails()

    print(f"Znaleziono {len(emails)} nowych maili")

    report = f"🔍 RAPORT EEN MATCHING\nData: {datetime.now().strftime('%Y-%m-%d %H:%M')}\nLiczba nowych maili: {len(emails)}\n\n"

    for e in emails:
        print(f"Przetwarzam: {e['subject']}")
        if any(keyword in e["subject"] for keyword in ["Enterprise Europe Network", "EU-CORPORATE-NOTIFICATION-SYSTEM", "Business request", "Only Requests", "Only Offers"]):
            analysis = analyze_with_grok(e["body"], e["subject"])
            report += f"{'='*80}\n"
            report += f"Temat: {e['subject']}\n"
            report += f"Data: {e['date']}\n\n"
            report += analysis
            report += "\n\n"
        else:
            report += f"Pominięty mail: {e['subject']}\n\n"

    print("Wysyłam raport...")
    send_report(report)
    print("Zakończono.")


if __name__ == "__main__":
    main()
