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

print("=== DEBUG SEKRETÓW ===")
print(f"GMAIL_EMAIL: {'✅ ISTNIEJE' if GMAIL_EMAIL else '❌ BRAK'}")
print(f"GMAIL_PASSWORD: {'✅ ISTNIEJE' if GMAIL_PASSWORD else '❌ BRAK'}")
print("======================")

# ====================== POBIERANIE MAILU ======================
def get_latest_een_email():
    if not GMAIL_EMAIL or not GMAIL_PASSWORD:
        print("❌ Brak sekretów Gmail")
        return None

    try:
        print("🔄 Łączenie z Gmail IMAP...")
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
        mail.select("inbox")

        # Szukanie maili EEN
        status, messages = mail.search(None, '(OR (FROM "Enterprise Europe Network") (FROM "EISMEA") (SUBJECT "Partnering Opportunities"))')
        email_ids = messages[0].split()[-8:]   # ostatnie 8 maili

        print(f"Znaleziono {len(email_ids)} potencjalnych maili od EEN")

        for num in reversed(email_ids):
            _, msg_data = mail.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])

            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()

            print(f"Sprawdzam: {subject[:80]}...")

            if any(keyword in subject for keyword in ["Partnering Opportunities", "BOCO", "TODE", "Business Offer"]):
                print(f"✅ ZNALEZIONO MAIL EEN: {subject}")

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
        print("⚠️ Nie znaleziono aktualnego maila EEN")
        return None

    except Exception as e:
        print(f"❌ Błąd połączenia z Gmail: {e}")
        return None

# ====================== RESZTA FUNKCJI ======================
def load_firms_db():
    try:
        with open("firms_db.json", "r", encoding="utf-8") as f:
            return json.load(f)["firms"]
    except:
        print("⚠️ Brak lub błąd firms_db.json")
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
        return "<p><em>Brak dopasowanych firm w bazie dla tej branży.</em></p>"
    
    data = []
    for i, firm in enumerate(matched_firms, 1):
        contact = f"{firm.get('phone','')}<br>{firm.get('email','')}".strip('<br>') or "Kontakt via strona"
        data.append([i, firm['name'], firm['location'], contact, firm.get('website',''), 
                    "Najlepsze dopasowanie" if i == 1 else "Dobre dopasowanie"])
    
    df = pd.DataFrame(data, columns=["Priorytet", "Firma", "Lokalizacja", "Kontakt", "Strona www", "Komentarz"])
    return df.to_html(index=False, escape=False)

# ====================== MAIN ======================
def main():
    print("=== START EEN MATCHER ===")
    
    email_body = get_latest_een_email()
    
    if not email_body:
        print("⚠️ Próbuję fallback na input_email.txt...")
        if os.path.exists("input_email.txt"):
            with open("input_email.txt", "r", encoding="utf-8") as f:
                email_body = f.read()
            print("✅ Użyto pliku input_email.txt")
        else:
            print("❌ Nie ma żadnego źródła maila")
            return

    print(f"Przetwarzam maila o długości {len(email_body)} znaków...")

    firms = load_firms_db()
    profiles = parse_profiles(email_body)
    print(f"Znaleziono {len(profiles)} profili EEN")

    # Ranking i generowanie raportu
    def ranking_key(p):
        text = p['full_text']
        if any(x in text for x in ["cosmetic", "private label"]): return 10
        if any(x in text for x in ["food", "snack", "granola", "chocolate"]): return 8
        if "automotive" in text: return 6
        return 2

    ranked = sorted(profiles, key=ranking_key, reverse=True)
    top_profiles = ranked[:10]

    # Generowanie HTML
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
    <p><strong>Data:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")} | Znaleziono {len(profiles)} profili</p>
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

    print(f"✅ Raport HTML wygenerowany pomyślnie ({len(top_profiles)} profili)")

if __name__ == "__main__":
    main()
