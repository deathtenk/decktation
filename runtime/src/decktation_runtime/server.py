"""Stub runtime entrypoint for the backend split scaffold."""

import json
import sys


def main():
    request = {"id": "bootstrap", "method": "handshake"}
    response = {
        "id": request["id"],
        "ok": True,
        "result": {
            "message": "decktation runtime scaffold",
        },
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
