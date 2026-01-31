import urllib.request, json, base64, os, urllib.parse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

# --- CONFIGURATION ---
# Zendesk
url = os.environ.get('ZENDESK_URL')
email = os.environ.get('ZENDESK_EMAIL')
token = os.environ.get('ZENDESK_TOKEN')
auth = base64.b64encode(f"{email}:{token}".encode()).decode()
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

# Google Sheets
js_env = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
spreadsheet_id = os.environ.get('SPREADSHEET_ID')

# Brouillon Bridebook
brouillon_bridebook = """Bonjour,
Pour recevoir la documentation complète et les tarifs du Mas de Florette, je vous invite à vous rendre sur le site www.homesweetevent.com et sélectionner le Mas de Florette. Vous recevrez les éléments par mail en quelques minutes.
Et pour découvrir notre actualité, suivez-nous sur Instagram : @masdeflorette.
Bien cordialement, Valérie"""

PROPERTIES = {
    "BB": "Bastide des Barattes", "CT": "Clos du Tuilier", 
    "MF": "Mas de Florette", "CM": "Collines de Manon", "HE": "Hameau de l’Esperelle"
}

# --- FONCTION DISPONIBILITÉS ---
def get_availabilities(prop_code):
    try:
        service_account_info = json.loads(js_env)
        creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        service = build('sheets', 'v4', credentials=creds)
        
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
                if day_num.isdigit() and "&" not in cell_content:
                    try:
                        dt = datetime(2026, m_idx, int(day_num))
                        if prop_code in ["BB", "MF", "HE"] and dt.weekday() == 2: continue
                        availables.append(f"- {day_num} {month_name} 2026")
                    except: continue
        return f"Voici les prochaines dates libres pour {PROPERTIES[prop_code]} :\n\n" + "\n".join(availables[:15])
    except Exception as e:
        return f"Erreur lors de la lecture du calendrier : {e}"

# --- EXECUTION PRINCIPALE ---
try:
    # 1. Récupérer ID Valérie
    me_req = urllib.request.Request(f"{url}/api/v2/users/me.json", headers=headers)
    with urllib.request.urlopen(me_req) as resp:
        my_id = json.loads(resp.read().decode())['user']['id']

    # 2. Chercher tickets non affectés
    query = 'type:ticket assignee:none status<solved'
    search_url = f"{url}/api/v2/search.json?query={urllib.parse.quote(query)}"
    
    with urllib.request.urlopen(urllib.request.Request(search_url, headers=headers)) as resp:
        tickets = json.loads(resp.read().decode()).get('results', [])
        count = 0
        
        for t in tickets:
            if 'ia_fait' in t.get('tags', []): continue
            
            t_id = t['id']
            subject = (t.get('subject') or "").upper()
            payload = None

            # RÈGLE 1 : Alertes internes
            alert_matches = ["INTERNE : VISITE", "STATUT DE LA PISTE NON CHANGÉ", "INTERNE : CALL"]
            if any(m in subject for m in alert_matches):
                payload = {"status": "open", "assignee_id": my_id, "additional_tags": ["ia_fait"]}

            # RÈGLE 2 : Bridebook
            elif "BRIDEBOOK" in subject:
                payload = {"status": "open", "assignee_id": my_id, "comment": {"body": brouillon_bridebook, "public": False}, "additional_tags": ["ia_fait"]}

            # RÈGLE 3 : Disponibilités (Nouveau !)
            else:
                found_prop = next((c for c in PROPERTIES if c in subject), None)
                if "DISPO" in subject and found_prop:
                    message_dispo = get_availabilities(found_prop)
                    payload = {"status": "open", "assignee_id": my_id, "comment": {"body": f"[IA] {message_dispo}", "public": False}, "additional_tags": ["ia_fait"]}

            # ENVOI SUR ZENDESK
            if payload:
                u_req = urllib.request.Request(f"{url}/api/v2/tickets/{t_id}.json", data=json.dumps({"ticket": payload}).encode(), headers=headers, method='PUT')
                urllib.request.urlopen(u_req)
                count += 1

    print(f"TERMINÉ : {count} tickets traités.")

except Exception as e:
    print(f"Erreur globale : {e}")
