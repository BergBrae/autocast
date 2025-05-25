import yaml
import os
from dotenv import load_dotenv
from typing import Tuple, Optional

from datatypes import AppConfig
from pathlib import Path
from pydantic import ValidationError

CONFIG_FILE_PATH = Path(__file__).parent / "config.yaml"
ENV_FILE_PATH = Path(__file__).parent / ".env"


def load_config_and_tmdb_keys() -> Tuple[AppConfig, Optional[str], Optional[str]]:
    """Loads the application configuration from config.yaml and TMDB API keys from .env."""
    # Load .env file for TMDB API keys
    load_dotenv(dotenv_path=ENV_FILE_PATH)
    tmdb_api_key = os.getenv("TMDB_API_KEY")
    tmdb_read_access_token = os.getenv("TMDB_READ_ACCESS_TOKEN")

    if not CONFIG_FILE_PATH.exists():
        default_roku_devices = [
            {"name": "Living Room TV", "ip_address": "192.168.1.100"},
            {"name": "Bedroom TV", "ip_address": "192.168.1.101"},
        ]
        default_config_data = {
            "roku_devices": default_roku_devices,
        }
        try:
            with open(CONFIG_FILE_PATH, "w") as f:
                yaml.dump(default_config_data, f, indent=2)
            print(f"Created a default configuration file: {CONFIG_FILE_PATH}")
            print("Please update it with your Roku device details.")
            if not tmdb_api_key and not tmdb_read_access_token:
                print(
                    "TMDB API keys not found in .env file. Please create .env and add TMDB_API_KEY and/or TMDB_READ_ACCESS_TOKEN."
                )
        except IOError as e:
            print(f"Error creating default config file: {e}")
            return AppConfig(roku_devices=[]), tmdb_api_key, tmdb_read_access_token

    try:
        with open(CONFIG_FILE_PATH, "r") as f:
            config_data = yaml.safe_load(f)
        if not config_data:
            raise ValueError("Config file is empty or not found.")
        app_config = AppConfig(**config_data)
        return app_config, tmdb_api_key, tmdb_read_access_token
    except FileNotFoundError:
        print(f"Error: Configuration file not found at {CONFIG_FILE_PATH}.")
        return AppConfig(roku_devices=[]), tmdb_api_key, tmdb_read_access_token
    except (yaml.YAMLError, ValidationError) as e:
        print(f"Error loading or validating configuration from {CONFIG_FILE_PATH}: {e}")
        raise e
    except ValueError as e:
        print(f"Error: {e}")
        return AppConfig(roku_devices=[]), tmdb_api_key, tmdb_read_access_token


# Keep the old function for backward compatibility but mark it as deprecated
def load_config_and_omdb_key() -> Tuple[AppConfig, Optional[str]]:
    """Deprecated: Use load_config_and_tmdb_keys() instead."""
    app_config, tmdb_api_key, tmdb_read_access_token = load_config_and_tmdb_keys()
    # Return the read access token as it's more versatile
    return app_config, tmdb_read_access_token


if __name__ == "__main__":
    app_config, api_key, access_token = load_config_and_tmdb_keys()
    if app_config:
        print("Configuration loaded successfully:")
        print(f"Roku Devices: {app_config.roku_devices}")
        print(f"TMDB API Key from .env: {'*' * len(api_key) if api_key else 'Not Set'}")
        print(
            f"TMDB Read Access Token from .env: {'*' * len(access_token) if access_token else 'Not Set'}"
        )

        if app_config.roku_devices:
            print(f"First Roku device name: {app_config.roku_devices[0].name}")
            print(f"First Roku device IP: {app_config.roku_devices[0].ip_address}")
    else:
        print("Failed to load configuration.")
