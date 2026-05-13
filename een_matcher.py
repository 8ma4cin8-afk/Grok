import imaplib
import email
import os
import re
import json
from datetime import datetime
from email.header import decode_header
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
        email_ids = messages[0].split()[-20:]  # ostatnie 20
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
        print(f"BŁĄD pobierania maili: {e}")
        return []

def analyze_profiles_with_grok(full_text):
    prompt = f"""Jesteś specjalistą od matchingu EEN dla Dolnego Śląska i Opolszczyzny.
Przetwórz poniższy mail z wieloma profilami i dla każdego zagranicznego profilu (gdzie Polska jest targetem) przygotuj blok w dokładnie tym formacie:

**REFERENCJA**
**Kraj**
**Typ oferty**
Krótki tytuł/opis
**Ocena potencjału:** Wysoki / Średni / Niski (X/10)
Krótki komentarz dlaczego.

**Zaktualizowana tabela z kontaktami dla profilu REFERENCJA**
| Priorytet | Firma | Lokalizacja | Kontakt (telefon + email) | Strona www | Komentarz |
|-----------|-------|-------------|---------------------------|------------|-----------|
| 1 | ... | ... | ... | ... | ... |

Zasady:
- Pomijaj całkowicie profile polskie
- Zawsze dokładnie 5 firm z Dolnego Śląska / Opolszczyzny
- Priorytet od najlepszego dopasowania
- Kontakt jak najbardziej konkretny

Mail do analizy:
{full_text[:28000]}"""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}"},
            json={
                "model": "grok-3",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4000
            },
            timeout=180
        )
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"BŁĄD GROK: {str(e)}"

def send_report(report_content):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = REPORT_TO
    msg['Subject'] = f"Raport EEN Matching - Dolny Śląsk - {datetime.now().strftime('%Y-%m-%d')}"
    msg.attach(MIMEText(report_content, 'plain', 'utf-8'))
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Raport wysłany pomyślnie")
    except Exception as e:
        print(f"Błąd wysyłki: {e}")

def main():
    print(f"[{datetime.now()}] Start EEN Matcher")
    emails = fetch_new_emails()
   
    if not emails:
        print("Brak nowych maili")
        return
   
    full_text = "\n\n".join([e["body"] for e in emails])
    print(f"Przetwarzam {len(emails)} maili...")
    report = analyze_profiles_with_grok(full_text)
   
    final_report = f"Raport EEN Matching - Dolny Śląsk\nData: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{report}"
   
    send_report(final_report)

if __name__ == "__main__":
    main()
