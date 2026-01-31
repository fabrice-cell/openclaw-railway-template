import json, os, sys
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime

# CONFIGURATION
js_env = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
spreadsheet_id = os.environ.get('SPREADSHEET_ID')

PROPERTIES = {
    "BB": "Bastide des Barattes", "CT": "Clos du Tuilier", 
    "MF": "Mas de Florette", "CM": "Collines de Manon", "HE": "Hameau de l’Esperelle"
}

def get_availabilities(prop_code, year):
    try:
        if not js_env or not spreadsheet_id:
            return "Erreur : Variables d'environnement manquantes sur Railway."
            
        creds = service_account.Credentials.from_service_account_info(
            json.loads(js_env), 
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        service = build('sheets', 'v4', credentials=creds)
        
        # 1. On liste les onglets pour trouver celui qui contient le code ET l'année
        # Exemple : Cherche un onglet qui contient "CT" et "2026"
        spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get('sheets', [])
        
        target_sheet = None
        for s in sheets:
            title = s['properties']['title']
            if prop_code in title and str(year) in title:
                target_sheet = title
                break
        
        if not target_sheet:
            return f"❌ Aucun onglet trouvé pour {PROPERTIES.get(prop_code, prop_code)} en {year}."

        # 2. Lecture chirurgicale : uniquement l'onglet trouvé
        # On lit la plage A1:M32 (Jours en A, Mois de Janvier(B) à Décembre(M))
        range_name = f"'{target_sheet}'!A1:M32"
        result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
        rows = result.get('values', [])
        
        if not rows:
            return f"L'onglet '{target_sheet}' semble vide."

        availables = []
        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        
        # 3. Analyse de la grille
        for m_idx, month_name in enumerate(months, start=1):
            for row in rows[2:]: # On saute les entêtes
                if len(row) <= m_idx or not row[0]: continue
                
                day_num = row[0].strip()
                cell_content = row[m_idx].strip() if m_idx < len(row) else ""
                
                # Critère de disponibilité : La cellule ne contient pas "&" (ex: "X & Y")
                # Et on vérifie que c'est bien un numéro de jour
                if day_num.isdigit() and "&" not in cell_content:
                    try:
                        day_int = int(day_num)
                        date_obj = datetime(int(year), m_idx, day_int)
                        
                        # Règle spécifique : Pas de mariages les mercredis pour BB, MF, HE
                        if prop_code in ["BB", "MF", "HE"] and date_obj.weekday() == 2:
                            continue
                            
                        availables.append(f"- {day_num} {month_name} {year}")
                    except ValueError:
                        continue # Jour invalide (ex: 31 février)

        if not availables:
            return f"Aucune disponibilité trouvée pour {target_sheet}."
            
        header = f"✅ DISPONIBILITÉS POUR {PROPERTIES.get(prop_code, prop_code)} ({year}) :\n"
        return header + "\n".join(availables)

    except Exception as e:
        return f"Erreur technique : {e}"

if __name__ == "__main__":
    # Utilisation : python3 check_dispo.py [CODE] [ANNEE]
    p_code = sys.argv[1].upper() if len(sys.argv) > 1 else "CT"
    p_year = sys.argv[2] if len(sys.argv) > 2 else "2026"
    
    print(get_availabilities(p_code, p_year))
