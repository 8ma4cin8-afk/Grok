import imaplib
import email
import os
from datetime import datetime
from email.header import decode_header
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import re

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
        email_ids = messages[0].split()[-12:]

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
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            emails.append({"subject": subject, "body": body[:12000], "date": msg["Date"]})
        mail.logout()
        return emails
    except Exception as e:
        print(f"BŁĄD pobierania: {e}")
        return []


def analyze_with_grok(profile_text, subject):
    prompt = f"""Jesteś moim specjalistą EEN od matchingu dla Dolnego Śląska i Opolszczyzny.

Użyj dokładnie tego formatu dla każdego profilu:

**Profil:** {subject}

**Ocena potencjału:** Wysoki / Średni / Niski (X/10)

**Opis:** (2-3 zdania)

**Zaktualizowana tabela z kontaktami dla profilu {subject.split()[0] if subject else 'Profil'}**

| Priorytet | Firma | Lokalizacja | Kontakt (tel + email) | Strona www | Komentarz |
|-----------|-------|-------------|-----------------------|------------|---------|

**Gotowy szablon maila:**

---
[pełny profesjonalny mail]
---

Profil do analizy:
{profile_text[:11000]}"""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}"},
            json={
                "model": "grok-3",           # szybszy model
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1800
            },
            timeout=180                      # mocno zwiększony timeout
        )
        
        if response.status_code != 200:
            return f"BŁĄD API {response.status_code}"
            
        return response.json()["choices"][0]["message"]["content"]
        
    except requests.exceptions.Timeout:
        return "TIMEOUT - Grok nie zdążył odpowiedzieć"
    except Exception as e:
        return f"BŁĄD GROK: {str(e)}"


def send_report(report_content):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = REPORT_TO
    msg['Subject'] = f"Raport EEN Matching - {datetime.now().strftime('%Y-%m-%d')}"

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
    emails = fetch_new_emails()
    print(f"Znaleziono {len(emails)} maili")

    full_report = f"Raport EEN Matching - Dolny Śląsk\nData: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"

    for e in emails:
        if any(k in e["subject"].lower() for k in ["profile", "query", "request", "offer", "business", "enterprise"]):
            print(f"Analizuję: {e['subject']}")
            analysis = analyze_with_grok(e["body"], e["subject"])
            full_report += analysis + "\n\n" + "="*90 + "\n\n"

    send_report(full_report)

if __name__ == "__main__":
    main()
