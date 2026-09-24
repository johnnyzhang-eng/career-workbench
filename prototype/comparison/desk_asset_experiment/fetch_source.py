"""Download the exact CC0 Poly Haven 1K glTF source into ignored private/.

Requires curl; verifies Poly Haven's per-file MD5 values and writes a SHA256
manifest. No files from the API other than this single asset are requested.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "private/polyhaven-desk"
API = "https://api.polyhaven.com/files/wooden_table_02"


def curl(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["curl", "-fsSL", "-A", "Mozilla/5.0", "--max-time", "90", url, "-o", str(target)],
        check=True,
    )


def main() -> None:
    api_json = OUT / "source_api.json"
    curl(API, api_json)
    asset = json.loads(api_json.read_text())["gltf"]["1k"]["gltf"]
    files = {"wooden_table_02_1k.gltf": asset, **asset["include"]}
    hashes = {}
    for name, meta in files.items():
        path = OUT / name
        curl(meta["url"], path)
        data = path.read_bytes()
        assert hashlib.md5(data).hexdigest() == meta["md5"], name
        hashes[name] = {"url": meta["url"], "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (OUT / "source_hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print("DESK_SOURCE_VERIFIED", len(hashes), "files")


if __name__ == "__main__":
    main()
