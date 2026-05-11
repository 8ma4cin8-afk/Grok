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
        email_ids = messages[0].split()[-15:]

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

            emails.append({"subject": subject, "body": body, "date": msg["Date"]})
        mail.logout()
        return emails
    except Exception as e:
        print(f"BŁĄD: {e}")
        return []


def analyze_with_grok(profile_text, subject):
    prompt = f"""To jest jeden profil EEN z paczki "Profiles query".

Temat: {subject}

Treść:
{profile_text[:11000]}

Zasady:
- Jeśli nadawca z Polski lub Polska nie jest targetem → pomiń
- Zrób analizę tylko jeśli to zagraniczny profil z Polską jako target

Zwróć JSON:
{{
  "profile_id": "...",
  "is_polish": false,
  "poland_target": "Tak",
  "score": 8,
  "short_description": "...",
  "companies": [5 firm z Dolnego Śląska],
  "email_template": "..."
}}"""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}"},
            json={
                "model": "grok-3",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1600
            },
            timeout=75
        )
        content = response.json()["choices"][0]["message"]["content"]
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"error": "no json"}
    except Exception as e:
        return {"error": str(e)}


# ... (pozostała część send_report i main bez zmian - możesz zostawić z poprzedniej wersji)

def main():
    emails = fetch_new_emails()
    print(f"Znaleziono {len(emails)} maili")

    reports = []
    for e in emails:
        if "Profiles query" in e["subject"] or "Only Requests" in e["subject"] or "Only Offers" in e["subject"]:
            print(f"Analizuję: {e['subject']}")
            analysis = analyze_with_grok(e["body"], e["subject"])
            reports.append(analysis)

    # Tymczasowo drukujemy w konsoli
    print(json.dumps(reports, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
