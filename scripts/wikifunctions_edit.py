#!/usr/bin/env python3
"""Create and update ZObjects on Wikifunctions via the API.

Handles authentication, CSRF tokens, and automatic AI disclosure
in edit summaries.

Usage:
    # Create a new ZObject from JSON
    echo '{"Z1K1": "Z2", ...}' | python scripts/wikifunctions_edit.py create

    # Create from a file
    python scripts/wikifunctions_edit.py create --file my_function.json

    # Update an existing ZObject
    python scripts/wikifunctions_edit.py update Z33579 --file updated.json

    # Dry run (show what would be sent without posting)
    echo '...' | python scripts/wikifunctions_edit.py create --dry-run

    # Custom edit summary (AI disclosure is always appended)
    echo '...' | python scripts/wikifunctions_edit.py create --summary "New helper function"

Credentials are read from .env in the project root:
    WF_BOT_USERNAME=User@BotName
    WF_BOT_PASSWORD=password

Edit summaries automatically include AI disclosure per Wikifunctions
community norms (see docs/ai-disclosure.md).
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

from config import WF_API, USER_AGENT

AI_DISCLOSURE = "Created with AI assistance (Claude Opus 4.6)"


def load_env():
    """Load credentials from .env file."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.normpath(env_path)
    env = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env[key.strip()] = value.strip()
    except FileNotFoundError:
        print("Error: .env file not found. Create it with WF_BOT_USERNAME and WF_BOT_PASSWORD.", file=sys.stderr)
        sys.exit(1)
    return env


