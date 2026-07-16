import os

# Root of the repository (python-bloom/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Main bloom package folder
BLOOM_DIR = os.path.join(ROOT_DIR, "bloom")

# Assets directory
ASSETS_DIR = os.path.join(BLOOM_DIR, "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "bloom-terminal-logo.png")
WATERMARK_PATH = os.path.join(ASSETS_DIR, "bloom-art-raw.png")
AVATARS_DIR = os.path.join(ASSETS_DIR, "avatars")

# Runtime data directory
DATA_DIR = os.path.join(ROOT_DIR, "data")
DB_DIR = os.path.join(DATA_DIR, "database")
DB_PATH = os.path.join(DB_DIR, "data.sql")

# Ensure necessary runtime dirs exist
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "cache"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "logs"), exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, "reports"), exist_ok=True)
