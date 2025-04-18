import requests
import dotenv

ENV = dotenv.dotenv_values(".env")

ICD_KEY = ENV['ICD_KEY']
ICD_CLIENT = ENV['ICD_CLIENT']
TOKEN_ENDPOINT = 'https://icdaccessmanagement.who.int/connect/token'
SCOPE = 'icdapi_access'
GRANT_TYPE = 'client_credentials'

def fetch():
    payload = {'client_id': ICD_CLIENT, 
	   	   'client_secret': ICD_KEY, 
           'scope': SCOPE, 
           'grant_type': GRANT_TYPE}
    # make request
    r = requests.post(TOKEN_ENDPOINT, data=payload).json()
    token = r['access_token']
    return token

def query_icd_10_api(input: str):
    """
    Function to call the ICD-10 API and return suggestions for medical codes based on the user input.
    """
    token = fetch()
    url = f"https://id.who.int/icd/entity/search?q={input}"
    headers = {
        "Accept": "application/json",
        "Authorization":  f"Bearer {token}",
        'API-Version': 'v2',
        'Accept-Language': 'en'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        suggestions = response.json()
        return suggestions
    else:
        return None

print(query_icd_10_api("Cholera"))