import imaplib
import email
import os
import json
import re
from datetime import datetime
from email.header import decode_header
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

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

            emails.append({"subject": subject, "body": body[:14000], "date": msg["Date"]})
        mail.logout()
        return emails
    except Exception as e:
        print(f"BŁĄD pobierania: {e}")
        return []


def analyze_with_grok(profile_text, subject):
    prompt = f"""Jesteś ekspertem EEN dla Dolnego Śląska.

Analizuj TEN JEDEN profil:

Temat: {subject}

Treść:
{profile_text[:13000]}

Zwróć wynik jako czysty JSON."""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}"},
            json={
                "model": "grok-3",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 2000
            },
            timeout=90
        )
        content = response.json()["choices"][0]["message"]["content"]
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"error": "no json"}
    except Exception as e:
        return {"error": str(e)}


def generate_html(reports):
    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Raport EEN Matching</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #1a3c6e; }}
        h2 {{ color: #2c5aa0; border-bottom: 2px solid #ddd; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #999; padding: 8px; text-align: left; }}
        th {{ background-color: #f0f0f0; }}
    </style>
    </head>
    <body>
    <h1>Raport EEN Matching - Dolny Śląsk</h1>
    <p><strong>Data:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    <hr>
    """

    for r in reports:
        if r.get("is_polish") or "polish" in str(r).lower():
            html += f"<h2>❌ {r.get('profile_id', 'Profil')} — Profil polski (pominięty)</h2><hr>"
            continue

        html += f"<h2>✅ {r.get('profile_id', 'Profil')}</h2>"
        html += f"<p><strong>Ocena:</strong> {r.get('score', 'N/A')}/10</p>"
        html += f"<p>{r.get('short_description', '')}</p>"

        html += "<table><tr><th>Priorytet</th><th>Firma</th><th>Lokalizacja</th><th>Dlaczego pasuje?</th><th>Kontakt</th><th>Komentarz</th></tr>"
        for idx, c in enumerate(r.get('companies', []), 1):
            html += f"<tr><td>{idx}</td><td>{c.get('name','')}</td><td>{c.get('location','')}</td><td>{c.get('why','')}</td><td>{c.get('contact','')}</td><td>{c.get('comment','')}</td></tr>"
        html += "</table><hr>"

    html += "</body></html>"
    with open("een_report.html", "w", encoding="utf-8") as f:
        f.write(html)
    return "een_report.html"


def send_report(reports):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = REPORT_TO
    msg['Subject'] = f"Raport EEN Matching - {datetime.now().strftime('%Y-%m-%d')}"

    body = "Raport w załączniku (HTML)"
    msg.attach(MIMEText(body, 'plain'))

    generate_html(reports)

    with open("een_report.html", "rb") as f:
        attach = MIMEApplication(f.read(), _subtype="html")
        attach.add_header('Content-Disposition', 'attachment', filename="Raport_EEN_Matching.html")
        msg.attach(attach)

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

    reports = []
    for e in emails:
        if any(k in e["subject"].lower() for k in ["profile", "query", "request", "offer", "business", "enterprise"]):
            analysis = analyze_with_grok(e["body"], e["subject"])
            if isinstance(analysis, dict):
                reports.append(analysis)

    if reports:
        send_report(reports)
    else:
        print("Nie znaleziono profili")

if __name__ == "__main__":
    main()
