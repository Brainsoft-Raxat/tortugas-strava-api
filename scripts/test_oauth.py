import os

from dotenv import load_dotenv
from stravalib import Client

load_dotenv()

STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REDIRECT_URI = os.environ.get("STRAVA_REDIRECT_URI")

client = Client()
url = client.authorization_url(
    client_id=STRAVA_CLIENT_ID,
    redirect_uri=STRAVA_REDIRECT_URI,
)
