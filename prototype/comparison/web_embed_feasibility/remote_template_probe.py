#!/usr/bin/env python3
"""Inspect/download only named members of a large public ZIP via HTTP byte ranges.

This is a developer experiment helper, not a build dependency. GitHub's release
asset endpoint currently supports range requests; a server that ignores Range
is rejected so this script never accidentally downloads the full archive.
"""

from __future__ import annotations

import argparse
import io
import urllib.request
import zipfile
from pathlib import Path


class HTTPRangeFile(io.RawIOBase):
    def __init__(self, url: str, size: int):
        self.url = url
        self.size = size
        self.position = 0
        self.transferred = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            target = offset
        elif whence == 1:
            target = self.position + offset
        elif whence == 2:
            target = self.size + offset
        else:
            raise ValueError("invalid whence")
        if target < 0:
            raise ValueError("negative seek")
        self.position = target
        return target

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            amount = self.size - self.position
        amount = min(amount, self.size - self.position)
        if amount <= 0:
            return b""
        first = self.position
        last = first + amount - 1
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={first}-{last}"})
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 206:
                raise RuntimeError(f"Range unsupported: HTTP {response.status}")
            content_range = response.headers.get("Content-Range", "")
            if not content_range.startswith(f"bytes {first}-{last}/"):
                raise RuntimeError(f"unexpected Content-Range: {content_range}")
            data = response.read(amount + 1)
        if len(data) != amount:
            raise RuntimeError(f"range length mismatch: expected {amount}, got {len(data)}")
        self.position += amount
        self.transferred += amount
        return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("size", type=int)
    parser.add_argument("--extract", action="append", default=[], metavar="ZIP_MEMBER")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    remote = HTTPRangeFile(args.url, args.size)
    with zipfile.ZipFile(remote) as archive:
        for item in archive.infolist():
            if "web" in item.filename.lower() or item.filename in args.extract:
                print(f"{item.filename}\tcompressed={item.compress_size}\tuncompressed={item.file_size}")
        if args.extract:
            if not args.out:
                parser.error("--out required with --extract")
            args.out.mkdir(parents=True, exist_ok=True)
            for member in args.extract:
                target = args.out / Path(member).name
                with archive.open(member) as source, target.open("wb") as destination:
                    while chunk := source.read(1024 * 1024):
                        destination.write(chunk)
                print(f"saved={target} bytes={target.stat().st_size}")
    print(f"transferred={remote.transferred}")


if __name__ == "__main__":
    main()
