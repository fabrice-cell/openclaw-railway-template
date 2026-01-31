import json, os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

# CONFIGURATION GOOGLE
js_env = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
spreadsheet_id = os.environ.get('SPREADSHEET_ID')

PROPERTIES = {
    "BB": "Bastide des Barattes", "CT": "Clos du Tuilier", 
    "MF": "Mas de Florette", "CM": "Collines de Manon", "HE": "Hameau de l’Esperelle"
}

def get_availabilities(prop_code):
    try:
        service_account_info = json.loads(js_env)
        creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
        service = build('sheets', 'v4', credentials=creds)
        
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        sheet_name = next((s['properties']['title'] for s in sheets if s['properties']['title'].startswith(prop_code)), None)
        
        if not sheet_name: return f"Erreur : Code '{prop_code}' non trouvé dans les onglets."

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
        
        res = f"--- DISPOS 2026 : {PROPERTIES[prop_code]} ---\n"
        return res + "\n".join(availables[:15])
    except Exception as e:
        return f"Erreur technique : {e}"

# Test direct si on lance le fichier
if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "CT"
    print(get_availabilities(code.upper()))
