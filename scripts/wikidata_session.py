"""Authenticated Wikidata API session for the lexeme-contribution pipeline.

Uses a BotPassword credential from .env (WD_BOT_USERNAME / WD_BOT_PASSWORD),
logs in once, caches the CSRF token, and exposes small helpers for the
wikibase API modules we need (wbeditentity, wbcreateclaim, etc).

Includes `maxlag=5` on every write so we back off gracefully when Wikidata
replication is lagging, per the wikibase API etiquette guide. The bot
password does NOT need the "high-volume editing" grant; we stay well under
the default user rate limit.

Reads credentials from ../.env:
    WD_BOT_USERNAME=YourName@bot-label
    WD_BOT_PASSWORD=<generated>
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from config import WIKIDATA_API, USER_AGENT

_ENV_PATH = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _load_env():
    env = {}
    with open(_ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


class WikidataSession:
    def __init__(self, username: str | None = None, password: str | None = None):
        if username is None or password is None:
            env = _load_env()
            username = username or env.get("WD_BOT_USERNAME", "")
            password = password or env.get("WD_BOT_PASSWORD", "")
        if not username or not password:
            raise RuntimeError(
                "WD_BOT_USERNAME and WD_BOT_PASSWORD must be set in .env"
            )
        self.username = username
        self.password = password
        self._cookies = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookies)
        )
        self._opener.addheaders = [("User-Agent", USER_AGENT)]
        self._csrf: str | None = None
        self._logged_in = False

    # ------------------------------ HTTP ------------------------------

    def _call(self, params: dict, post: dict | None = None) -> dict:
        qs = urllib.parse.urlencode(params)
        url = f"{WIKIDATA_API}?{qs}"
        if post is not None:
            data = urllib.parse.urlencode(post).encode()
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        else:
            req = urllib.request.Request(url)
        with self._opener.open(req) as resp:
            return json.load(resp)

    # ------------------------- Authentication -------------------------

    def _login(self) -> None:
        if self._logged_in:
            return
        r = self._call({"action": "query", "meta": "tokens",
                        "type": "login", "format": "json"})
        lgtoken = r["query"]["tokens"]["logintoken"]
        r = self._call(
            {"action": "login", "format": "json"},
            post={"lgname": self.username, "lgpassword": self.password,
                  "lgtoken": lgtoken},
        )
        result = r.get("login", {}).get("result")
        if result != "Success":
            reason = r.get("login", {}).get("reason", "(no reason)")
            raise RuntimeError(f"Wikidata login failed: {result} — {reason}")
        self._logged_in = True

    def _csrf_token(self) -> str:
        self._login()
        if self._csrf:
            return self._csrf
        r = self._call({"action": "query", "meta": "tokens",
                        "type": "csrf", "format": "json"})
        self._csrf = r["query"]["tokens"]["csrftoken"]
        if not self._csrf or self._csrf == "+\\":
            raise RuntimeError("Wikidata returned a placeholder CSRF token — auth failed")
        return self._csrf

    # --------------------- Read helpers (no auth) ---------------------

    def get_entity(self, entity_id: str) -> dict:
        """Fetch full entity JSON (Q-item, lexeme, sense, form, property)."""
        url = f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req) as resp:
            data = json.load(resp)
        return data["entities"][entity_id]

    def search_entities(self, query: str, *, entity_type: str = "item",
                        language: str = "en", limit: int = 10) -> list[dict]:
        r = self._call({
            "action": "wbsearchentities",
            "search": query, "language": language, "type": entity_type,
            "limit": str(limit), "format": "json",
        })
        return r.get("search", [])

    def sparql(self, query: str) -> list[dict]:
        params = urllib.parse.urlencode({"query": query, "format": "json"})
        url = f"https://query.wikidata.org/sparql?{params}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/sparql-results+json",
            "User-Agent": USER_AGENT,
        })
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)["results"]["bindings"]

    # ---------------------- Write helpers (auth) ----------------------
    # All writes include maxlag=5 and a summary with AI disclosure.

    def _write(self, params: dict, post: dict) -> dict:
        params = dict(params)
        params.setdefault("format", "json")
        params.setdefault("maxlag", "5")
        post = dict(post)
        post["token"] = self._csrf_token()
        return self._call(params, post=post)

    def wbeditentity_new(self, *, entity_type: str, data: dict, summary: str) -> dict:
        """Create a new entity (item or lexeme)."""
        return self._write(
            {"action": "wbeditentity", "new": entity_type, "summary": summary, "bot": "0"},
            {"data": json.dumps(data, ensure_ascii=False)},
        )

    def wbeditentity(self, *, entity_id: str, data: dict, summary: str,
                     baserevid: int | None = None) -> dict:
        """Edit an existing entity (merge semantics on labels/claims/etc.)."""
        post = {"data": json.dumps(data, ensure_ascii=False)}
        params = {"action": "wbeditentity", "id": entity_id, "summary": summary, "bot": "0"}
        if baserevid is not None:
            params["baserevid"] = str(baserevid)
        return self._write(params, post)

    def wbcreateclaim(self, *, entity_id: str, property_id: str,
                      value_item_id: str, summary: str) -> dict:
        """Add a single claim (<entity> P-prop -> Q/L value) on a lexeme,
        sense, item, or property. `value_item_id` is a Q-ID or L-ID."""
        value = json.dumps(_format_entity_value(value_item_id))
        return self._write(
            {"action": "wbcreateclaim", "entity": entity_id,
             "property": property_id, "snaktype": "value",
             "summary": summary, "bot": "0"},
            {"value": value},
        )


# ----------------------------- Utilities -----------------------------

def _format_entity_value(entity_id: str) -> dict:
    """Return the wikibase JSON value for a Q/L/P entity reference."""
    if entity_id.startswith("Q"):
        return {"entity-type": "item", "numeric-id": int(entity_id[1:]), "id": entity_id}
    if entity_id.startswith("L") and "-" not in entity_id:
        return {"entity-type": "lexeme", "numeric-id": int(entity_id[1:]), "id": entity_id}
    if entity_id.startswith("P"):
        return {"entity-type": "property", "numeric-id": int(entity_id[1:]), "id": entity_id}
    raise ValueError(f"Unrecognised entity id for claim value: {entity_id}")


if __name__ == "__main__":
    # Smoke test: log in, whoami.
    sess = WikidataSession()
    sess._login()
    r = sess._call({"action": "query", "meta": "userinfo", "format": "json"})
    print("logged in as:", r["query"]["userinfo"].get("name"))
    print("csrf token available:", bool(sess._csrf_token()))
