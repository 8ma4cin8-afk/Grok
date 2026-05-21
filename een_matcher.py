# een_matcher.py
import re
import os
from datetime import datetime
import imaplib
import email
from email.header import decode_header

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

print("=== EEN MATCHER - Wersja czysta ===")
print(f"GMAIL_EMAIL: {'✅' if GMAIL_EMAIL else '❌'}")
print(f"GMAIL_PASSWORD: {'✅' if GMAIL_PASSWORD else '❌'}")

def get_latest_een_email():
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        mail.select("inbox")

        # Szukanie maili EEN
        status, messages = mail.search(None, '(OR (FROM "Enterprise") (FROM "EISMEA") (SUBJECT "Partnering Opportunities"))')
        email_ids = messages[0].split()[-5:]  # ostatnie 5 maili

        for num in reversed(email_ids):
            _, msg_data = mail.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])

            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()

            print(f"Sprawdzam: {subject}")

            if "Partnering Opportunities" in subject:
                print(f"✅ Znaleziono mail EEN: {subject}")
                
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors='ignore')
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors='ignore')
                
                mail.logout()
                return body

        mail.logout()
        print("Nie znaleziono nowego maila EEN")
        return None

    except Exception as e:
        print(f"Błąd: {e}")
        return None


def parse_profiles(text):
    profiles = []
    pattern = r'(Business Offer|Business Request|Technology Offer)\s+(B[O|R|T]\w{2}\d{8,})\s*(.+?)(?=\n\s*(Business Offer|Business Request|Technology Offer)|$)'
    matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for m in matches:
        p_type = m.group(1).strip()
        ref = m.group(2).strip()
        content = m.group(3).strip()
        lines = content.split('\n')
        country = lines[0].strip() if lines else ""
        title = lines[1].strip() if len(lines) > 1 else content[:150]
        
        profiles.append({
            'ref': ref,
            'type': p_type,
            'country': country,
            'title': title
        })
    return profiles


def main():
    email_body = get_latest_een_email()
    
    if not email_body:
        print("Nie udało się pobrać maila.")
        return

    profiles = parse_profiles(email_body)
    print(f"Znaleziono {len(profiles)} profili")

    html_content = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <title>Raport EEN Matching</title>
    <style>body {{font-family: Arial; margin: 40px;}} h1 {{color: navy;}}</style>
</head>
<body>
    <h1>Raport EEN Matching — Dolny Śląsk + Opolszczyzna</h1>
    <p>Data: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    <p>Przetworzono {len(profiles)} profili</p>
    <p>Wersja czysta - wróciliśmy do działającego stanu.</p>
</body>
</html>"""

    with open("raport_een.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print("✅ raport_een.html wygenerowany")

if __name__ == "__main__":
    main()
