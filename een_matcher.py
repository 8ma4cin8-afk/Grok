# een_matcher.py
import re
import json
from datetime import datetime
from jinja2 import Template
import pandas as pd

# ====================== KONFIGURACJA ======================
try:
    from weasyprint import HTML
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("⚠️  weasyprint nie jest zainstalowany. PDF nie będzie generowany.")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="utf-8">
    <title>Raport EEN Matching - Dolny Śląsk + Opolszczyzna {{ date }}</title>
    <style>
        body { font-family: Arial, Helvetica, sans-serif; margin: 40px; background: #f4f6f9; color: #333; }
        h1 { color: #1e3a8a; }
        .profile { background: white; padding: 25px; margin-bottom: 35px; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; margin: 18px 0; }
        th { background: #1e3a8a; color: white; padding: 12px; text-align: left; }
        td { padding: 12px; border-bottom: 1px solid #ddd; }
        tr:nth-child(even) { background: #f8fafc; }
        .high { color: #166534; font-weight: bold; }
        .medium { color: #854d0e; font-weight: bold; }
        .low { color: #991b1b; }
    </style>
</head>
<body>
    <h1>Raport EEN Matching — Dolny Śląsk + Opolszczyzna</h1>
    <p><strong>Data:</strong> {{ date }} | Przeanalizowano: {{ total }} profili | Pokazano Top {{ shown }}</p>
    
    {% for p in profiles %}
    <div class="profile">
        <h2>{{ p.ref }} — {{ p.country }}</h2>
        <p><strong>{{ p.type }}</strong><br>{{ p.title }}</p>
        <p><strong>Ocena potencjału: <span class="{{ p.potential.lower() }}">{{ p.potential }}</span></strong></p>
        <p>{{ p.justification }}</p>
        
        <h3>5 najlepszych potencjalnych partnerów z regionu</h3>
        {{ p.table_html | safe }}
    </div>
    {% endfor %}
</body>
</html>
"""

def load_firms_db():
    with open("firms_db.json", "r", encoding="utf-8") as f:
        return json.load(f)["firms"]

def parse_profiles(text):
    profiles = []
    # Lepszy parser dla maili EEN
    pattern = r'(Business Offer|Business Request|Technology Offer|Research & Development Request)\s+(B[O|R|T]\w{2}\d{8,})\s*(.+?)(?=\n\s*(Business Offer|Business Request|Technology Offer|Research & Development Request)|$)' 
    matches = re.finditer(pattern, text, re.DOTALL | re.IGNORECASE)
    
    for m in matches:
        p_type = m.group(1).strip()
        ref = m.group(2).strip()
        content = m.group(3).strip()
        
        country = content.split('\n')[0].strip()
        title = content.split('\n')[1].strip() if '\n' in content else content[:180]
        
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
        score = sum(3 for sector in firm["sectors"] if sector in profile_lower)
        if score > 0:
            scored.append((score, firm))
    
    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:top_n]]

def create_table_html(matched_firms):
    if not matched_firms:
        return "<p><em>Brak dopasowanych firm w bazie dla tej branży.</em></p>"
    
    data = []
    for i, firm in enumerate(matched_firms, 1):
        contact = f"{firm['phone']}<br>{firm['email']}" if firm['phone'] or firm['email'] else "Kontakt via strona"
        data.append([
            i,
            firm['name'],
            firm['location'],
            contact,
            firm['website'],
            "Bardzo dobre dopasowanie branżowe" if i == 1 else "Dobre dopasowanie"
        ])
    
    df = pd.DataFrame(data, columns=["Priorytet", "Firma", "Lokalizacja", "Kontakt", "Strona www", "Komentarz"])
    return df.to_html(index=False, escape=False, classes="table")

def main():
    with open("input_email.txt", "r", encoding="utf-8") as f:
        email_text = f.read()

    firms = load_firms_db()
    profiles = parse_profiles(email_text)
    
    ranked_profiles = sorted(profiles, key=lambda p: sum(1 for kw in ["cosmetic","private label","food","snack","automotive"] if kw in p['full_text'].lower()), reverse=True)
    top_profiles = ranked_profiles[:10]

    html_profiles = []
    for p in top_profiles:
        matched = match_companies(p['full_text'], firms)
        table_html = create_table_html(matched)
        
        potential = "Wysoki" if any(kw in p['full_text'] for kw in ["cosmetic","private label","food"]) else "Średni"
        
        html_profiles.append({
            'ref': p['ref'],
            'country': p['country'],
            'type': p['type'],
            'title': p['title'],
            'potential': potential,
            'justification': "Bardzo silne dopasowanie do kluczowych sektorów regionu." if potential == "Wysoki" else "Umiarkowane dopasowanie – warto zweryfikować.",
            'table_html': table_html
        })

    # Generowanie HTML
    template = Template(HTML_TEMPLATE)
    html_content = template.render(
        date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        total=len(profiles),
        shown=len(top_profiles),
        profiles=html_profiles
    )

    with open("raport_een.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Wygenerowano raport HTML ({len(top_profiles)} profili)")

    # Generowanie PDF
    if PDF_AVAILABLE:
        HTML(string=html_content).write_pdf("raport_een.pdf")
        print("✅ Wygenerowano raport PDF: raport_een.pdf")
    else:
        print("⚠️  Zainstaluj weasyprint aby generować PDF: pip install weasyprint")

if __name__ == "__main__":
    main()