class WikifunctionsSession:
    """Authenticated session for Wikifunctions API edits."""

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.csrf_token = None

    def _request(self, params, post_data=None):
        """Make an API request. GET if no post_data, POST otherwise."""
        if post_data is not None:
            url = WF_API
            data = urllib.parse.urlencode({**params, **post_data}).encode()
            req = urllib.request.Request(url, data=data, headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/x-www-form-urlencoded",
            })
        else:
            url = f"{WF_API}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

        try:
            with self.opener.open(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                print(f"HTTP {e.code}: {body[:500]}", file=sys.stderr)
                sys.exit(1)

    def login(self):
        """Log in with bot password (two-step: get token, then login)."""
        # Step 1: get login token
        result = self._request({
            "action": "query",
            "meta": "tokens",
            "type": "login",
            "format": "json",
        })
        login_token = result["query"]["tokens"]["logintoken"]

        # Step 2: login
        result = self._request(
            {"action": "login", "format": "json"},
            {
                "lgname": self.username,
                "lgpassword": self.password,
                "lgtoken": login_token,
            },
        )
        login_result = result.get("login", {})
        if login_result.get("result") != "Success":
            reason = login_result.get("reason", login_result.get("result", "unknown"))
            print(f"Login failed: {reason}", file=sys.stderr)
            sys.exit(1)
        print(f"Logged in as {login_result.get('lgusername', self.username)}", file=sys.stderr)

    def get_csrf_token(self):
        """Fetch a CSRF token for editing."""
        result = self._request({
            "action": "query",
            "meta": "tokens",
            "type": "csrf",
            "format": "json",
        })
        self.csrf_token = result["query"]["tokens"]["csrftoken"]
        if self.csrf_token == "+\\":
            print("Error: got anonymous CSRF token — login may have failed.", file=sys.stderr)
            sys.exit(1)

    def create(self, zobject_json, summary=""):
        """Create a new ZObject. Returns the response dict."""
        if not self.csrf_token:
            self.get_csrf_token()

        result = self._request(
            {"action": "wikilambda_edit", "format": "json"},
            {
                "zobject": zobject_json,
                "summary": summary,
                "token": self.csrf_token,
            },
        )
        return result

    def update(self, zid, zobject_json, summary=""):
        """Update an existing ZObject. Returns the response dict."""
        if not self.csrf_token:
            self.get_csrf_token()

        result = self._request(
            {"action": "wikilambda_edit", "format": "json"},
            {
                "zid": zid,
                "zobject": zobject_json,
                "summary": summary,
                "token": self.csrf_token,
            },
        )
        return result


def make_edit_summary(user_summary, ai_task=None):
    """Build an edit summary with AI disclosure appended."""
    if ai_task:
        disclosure = f"Created with AI assistance (Claude Opus 4.6, {ai_task})"
    else:
        disclosure = AI_DISCLOSURE
    if user_summary:
        return f"{user_summary} — {disclosure}"
    return disclosure


def zero_out_self_references(zobject, zid_placeholder="Z0"):
    """Replace self-referential ZIDs with Z0 for new object creation.

    When creating a new ZObject, all self-referential keys (Z2K1, Z8K5,
    argument keys like Z33579K1) need to be Z0. This function takes a
    ZObject dict and replaces the current ZID with Z0.
    """
    raw = json.dumps(zobject)
    # Find the current ZID from Z2K1
    current_zid = None
    z2k1 = zobject.get("Z2K1")
    if isinstance(z2k1, dict):
        current_zid = z2k1.get("Z6K1")
    elif isinstance(z2k1, str):
        current_zid = z2k1

    if not current_zid or current_zid == "Z0":
        return zobject  # Already zeroed out or no ZID to replace

    # Replace ZID references: the ZID itself and argument keys like Z33579K1
    # Be careful: only replace the ZID as a complete token, not as a substring
    # of other ZIDs (e.g., Z33 should not match Z33579)
    import re
    # Replace the ZID in Z2K1
    result = zobject.copy()
    result["Z2K1"] = {"Z1K1": "Z6", "Z6K1": "Z0"}

    # For the rest, we need to do string replacement of the ZID prefix
    # in argument keys (e.g., Z33579K1 -> Z0K1)
    raw = json.dumps(result)
    raw = re.sub(rf'\b{re.escape(current_zid)}(K\d+)', rf'Z0\1', raw)
    # Also replace bare references to the ZID (e.g., Z8K5 identity)
    raw = raw.replace(f'"{current_zid}"', '"Z0"')

    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(
        description="Create and update ZObjects on Wikifunctions"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create subcommand
    create_parser = subparsers.add_parser("create", help="Create a new ZObject")
    create_parser.add_argument("--file", "-f", help="JSON file to read (default: stdin)")
    create_parser.add_argument("--summary", "-s", help="Edit summary (AI disclosure is appended)")
    create_parser.add_argument("--ai-task", help="Brief description of AI's role (e.g., 'composition drafting')")
    create_parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without posting")
    create_parser.add_argument("--zero-self-refs", action="store_true",
                               help="Replace self-referential ZIDs with Z0 (use when creating from a fetched ZObject template)")

    # update subcommand
    update_parser = subparsers.add_parser("update", help="Update an existing ZObject")
    update_parser.add_argument("zid", help="ZID to update (e.g., Z33579)")
    update_parser.add_argument("--file", "-f", help="JSON file to read (default: stdin)")
    update_parser.add_argument("--summary", "-s", help="Edit summary (AI disclosure is appended)")
    update_parser.add_argument("--ai-task", help="Brief description of AI's role (e.g., 'composition drafting')")
    update_parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without posting")

    args = parser.parse_args()

    # Read ZObject JSON
    if args.file:
        with open(args.file) as f:
            zobject = json.load(f)
    else:
        zobject = json.load(sys.stdin)

    if args.command == "create" and args.zero_self_refs:
        zobject = zero_out_self_references(zobject)

    zobject_json = json.dumps(zobject)
    summary = make_edit_summary(args.summary, getattr(args, 'ai_task', None))

    if args.dry_run:
        print("=== DRY RUN ===", file=sys.stderr)
        print(f"Action: {args.command}", file=sys.stderr)
        if args.command == "update":
            print(f"ZID: {args.zid}", file=sys.stderr)
        print(f"Summary: {summary}", file=sys.stderr)
        print(f"ZObject ({len(zobject_json)} bytes):", file=sys.stderr)
        print(json.dumps(zobject, indent=2))
        return

    # Authenticate and execute
    env = load_env()
    username = env.get("WF_BOT_USERNAME")
    password = env.get("WF_BOT_PASSWORD")
    if not username or not password:
        print("Error: WF_BOT_USERNAME and WF_BOT_PASSWORD must be set in .env", file=sys.stderr)
        sys.exit(1)

    session = WikifunctionsSession(username, password)
    session.login()

    if args.command == "create":
        result = session.create(zobject_json, summary)
    else:
        result = session.update(args.zid, zobject_json, summary)

    # Handle response
    if "error" in result:
        print(f"API error: {json.dumps(result['error'], indent=2)}", file=sys.stderr)
        sys.exit(1)

    edit_result = result.get("wikilambda_edit", {})
    if "title" in edit_result:
        zid = edit_result["title"]
        print(f"{zid}", file=sys.stdout)
        print(f"Success: https://www.wikifunctions.org/view/en/{zid}", file=sys.stderr)
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
