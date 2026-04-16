"""Shared configuration for Wikifunctioneering scripts."""

import os

WF_API = "https://www.wikifunctions.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def _read_env(key):
    """Read a value from .env file."""
    try:
        with open(os.path.normpath(_ENV_PATH)) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1]
    except FileNotFoundError:
        pass
    return ""


def _build_user_agent():
    contact = os.environ.get("CONTACT_EMAIL", "") or _read_env("CONTACT_EMAIL")
    if contact:
        return f"Wikifunctioneering/0.1 ({contact})"
    return "Wikifunctioneering/0.1"


USER_AGENT = _build_user_agent()
