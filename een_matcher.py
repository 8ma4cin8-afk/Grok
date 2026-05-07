import imaplib
import email
import os
import json
from datetime import datetime
from email.header import decode_header
import requests

# ================== KONFIGURACJA ==================
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
GROK_API_KEY = os.getenv("GROK_API_KEY")

# Adres, na który wysyłamy raport
REPORT_EMAIL = "marcin.jablonski@pwr.edu.pl"

# =================================================

def fetch_new_emails():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
    mail.select("inbox")

    _, messages = mail.search(None, 'UNSEEN')
    email_ids = messages[0].split()

    emails = []
    for eid in email_ids[-10:]:  # ostatnie 10 nieprzeczytanych
        _, msg_data = mail.fetch(eid, "(RFC822)")
        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = decode_header(msg["Subject"])[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = msg.get_payload(decode=True).decode()

        emails.append({
            "subject": subject,
            "body": body,
            "date": msg["Date"]
        })

    mail.logout()
    return emails


def analyze_with_grok(profile_text):
    prompt = f"""Jesteś ekspertem EEN matchmaking. Przeanalizuj poniższy profil i przygotuj rozbudowany raport dla konsultanta z Dolnego Śląska i Opolszczyzny.

Typ profilu: {profile_text[:500]}

Szczegółowo:
1. Ocena potencjału (1-10)
2. Typ poszukiwanego partnera z regionu
3. Uzasadnienie
4. Kluczowe frazy do wyszukiwania firm
5. Gotowy fragment pierwszej wiadomości do firmy (po polsku)

Zwróć wynik w formacie JSON."""

    response = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROK_API_KEY}"},
        json={
            "model": "grok-4",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
    )
    
    try:
        return response.json()["choices"][0]["message"]["content"]
    except:
        return "Błąd analizy Grok"


def main():
    emails = fetch_new_emails()
    
    if not emails:
        print("Brak nowych maili")
        return

    report = f"Raport EEN Matching - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    
    for e in emails:
        if "Enterprise Europe Network" in e["subject"] or "EU-CORPORATE-NOTIFICATION-SYSTEM" in e["subject"]:
            analysis = analyze_with_grok(e["body"])
            report += f"---\n{analysis}\n\n"

    # Wysyłka raportu (można użyć smtplib)
    print(report)   # na razie drukujemy - później dodamy wysyłkę

if __name__ == "__main__":
    main()
