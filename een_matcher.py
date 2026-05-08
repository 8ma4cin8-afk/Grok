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
        email_ids = messages[0].split()[-10:]

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

            emails.append({"subject": subject, "body": body[:8000], "date": msg["Date"]})  # mocno skrócone
        mail.logout()
        return emails
    except Exception as e:
        print(f"BŁĄD: {e}")
        return []


def analyze_with_grok(profile_text, subject):
    prompt = f"""Profil EEN: {subject}

{profile_text[:7500]}

Przygotuj zwięzły, konkretny raport dla Dolnego Śląska w formacie:

**Profil:** {subject}
**Ocena:** X/10
**Polska w target?** Tak/Nie

**Top 5 firm z DS:**

| Priorytet | Firma | Lokalizacja | Dlaczego pasuje? | Kontakt |
|-----------|-------|-------------|------------------|---------|

**Gotowy mail do firmy:**

---
[Treść gotowego maila]
---

Bądź konkretny."""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}"},
            json={
                "model": "grok-4",        # można zmienić na "grok-3" jeśli dalej timeout
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1400
            },
            timeout=75
        )
        if response.status_code != 200:
            return f"BŁĄD API: {response.status_code}"
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"BŁĄD: {str(e)}"


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
    except Exception as e:
        print(f"Błąd wysyłki: {e}")


def main():
    emails = fetch_new_emails()
    report = f"🔍 RAPORT EEN MATCHING\nData: {datetime.now().strftime('%Y-%m-%d %H:%M')}\nLiczba profili: {len(emails)}\n\n"

    for e in emails:
        if any(k in e["subject"].lower() for k in ["profile", "query", "request", "offer", "business", "enterprise"]):
            analysis = analyze_with_grok(e["body"], e["subject"])
            report += analysis + "\n\n" + "="*80 + "\n\n"

    send_report(report)

if __name__ == "__main__":
    main()
