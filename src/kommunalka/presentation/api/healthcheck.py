"""Container healthcheck: exits with 0 when the server answers, with 1 otherwise."""

import sys
from urllib.request import urlopen

URL = "http://localhost:8000/openapi.json"


def main() -> int:
    try:
        urlopen(URL, timeout=4).close()
    except OSError as error:
        print(f"unhealthy: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
