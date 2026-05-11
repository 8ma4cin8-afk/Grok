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
from jinja2 import Template
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
    prompt = f"""Analizuj JEDEN profil EEN i przygotuj raport w formacie JSON:

{{
  "profile_id": "{subject}",
  "score": 8,
  "poland_target": "Tak / Nie / All countries",
  "short_description": "...",
  "companies": [
    {{"name": "...", "location": "...", "why": "...", "contact": "...", "comment": "..."}},
    ...
  ],
  "email_template": "Pełny gotowy mail..."
}}

Profil:
Temat: {subject}
Treść: {profile_text[:12000]}
"""

    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROK_API_KEY}"},
            json={
                "model": "grok-4",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.25,
                "max_tokens": 2200
            },
            timeout=90
        )
        result = response.json()["choices"][0]["message"]["content"]
        # Wyciągnięcie JSON
        import re
        json_match = re.search(r'\{.*\}', result, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return {"error": "Nie udało się sparsować JSON"}
    except Exception as e:
        return {"error": str(e)}


def generate_pdf(reports):
    # Na razie prosty HTML → PDF (później ulepszymy)
    html = "<h1>Raport EEN Matching - Dolny Śląsk</h1>"
    html += f"<p>Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p><hr>"

    for r in reports:
        html += f"<h2>{r.get('profile_id', 'Profil')}</h2>"
        html += f"<p><strong>Ocena:</strong> {r.get('score', 'N/A')}/10 | <strong>Polska target:</strong> {r.get('poland_target', 'Nieznane')}</p>"
        html += f"<p><strong>Opis:</strong> {r.get('short_description', '')}</p>"
        
        html += "<table border='1' style='border-collapse: collapse; width:100%'>"
        html += "<tr><th>Priorytet</th><th>Firma</th><th>Lokalizacja</th><th>Dlaczego pasuje?</th><th>Kontakt</th><th>Komentarz</th></tr>"
        for company in r.get('companies', []):
            html += f"<tr><td>{company.get('name')}</td><td>{company.get('location')}</td><td>{company.get('why')}</td><td>{company.get('contact')}</td><td>{company.get('comment')}</td></tr>"
        html += "</table><br>"

        html += f"<h3>Gotowy mail:</h3><pre>{r.get('email_template', '')}</pre><hr>"

    # Zapisz do PDF (prosty sposób)
    with open("een_report.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    # Na razie zwracamy HTML, później dodamy prawdziwy PDF
    return "een_report.html"


def send_report(reports):
    msg = MIMEMultipart()
    msg['From'] = GMAIL_EMAIL
    msg['To'] = REPORT_TO
    msg['Subject'] = f"Raport EEN Matching - {datetime.now().strftime('%Y-%m-%d')}"

    # Tekstowy body
    body = "Raport EEN Matching w załączniku jako PDF.\n"
    msg.attach(MIMEText(body, 'plain'))

    # Załącznik (na razie HTML)
    with open("een_report.html", "rb") as f:
        attach = MIMEApplication(f.read(), _subtype="html")
        attach.add_header('Content-Disposition', 'attachment', filename="Raport_EEN_Matching.pdf")
        msg.attach(attach)

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(GMAIL_EMAIL, GMAIL_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Raport wysłany z załącznikiem")
    except Exception as e:
        print(f"Błąd wysyłki: {e}")


def main():
    emails = fetch_new_emails()
    print(f"Znaleziono {len(emails)} profili")

    reports = []
    for e in emails:
        if any(k in e["subject"].lower() for k in ["profile", "query", "request", "offer", "business", "enterprise"]):
            analysis = analyze_with_grok(e["body"], e["subject"])
            reports.append(analysis)

    if reports:
        generate_pdf(reports)
        send_report(reports)

if __name__ == "__main__":
    main()
