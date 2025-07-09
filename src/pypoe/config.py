import os
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path

@dataclass
class Config:
    """Configuration class for PyPoe using official Poe API."""
    poe_api_key: str = ""
    database_path: str = ""
    web_username: str = ""
    web_password: str = ""

    def __post_init__(self):
        load_dotenv()
        
        # Set default database path to user-specific directory (~/.pypoe/)
        default_db_path = os.path.expanduser("~/.pypoe/single_webchat_history.db")
        
        self.poe_api_key = os.getenv("POE_API_KEY", self.poe_api_key)
        self.database_path = os.getenv("DATABASE_PATH", default_db_path)
        self.web_username = os.getenv("PYPOE_WEB_USERNAME", self.web_username)
        self.web_password = os.getenv("PYPOE_WEB_PASSWORD", self.web_password)

        # Ensure the ~/.pypoe directory exists
        pypoe_dir = Path(self.database_path).parent
        pypoe_dir.mkdir(parents=True, exist_ok=True)

        if not self.poe_api_key:
            raise ValueError(
                "POE_API_KEY is not set. Please get your API key from https://poe.com/api_key "
                "and set it in your .env file or environment variables."
            )

def get_config() -> Config:
    """Get the application configuration."""
    return Config() 