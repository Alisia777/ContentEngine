from __future__ import annotations

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import uvicorn


def main() -> None:
    port = int(os.getenv("PORT", "8014"))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips=os.getenv("QVF_FORWARDED_ALLOW_IPS", "*") or "*",
    )


if __name__ == "__main__":
    main()
