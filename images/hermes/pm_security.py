"""Suji image-only security fix, applied before PM atomically publishes tools."""
from pathlib import Path
import hashlib
import json
import shutil
import tarfile
import tempfile

UNDICI_SHA256 = "29c4b8e0b2d86cb8795571c1959012ce057a14ecfd34858335f47c31e770a04f"


def patch_bundled_undici(staged: Path) -> None:
    """Only the exact npm layout/versions in the pinned Hermes image are supported."""
    root = staged.resolve(strict=True)
    destination = root / "lib/node_modules/npm/node_modules/undici"
    if destination.is_symlink() or not destination.resolve(strict=True).is_relative_to(root):
        raise ValueError("unexpected npm Undici path")
    current = json.loads((destination / "package.json").read_text())
    if current.get("name") != "undici" or current.get("version") not in {"6.27.0", "6.28.0", "6.29.1"}:
        raise ValueError("unexpected bundled Undici version")
    archive = Path(__file__).with_name("suji-security") / "undici6.tgz"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != UNDICI_SHA256:
        raise ValueError("Undici artifact checksum mismatch")
    # This operates on unpublished PM scratch state. Any error aborts publication.
    with tempfile.TemporaryDirectory(prefix=".suji-undici-", dir=root) as scratch:
        unpacked = Path(scratch)
        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                if not member.name.startswith("package/") or not (member.isfile() or member.isdir()):
                    raise ValueError("unexpected Undici artifact member")
            tar.extractall(unpacked, filter="data")
        replacement = unpacked / "package"
        package = json.loads((replacement / "package.json").read_text())
        if package.get("name") != "undici" or package.get("version") != "6.29.1" or package.get("dependencies"):
            raise ValueError("unexpected Undici replacement")
        shutil.rmtree(destination)
        replacement.rename(destination)
