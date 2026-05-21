# een_matcher.py
import re
import json
import os
from datetime import datetime
import pandas as pd
import imaplib
import email
from email.header import decode_header

GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

def get_latest_een_email():
    print("🔍 Logowanie do Gmaila...")
    if not GMAIL_EMAIL or not GMAIL_PASSWORD:
        print("❌ Brak danych logowania (sekrety)")
        return None

    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        mail.select("inbox")

        # Szersze wyszukiwanie
        status, messages = mail.search(None, 'FROM "een" OR FROM "Enterprise" OR FROM "EISMEA"')
        email_ids = messages[0].split()[-10:]  # ostatnie 10 maili

        print(f"Znaleziono {len(email_ids)} potencjalnych maili")

        for num in reversed(email_ids):
            _, msg_data = mail.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])

            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()

            print(f"Sprawdzam mail: {subject}")

            if "Partnering Opportunities" in subject or "BOCO" in subject or "TODE" in subject or "Business Offer" in subject:
                print(f"✅ ZNALEZIONO MAIL EEN: {subject}")

                # Pobieranie treści
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
        print("⚠️ Nie znaleziono maila EEN w ostatnich wiadomościach")
        return None

    except Exception as e:
        print(f"❌ Błąd połączenia z Gmail: {e}")
        return None

# ====================== RESZTA KODU (bez zmian) ======================
def load_firms_db():
    try:
        with open("firms_db.json", "r", encoding="utf-8") as f:
            return json.load(f)["firms"]
    except:
        print("⚠️ Brak firms_db.json lub błąd odczytu")
        return []

def parse_profiles(text):
    # ... (pozostawiam bez zmian - ta sama funkcja co wcześniej)
    profiles = []
    pattern = r'(Business Offer|Business Request|Technology Offer|Research & Development Request)\s+(B[O|R|T]\w{2}\d{8,})\s*(.+?)(?=\n\s*(Business Offer|Business Request|Technology Offer|Research & Development Request)|$)'
    matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for m in matches:
        p_type = m.group(1).strip()
        ref = m.group(2).strip()
        content = m.group(3).strip()
        lines = content.split('\n')
        country = lines[0].strip() if lines else "Nieznany"
        title = lines[1].strip() if len(lines) > 1 else content[:180]
        
        profiles.append({
            'ref': ref,
            'type': p_type,
            'country': country,
            'title': title,
            'full_text': content.lower()
        })
    return profiles

# ... (match_companies, create_table_html, main - zostawiam jak w poprzedniej wersji)

def main():
    print("=== START EEN MATCHER ===")
    email_body = get_latest_een_email()
    
    if not email_body:
        print("⚠️ Nie udało się pobrać maila EEN")
        if os.path.exists("input_email.txt"):
            print("Używam pliku input_email.txt jako fallback")
            with open("input_email.txt", "r", encoding="utf-8") as f:
                email_body = f.read()
        else:
            print("❌ Brak jakiegokolwiek źródła maila")
            return

    print(f"Przetwarzam {len(email_body)} znaków tekstu...")

    firms = load_firms_db()
    profiles = parse_profiles(email_body)
    print(f"Znaleziono {len(profiles)} profili EEN")

    # reszta generowania raportu...
    # (tutaj wklej resztę z poprzedniej wersji - generowanie HTML)

    # Na razie zostawiam uproszczone zakończenie:
    print(f"✅ Przetworzono {len(profiles)} profili")
    with open("raport_een.html", "w", encoding="utf-8") as f:
        f.write(f"<h1>Raport wygenerowany {datetime.now()}</h1><p>Znaleziono {len(profiles)} profili</p>")
    print("Raport HTML zapisany")

if __name__ == "__main__":
    main()
