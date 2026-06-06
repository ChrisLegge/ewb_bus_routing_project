"""
fetch_gtfs.py — download the live Transport for West Midlands GTFS feed.

Credentials are read from the git-ignored .env via dashboard/config.py —
never hard-coded here. Register for free at https://api-portal.tfwm.org.uk/.

Usage:
    python scripts/fetch_gtfs.py
Output:
    data/gtfs/tfwm_gtfs.zip   (git-ignored — regenerable)
"""

import sys
import urllib.request
from pathlib import Path

_REPO = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO / "dashboard"))

from config import require_tfwm_credentials  # noqa: E402

# NOTE: TfWM's API serves GTFS over http only — their https cert is misconfigured
# (hostname mismatch). The payload is open government data and credentials are
# low-sensitivity public-data keys, so plain http is acceptable here.
GTFS_URL = "http://api.tfwm.org.uk/gtfs/tfwm_gtfs.zip"
OUT = _REPO / "data" / "gtfs" / "tfwm_gtfs.zip"


def main() -> None:
    app_id, app_key = require_tfwm_credentials()
    url = f"{GTFS_URL}?app_id={app_id}&app_key={app_key}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading TfWM GTFS feed -> {OUT} ...")
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = resp.read()
    OUT.write_bytes(data)
    print(f"Done: {len(data) / 1_048_576:.1f} MB written.")


if __name__ == "__main__":
    main()
