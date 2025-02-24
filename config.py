import os
import json
from pathlib import Path
from typing import Optional, Dict, Any

CONFIG_DIR = Path.home() / '.telegram_dl'
CONFIG_FILE = CONFIG_DIR / 'config.json'
SESSION_FILE = CONFIG_DIR / 'user.session'

def ensure_config_dir():
    """Ensure configuration directory exists."""
    CONFIG_DIR.mkdir(exist_ok=True)

def load_config() -> Dict[str, Any]:
    """Load configuration from file."""
    if not CONFIG_FILE.exists():
        return {}
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config: Dict[str, Any]):
    """Save configuration to file."""
    ensure_config_dir()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def get_session_path() -> Path:
    """Get path to session file."""
    ensure_config_dir()
    return SESSION_FILE

def is_configured() -> bool:
    """Check if the application is configured."""
    config = load_config()
    return all(key in config for key in ['api_id', 'api_hash'])
