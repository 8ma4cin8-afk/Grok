# een_matcher.py
import re
import json
import os
from datetime import datetime
import pandas as pd
import imaplib
import email
from email.header import decode_header

# ====================== KONFIGURACJA ======================
GMAIL_EMAIL = os.getenv("GMAIL_EMAIL")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

try:
    from weasyprint import HTML
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

# ====================== POBIERANIE NAJNOWSZEGO MAILU EEN ======================
def get_latest_een_email():
    if not GMAIL_EMAIL or not GMAIL_PASSWORD:
        print("❌ Brak sekretów Gmail w GitHub Secrets")
        return None

    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        mail.select("inbox")

        # Szukamy maili od Enterprise Europe Network
        status, messages = mail.search(None, 'FROM "Enterprise Europe Network"')
        email_ids = messages[0].split()[-5:]  # ostatnie 5 maili

        latest_email = None
        latest_date = None

        for num in reversed(email_ids):
            _, msg_data = mail.fetch(num, '(RFC822)')
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()

            date = msg["Date"]

            # Pobieramy treść
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()

            if "Partnering Opportunities" in subject or "BOCO" in body or "TODE" in body:
                print(f"✅ Znaleziono mail EEN: {subject}")
                return body

        mail.logout()
        return None

    except Exception as e:
        print(f"❌ Błąd pobierania maila: {e}")
        return None

# ====================== RESZTA KODU (jak wcześniej) ======================
def load_firms_db():
    try:
        with open("firms_db.json", "r", encoding="utf-8") as f:
            return json.load(f)["firms"]
    except:
        return []

def parse_profiles(text):
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

def match_companies(profile_text, firms, top_n=5):
    profile_lower = profile_text.lower()
    scored = []
    for firm in firms:
        score = sum(3 for sector in firm.get("sectors", []) if sector in profile_lower)
        if score > 0:
            scored.append((score, firm))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:top_n]]

def create_table_html(matched_firms):
    if not matched_firms:
        return "<p><em>Brak dopasowanych firm w bazie.</em></p>"
    
    data = []
    for i, firm in enumerate(matched_firms, 1):
        contact = f"{firm.get('phone','')}<br>{firm.get('email','')}".strip('<br>') or "Kontakt via strona"
        data.append([i, firm['name'], firm['location'], contact, firm.get('website',''), 
                    "Najlepsze dopasowanie" if i == 1 else "Dobre dopasowanie"])
    
    df = pd.DataFrame(data, columns=["Priorytet", "Firma", "Lokalizacja", "Kontakt", "Strona www", "Komentarz"])
    return df.to_html(index=False, escape=False)

# ====================== MAIN ======================
def main():
    print("🔍 Pobieranie najnowszego maila EEN...")
    email_body = get_latest_een_email()
    
    if not email_body:
        print("⚠️ Nie znaleziono maila EEN - sprawdzam czy istnieje input_email.txt")
        if os.path.exists("input_email.txt"):
            with open("input_email.txt", "r", encoding="utf-8") as f:
                email_body = f.read()
        else:
            print("❌ Brak maila do przetworzenia")
            return

    firms = load_firms_db()
    profiles = parse_profiles(email_body)

    def ranking_key(p):
        text = p['full_text']
        if any(x in text for x in ["cosmetic", "private label"]): return 10
        if any(x in text for x in ["food", "snack", "granola", "chocolate"]): return 8
        if "automotive" in text: return 6
        if "apparel" in text: return 4
        return 1

    ranked = sorted(profiles, key=ranking_key, reverse=True)
    top_profiles = ranked[:10]

    # Generowanie HTML (jak poprzednio)
    html_content = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <title>Raport EEN Matching - Dolny Śląsk + Opolszczyzna</title>
    <style>
        body {{font-family:Arial,sans-serif;margin:40px;background:#f4f6f9;}}
        h1 {{color:#1e3a8a;}}
        .profile {{background:white;padding:25px;margin-bottom:35px;border-radius:10px;box-shadow:0 4px 12px rgba(0,0,0,0.1);}}
        table {{width:100%;border-collapse:collapse;}}
        th {{background:#1e3a8a;color:white;padding:12px;}}
        td {{padding:12px;border-bottom:1px solid #ddd;}}
        tr:nth-child(even) {{background:#f8fafc;}}
    </style>
</head>
<body>
    <h1>Raport EEN Matching — Dolny Śląsk + Opolszczyzna</h1>
    <p><strong>Data:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")} | Przeanalizowano: {len(profiles)} profili</p>
"""

    for p in top_profiles:
        matched = match_companies(p['full_text'], firms)
        table = create_table_html(matched)
        potential = "Wysoki" if ranking_key(p) >= 6 else "Średni"
        
        html_content += f"""
    <div class="profile">
        <h2>{p['ref']} — {p['country']}</h2>
        <p><strong>{p['type']}</strong><br>{p['title']}</p>
        <p><strong>Ocena potencjału:</strong> <span style="color:#166534;font-weight:bold;">{potential}</span></p>
        <h3>5 najlepszych partnerów z regionu</h3>
        {table}
    </div>
"""
    html_content += "</body></html>"

    with open("raport_een.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Raport wygenerowany ({len(top_profiles)} profili)")

if __name__ == "__main__":
    main()
