import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

# Get raw JSON from environment variable
firebase_creds_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
cred_dict = json.loads(firebase_creds_json)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)

db = firestore.client()
print("✅ Firebase initialized from environment variable!")
