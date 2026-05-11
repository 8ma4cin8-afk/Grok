import imaplib
import email
import os
from datetime import datetime
from email.header import decode_header
import requests
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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

            emails.append({"subject": subject, "body": body[:13000], "date": msg["Date"]})
        mail.logout()
        return emails
    except Exception as e:
        print(f"BŁĄD: {e}")
        return []


def analyze_with_grok(profile_text, subject):
    prompt = f"""Jesteś ekspertem EEN. Analizujesz TYLKO JEDEN profil.

Zasady:
- Jeśli nadawca jest z Polski → napisz "Profil polski - pomijamy"
- Jeśli Polska nie jest w target countries → napisz "Polska nie jest targetem"
- Tylko zagraniczne profile gdzie Polska jest targetem → zrób pełną analizę

Profil:
Temat: {subject}

Treść:
{profile_text}

Zwróć wynik w formacie JSON:
{{
  "profile_id": "{subject}",
  "is_polish": true/false,
  "poland_target": "Tak/Nie",
  "score": 8,
  "short_description": "...",
  "companies": [
    {{"name": "...", "location": "...", "why": "...", "contact": "...", "comment": "..."}},
    ...
  ],
  "email_template": "Pełny gotowy mail..."
}}"""

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
            timeout=80
        )
        
        content = response.json()["choices"][0]["message"]["content"]
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"error": "Brak JSON"}
    except Exception as e:
        return {"error": str(e)}


def send_report(reports):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = REPORT_TO
    msg['Subject'] = f"Raport EEN Matching - {datetime.now().strftime('%Y-%m-%d')}"

    body = f"Raport EEN Matching - {datetime.now().strftime('%Y-%m-%d %H:%M')}\nLiczba przeanalizowanych profili: {len(reports)}\n\n"
    msg.attach(MIMEText(body, 'plain'))

    # Tymczasowo HTML
    html = "<h1>Raport EEN Matching - Dolny Śląsk</h1><p>" + datetime.now().strftime('%Y-%m-%d %H:%M') + "</p><hr>"
    for r in reports:
        if r.get("is_polish"):
            html += f"<h2>{r.get('profile_id')} → Profil polski - pominięty</h2><hr>"
            continue
        if r.get("poland_target") == "Nie":
            html += f"<h2>{r.get('profile_id')} → Polska nie jest targetem</h2><hr>"
            continue

        html += f"<h2>{r.get('profile_id')}</h2>"
        html += f"<p><strong>Ocena:</strong> {r.get('score')}/10</p>"
        html += f"<p>{r.get('short_description')}</p>"

        html += "<table border='1'><tr><th>Firma</th><th>Lokalizacja</th><th>Dlaczego pasuje?</th><th>Kontakt</th><th>Komentarz</th></tr>"
        for c in r.get('companies', []):
            html += f"<tr><td>{c.get('name')}</td><td>{c.get('location')}</td><td>{c.get('why')}</td><td>{c.get('contact')}</td><td>{c.get('comment')}</td></tr>"
        html += "</table><hr>"

    with open("report.html", "w", encoding="utf-8") as f:
        f.write(html)

    with open("report.html", "rb") as f:
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
    reports = []
    for e in emails:
        if any(k in e["subject"].lower() for k in ["profile", "query", "request", "offer", "business", "enterprise"]):
            analysis = analyze_with_grok(e["body"], e["subject"])
            reports.append(analysis)

    send_report(reports)

if __name__ == "__main__":
    main()
