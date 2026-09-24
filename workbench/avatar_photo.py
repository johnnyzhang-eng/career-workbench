"""Private, user-selected source photo for a future local avatar workflow.

The photo is never an exported scene asset. This module does not generate a
character or contact an external service.
"""

import base64
import binascii
import os
import struct
import tempfile
from pathlib import Path


MAX_PHOTO_BYTES = 2_000_000
MAX_EDGE = 2048
MIN_EDGE = 64
MIME_EXT = {"image/png": ".png", "image/jpeg": ".jpg"}


def _dimensions(data, mime_type):
    if mime_type == "image/png":
        if (len(data) < 45 or data[:8] != b"\x89PNG\r\n\x1a\n"
                or data[12:16] != b"IHDR" or data[-8:] != b"IEND\xaeB`\x82"):
            raise ValueError("PNG 图片无效")
        return struct.unpack(">II", data[16:24])
    if mime_type == "image/jpeg":
        if len(data) < 32 or data[:2] != b"\xff\xd8" or data[-2:] != b"\xff\xd9":
            raise ValueError("JPEG 图片无效")
        offset = 2
        while offset + 4 <= len(data) - 2:
            if data[offset] != 0xff:
                raise ValueError("JPEG 图片无效")
            marker = data[offset + 1]
            if marker == 0xff:
                offset += 1
                continue
            if marker in {0xd8, 0xd9, 0x00}:
                raise ValueError("JPEG 图片无效")
            length = int.from_bytes(data[offset + 2:offset + 4], "big")
            if length < 2 or offset + 2 + length > len(data):
                raise ValueError("JPEG 图片无效")
            if marker in {0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7,
                          0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf}:
                if length < 7:
                    raise ValueError("JPEG 图片无效")
                height = int.from_bytes(data[offset + 5:offset + 7], "big")
                width = int.from_bytes(data[offset + 7:offset + 9], "big")
                return width, height
            offset += 2 + length
        raise ValueError("JPEG 缺少图像尺寸")
    raise ValueError("仅支持 PNG 或 JPEG 原照")


class AvatarPhotoStore:
    """One private original, stored under an ignored workspace directory."""

    def __init__(self, workspace):
        self.workspace = Path(workspace).expanduser().resolve()
        repo = Path(__file__).resolve().parents[1]
        if self.workspace.is_relative_to(repo) and not self.workspace.is_relative_to(repo / "private"):
            raise ValueError("仓库内的照片工作区必须位于 private/ 下")
        self.directory = self.workspace / "private_avatar"

    def _existing(self):
        if self.directory.is_symlink():
            raise ValueError("照片目录不能是符号链接")
        for suffix, mime_type in ((".png", "image/png"), (".jpg", "image/jpeg")):
            path = self.directory / ("source" + suffix)
            if path.is_symlink():
                raise ValueError("照片路径不能是符号链接")
            if path.is_file():
                return path, mime_type
        return None, None

    def status(self):
        path, mime_type = self._existing()
        return {"present": path is not None, "mime_type": mime_type,
                "byte_size": path.stat().st_size if path else 0,
                "generated_avatar": False}

    def read(self):
        path, mime_type = self._existing()
        if path is None:
            raise FileNotFoundError("还没有选择照片")
        return path.read_bytes(), mime_type

    def save(self, encoded, mime_type):
        if mime_type not in MIME_EXT or not isinstance(encoded, str):
            raise ValueError("仅支持 PNG 或 JPEG 原照")
        if len(encoded) > 2_700_000:
            raise ValueError("图片过大，最多 2 MB")
        try:
            data = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("图片编码无效") from exc
        if not data or len(data) > MAX_PHOTO_BYTES:
            raise ValueError("图片过大或为空，最多 2 MB")
        width, height = _dimensions(data, mime_type)
        if not (MIN_EDGE <= width <= MAX_EDGE and MIN_EDGE <= height <= MAX_EDGE):
            raise ValueError("图片宽高须在 64–2048 像素之间")
        if self.directory.is_symlink():
            raise ValueError("照片目录不能是符号链接")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        target = self.directory / ("source" + MIME_EXT[mime_type])
        current, _ = self._existing()
        with tempfile.NamedTemporaryFile(dir=self.directory, prefix=".photo-", delete=False) as tmp:
            temp_path = Path(tmp.name)
            try:
                os.chmod(temp_path, 0o600)
                tmp.write(data)
                tmp.flush()
                os.fsync(tmp.fileno())
            except BaseException:
                temp_path.unlink(missing_ok=True)
                raise
        try:
            os.replace(temp_path, target)
        finally:
            temp_path.unlink(missing_ok=True)
        if current and current != target:
            current.unlink(missing_ok=True)
        return self.status()

    def delete(self):
        if self.directory.is_symlink():
            raise ValueError("照片目录不能是符号链接")
        for suffix in MIME_EXT.values():
            path = self.directory / ("source" + suffix)
            if path.is_symlink():
                raise ValueError("照片路径不能是符号链接")
            path.unlink(missing_ok=True)
        return self.status()
