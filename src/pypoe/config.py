import os
from dataclasses import dataclass
from dotenv import load_dotenv

@dataclass
class Config:
    """Configuration class for PyPoe using official Poe API."""
    poe_api_key: str = ""
    database_path: str = "users/history/pypoe_history.db"

    def __post_init__(self):
        load_dotenv()
        self.poe_api_key = os.getenv("POE_API_KEY", self.poe_api_key)
        self.database_path = os.getenv("DATABASE_PATH", self.database_path)

        if not self.poe_api_key:
            raise ValueError(
                "POE_API_KEY is not set. Please get your API key from https://poe.com/api_key "
                "and set it in your .env file or environment variables."
            )

def get_config() -> Config:
    """Get the application configuration."""
    return Config() 