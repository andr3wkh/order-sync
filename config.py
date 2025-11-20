import os
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv('DATABASE_URL')

# Polling
POLL_INTERVAL = int(os.getenv('POLL_INTERVAL', 60))
