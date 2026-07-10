"""Shared configuration for Wikifunctioneering scripts."""

import os
import re

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


def _pretty_model(model_id):
    """Turn a model id like "claude-opus-4-8[1m]" into "Claude Opus 4.8".

    Date-stamp segments (e.g. "20251001") are dropped. Unrecognized ids
    fall back to a Title-Cased rendering of the raw id. Returns None for
    an empty/None input.
    """
    if not model_id:
        return None
    model_id = re.sub(r"\[.*\]$", "", model_id.strip())
    if not model_id:
        return None
    parts = model_id.split("-")
    families = {"opus", "sonnet", "haiku", "fable"}
    fam = next((p for p in parts if p.lower() in families), None)
    if not fam:
        return " ".join(p.capitalize() for p in parts)
    idx = parts.index(fam)
    version = ".".join(p for p in parts[idx + 1:] if re.fullmatch(r"\d{1,3}", p))
    pieces = ["Claude", fam.capitalize()] + ([version] if version else [])
    return " ".join(pieces)


def _fill_disclosure_model(template):
    """Substitute {model} from CLAUDE_MODEL / AI_MODEL; drop the
    "({model})" parenthetical if no model env var is set."""
    if "{model}" not in template:
        return template
    model = _pretty_model(os.environ.get("CLAUDE_MODEL") or os.environ.get("AI_MODEL"))
    if model:
        return template.replace("{model}", model)
    return re.sub(r"\s*\(\{model\}\)", "", template).replace("{model}", "").strip()


def _build_ai_disclosure():
    """AI disclosure string for edit summaries.

    Source of truth: the `AI_DISCLOSURE` env var (or .env entry). May contain
    a `{model}` placeholder filled from CLAUDE_MODEL / AI_MODEL at run time.
    Falls back to a generic, AI-agnostic string so this codebase is portable
    across different AI tools.
    """
    configured = os.environ.get("AI_DISCLOSURE", "") or _read_env("AI_DISCLOSURE")
    template = configured or "Created with AI assistance ({model})"
    return _fill_disclosure_model(template)


AI_DISCLOSURE = _build_ai_disclosure()
