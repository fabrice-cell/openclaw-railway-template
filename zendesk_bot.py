import urllib.request, json, base64, os, urllib.parse
# On importe la fonction du premier script
from check_dispo import get_availabilities

# CONFIG ZENDESK
url = os.environ.get('ZENDESK_URL')
email = os.environ.get('ZENDESK_EMAIL')
token = os.environ.get('ZENDESK_TOKEN')
auth = base64.b64encode(f"{email}:{token}".encode()).decode()
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

brouillon_bridebook = "Bonjour, Pour recevoir la documentation du Mas de Florette..."

try:
    # 1. Qui suis-je ?
    me_req = urllib.request.Request(f"{url}/api/v2/users/me.json", headers=headers)
    with urllib.request.urlopen(me_req) as resp:
        my_id = json.loads(resp.read().decode())['user']['id']

    # 2. Tickets non affectés
    query = 'type:ticket assignee:none status<solved'
    search_url = f"{url}/api/v2/search.json?query={urllib.parse.quote(query)}"
    
    with urllib.request.urlopen(urllib.request.Request(search_url, headers=headers)) as resp:
        tickets = json.loads(resp.read().decode()).get('results', [])
        
        for t in tickets:
            if 'ia_fait' in t.get('tags', []): continue
            
            subject = (t.get('subject') or "").upper()
            payload = None

            # RÈGLE 1 & 2 : Alertes et Bridebook (Ton code actuel)
            if any(m in subject for m in ["INTERNE : VISITE", "STATUT", "CALL"]):
                payload = {"status": "open", "assignee_id": my_id, "additional_tags": ["ia_fait"]}
            elif "BRIDEBOOK" in subject:
                payload = {"status": "open", "assignee_id": my_id, "comment": {"body": brouillon_bridebook, "public": False}, "additional_tags": ["ia_fait"]}

            # RÈGLE 3 : Appel au script de dispo
            else:
                for code in ["BB", "CT", "MF", "CM", "HE"]:
                    if code in subject and "DISPO" in subject:
                        resultat = get_availabilities(code)
                        payload = {"status": "open", "assignee_id": my_id, "comment": {"body": f"[IA] {resultat}", "public": False}, "additional_tags": ["ia_fait"]}
                        break

            if payload:
                u_req = urllib.request.Request(f"{url}/api/v2/tickets/{t['id']}.json", data=json.dumps({"ticket": payload}).encode(), headers=headers, method='PUT')
                urllib.request.urlopen(u_req)

except Exception as e:
    print(f"Erreur : {e}")
