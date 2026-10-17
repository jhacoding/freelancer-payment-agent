import os, requests
from dotenv import load_dotenv

load_dotenv()
r = requests.post(
    f"{os.getenv('PAYPAL_BASE_URL')}/v1/oauth2/token",
    auth=(os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_CLIENT_SECRET")),
    data={"grant_type": "client_credentials"},
)
print(r.status_code)
print("access_token" in r.json())