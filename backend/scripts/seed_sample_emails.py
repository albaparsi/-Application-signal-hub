"""Feed sample_emails.json into a running Application Signal Hub instance.

Usage:
    python scripts/seed_sample_emails.py [base_url]

Defaults to http://localhost:8000. Requires the `requests` package
(add it to requirements.txt if you want to keep this around long-term —
kept out of the main requirements for now since it's a dev convenience,
not something the API itself needs).
"""

import json
import sys
from pathlib import Path

import urllib.request
import urllib.error

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
SAMPLE_FILE = Path(__file__).resolve().parent.parent / "sample_emails.json"


def main():
    emails = json.loads(SAMPLE_FILE.read_text())
    for email in emails:
        payload = {k: v for k, v in email.items() if not k.startswith("_")}
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{BASE_URL}/email-events/ingest",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                body = json.loads(resp.read())
                print(f"[{email['message_id']}] {resp.status} — {body['message']}")
        except urllib.error.HTTPError as e:
            print(f"[{email['message_id']}] FAILED ({e.code}): {e.read().decode()}")


if __name__ == "__main__":
    main()
