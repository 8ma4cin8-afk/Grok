# een_matcher.py
import re
import json
from datetime import datetime
import pandas as pd

# ====================== KONFIGURACJA ======================
try:
    from weasyprint import HTML
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("⚠️ weasyprint nie jest zainstalowany - PDF nie będzie generowany.")

# ====================== ŁADOWANIE BAZY FIRM ======================
def load_firms_db():
    try:
        with open("firms_db.json", "r", encoding="utf-8") as f:
            return json.load(f)["firms"]
    except Exception as e:
        print(f"❌ Błąd ładowania firms_db.json: {e}")
        return []

# ====================== PARSER MAIL EEN ======================
def parse_profiles(text):
    profiles = []
    # Rozdzielanie profili
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

# ====================== MATCHING FIRM ======================
def match_companies(profile_text, firms, top_n=5):
    profile_lower = profile_text.lower()
    scored = []
    
    for firm in firms:
        score = sum(3 for sector in firm.get("sectors", []) if sector in profile_lower)
        if score > 0 or any(word in profile_lower for word in ["cosmetic", "food", "automotive", "textile", "apparel"]):
            scored.append((score + 1, firm))  # +1 żeby nie było zer
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:top_n]]

# ====================== TWORZENIE TABELI HTML ======================
def create_table_html(matched_firms):
    if not matched_firms:
        return "<p><em>Brak dopasowanych firm w bazie dla tej branży.</em></p>"
    
    data = []
    for i, firm in enumerate(matched_firms, 1):
        contact = ""
        if firm.get('phone'):
            contact += f"{firm['phone']}<br>"
        if firm.get('email'):
            contact += firm['email']
        if not contact:
            contact = "Kontakt via strona www"
        
        data.append([
            i,
            firm['name'],
            firm['location'],
            contact,
            firm.get('website', ''),
            "Najlepsze dopasowanie" if i == 1 else "Dobre dopasowanie branżowe"
        ])
    
    df = pd.DataFrame(data, columns=["Priorytet", "Firma", "Lokalizacja", "Kontakt (telefon + email)", "Strona www", "Komentarz"])
    return df.to_html(index=False, escape=False, classes="table")

# ====================== GŁÓWNA FUNKCJA ======================
def main():
    # Wczytanie maila
    with open("input_email.txt", "r", encoding="utf-8") as f:
        email_text = f.read()

    firms = load_firms_db()
    profiles = parse_profiles(email_text)
    
    # Ranking (prosty, ale skuteczny)
    def ranking_key(p):
        text = p['full_text']
        score = 0
        if any(x in text for x in ["cosmetic", "private label", "skincare"]):
            score += 5
        if any(x in text for x in ["food", "snack", "granola", "chocolate", "cacao"]):
            score += 4
        if "automotive" in text or "plastic injection" in text:
            score += 3
        if "apparel" in text or "uniform" in text:
            score += 2
        return score
    
    ranked_profiles = sorted(profiles, key=ranking_key, reverse=True)
    top_profiles = ranked_profiles[:10]

    # Generowanie HTML
    html_content = f"""<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <title>Raport EEN Matching - Dolny Śląsk + Opolszczyzna</title>
    <style>
        body {{ font-family: Arial, Helvetica, sans-serif; margin: 40px; background: #f4f6f9; color: #333; line-height: 1.5; }}
        h1 {{ color: #1e3a8a; }}
        .profile {{ background: white; padding: 25px; margin-bottom: 35px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; margin: 18px 0; }}
        th {{ background: #1e3a8a; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 12px; border-bottom: 1px solid #ddd; vertical-align: top; }}
        tr:nth-child(even) {{ background: #f8fafc; }}
        .high {{ color: #166534; font-weight: bold; }}
        .medium {{ color: #854d0e; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>Raport EEN Matching — Dolny Śląsk + Opolszczyzna</h1>
    <p><strong>Data:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M")} | Przeanalizowano: {len(profiles)} profili | Pokazano Top {len(top_profiles)}</p>
"""

    for p in top_profiles:
        matched = match_companies(p['full_text'], firms)
        table_html = create_table_html(matched)
        potential = "Wysoki" if ranking_key(p) >= 4 else "Średni"
        
        html_content += f"""
    <div class="profile">
        <h2>{p['ref']} — {p['country']}</h2>
        <p><strong>{p['type']}</strong><br>{p['title']}</p>
        <p><strong>Ocena potencjału: <span class="{potential.lower()}">{potential}</span></strong></p>
        <p>Bardzo dobre dopasowanie do kluczowych sektorów Dolnego Śląska i Opolszczyzny.</p>
        <h3>5 najlepszych potencjalnych partnerów z regionu</h3>
        {table_html}
    </div>
"""

    html_content += "</body></html>"

    # Zapis HTML
    with open("raport_een.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Wygenerowano raport HTML ({len(top_profiles)} profili)")

    # Generowanie PDF
    if PDF_AVAILABLE:
        try:
            HTML(string=html_content).write_pdf("raport_een.pdf")
            print("✅ Wygenerowano raport PDF: raport_een.pdf")
        except Exception as e:
            print(f"❌ Błąd generowania PDF: {e}")
    else:
        print("⚠️ PDF pominięty (zainstaluj weasyprint: pip install weasyprint)")

if __name__ == "__main__":
    main()
