import urllib.request, json, base64, os, urllib.parse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

# CONFIG ZENDESK
url = os.environ.get('ZENDESK_URL')
email = os.environ.get('ZENDESK_EMAIL')
token = os.environ.get('ZENDESK_TOKEN')
auth = base64.b64encode(f"{email}:{token}".encode()).decode()
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

# CONFIG GOOGLE
service_account_info = json.loads(os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON'))
spreadsheet_id = os.environ.get('SPREADSHEET_ID')
creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
service = build('sheets', 'v4', credentials=creds)

PROPERTIES = {
    "BB": "Bastide des Barattes", "CT": "Clos du Tuilier", 
    "MF": "Mas de Florette", "CM": "Collines de Manon", "HE": "Hameau de l’Esperelle"
}

def get_availabilities(prop_code):
    try:
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        sheet_name = next((s['properties']['title'] for s in sheets if s['properties']['title'].startswith(prop_code)), None)
        
        if not sheet_name: return f"Calendrier pour {prop_code} non trouvé."

        result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:M32").execute()
        rows = result.get('values', [])
        
        availables = []
        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        
        for m_idx, month_name in enumerate(months, start=1):
            for row in rows[2:]:
                if len(row) <= m_idx or not row[0]: continue
                day_num = row[0].strip()
                cell_content = row[m_idx].strip()
                
                # Disponible si pas de "X & Y"
                if day_num.isdigit() and "&" not in cell_content:
                    try:
                        dt = datetime(2026, m_idx, int(day_num))
                        # Mercredis ignorés pour BB, MF, HE
                        if prop_code in ["BB", "MF", "HE"] and dt.weekday() == 2: continue
                        availables.append(f"- {day_num} {month_name} 2026")
                    except: continue

        return f"{PROPERTIES[prop_code]} ({prop_code})\n" + "\n".join(availables[:15])
    except Exception as e:
        return f"Erreur Google Sheets: {e}"

try:
    me_req = urllib.request.Request(f"{url}/api/v2/users/me.json", headers=headers)
    with urllib.request.urlopen(me_req) as resp:
        my_id = json.loads(resp.read().decode())['user']['id']

    req = urllib.request.Request(f"{url}/api/v2/tickets.json?sort_by=created_at&sort_order=desc", headers=headers)
    with urllib.request.urlopen(req) as resp:
        tickets = json.loads(resp.read().decode()).get('tickets', [])

    for t in tickets:
        if t.get('assignee_id') is not None or 'ia_fait' in t.get('tags', []): continue
        
        subject = (t.get('subject') or "").upper()
        found_prop = next((c for c in PROPERTIES if c in subject), None)

        if "DISPO" in subject and found_prop:
            dispos = get_availabilities(found_prop)
            payload = {"ticket": {"status": "open", "assignee_id": my_id, "comment": {"body": f"[IA] Voici les dates libres :\n\n{dispos}", "public": False}, "additional_tags": ["ia_fait"]}}
            u_req = urllib.request.Request(f"{url}/api/v2/tickets/{t['id']}.json", data=json.dumps(payload).encode(), headers=headers, method='PUT')
            urllib.request.urlopen(u_req)
            print(f"Ticket {t['id']} traité.")

except Exception as e:
    print(f"Erreur : {e}")
