import os
from dotenv import load_dotenv
from pyfaktory import Client

# Load environment variables from the .env file
load_dotenv()

# Get the Faktory server URL
faktory_server_url = os.getenv('FAKTORY_SERVER_URL')

try:
    with Client(faktory_url=faktory_server_url) as client:
        print("Connected to Faktory server successfully.")
except Exception as e:
    print(f"Failed to connect to Faktory server: {e}")
