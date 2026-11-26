#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify the prebuilt mondrian kernel against its provenance.json.

Every prebuilt file must be listed in provenance.json with its sha256, every
listed file must exist, the provenance must name the exact source commits,
compiler and CI run it was built from, each module load list may only name
modules shipped next to it, and every module must carry the vermagic of the
kernel it was built with. Without any prebuilt file (before the first
release) the check passes and says so.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOT_PREBUILT = {"README.md", "provenance.json", ".gitattributes", "Android.bp"}
NOT_PREBUILT_DIRS = {".git", ".github", "tools", "tests"}
REQUIRED = ("Image", "dtbo.img")
REQUIRED_DIRS = ("dtbs", "vendor_ramdisk", "vendor_dlkm")
LOAD_LISTS = {
    "vendor_ramdisk": ("modules.load", "modules.load.recovery"),
    "vendor_dlkm": ("modules.load",),
}
SOURCES = ("kernel", "modules", "devicetrees")
SHA1 = re.compile(r"[0-9a-f]{40}")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prebuilt_files(root):
    files = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or rel.parts[0] in NOT_PREBUILT_DIRS or str(rel) in NOT_PREBUILT:
            continue
        files.append(str(rel))
    return files


def vermagic(path):
    data = Path(path).read_bytes()
    match = re.search(rb"vermagic=([^\0]+)\0", data)
    return match.group(1).decode() if match else None


def verify(root=ROOT):
    files = prebuilt_files(root)
    provenance_path = root / "provenance.json"
    if not files and not provenance_path.exists():
        return None
    require(provenance_path.exists(), "prebuilt files without provenance.json")
    prov = json.loads(provenance_path.read_text(encoding="utf-8"))

    require(prov.get("schema") == 1, "unknown provenance schema")
    require(prov.get("device") == "mondrian", "provenance is not for mondrian")
    for name in SOURCES:
        source = prov.get("sources", {}).get(name, {})
        require(str(source.get("repository", "")).startswith("https://github.com/PixelExperience-Reborn/"),
                f"{name}: source must be a PixelExperience-Reborn repository")
        require(SHA1.fullmatch(source.get("commit", "")) is not None, f"{name}: commit must be 40-hex")
    toolchain = prov.get("toolchain", {})
    require(toolchain.get("clang") and SHA1.fullmatch(toolchain.get("prebuilt_commit", "")),
            "toolchain: clang version and prebuilt commit are required")
    ci = prov.get("ci", {})
    require(isinstance(ci.get("run_id"), int) and ci.get("repository") and ci.get("workflow"),
            "ci: repository, workflow and run_id are required")
    release = prov.get("kernel_release", "")
    require(release, "kernel_release is required")

    listed = prov.get("files", {})
    require(sorted(listed) == files,
            f"provenance file list differs from the repository: {sorted(set(listed) ^ set(files))}")
    for rel, digest in listed.items():
        require(sha256(root / rel) == digest, f"{rel}: sha256 differs from provenance")

    for rel in REQUIRED:
        require(rel in listed, f"missing {rel}")
    for directory in REQUIRED_DIRS:
        require(any(f.startswith(directory + "/") for f in files), f"missing {directory}/")
    require(any(f.startswith("dtbs/") and f.endswith(".dtb") for f in files), "dtbs/ holds no .dtb")

    for directory, lists in LOAD_LISTS.items():
        shipped = {Path(f).name for f in files if f.startswith(directory + "/") and f.endswith(".ko")}
        for name in lists:
            rel = f"{directory}/{name}"
            require(rel in listed, f"missing {rel}")
            entries = [line.strip() for line in (root / rel).read_text().splitlines() if line.strip()]
            require(len(entries) == len(set(entries)), f"{rel}: duplicate entries")
            missing = sorted(set(entries) - shipped)
            require(not missing, f"{rel}: lists modules not shipped in {directory}/: {missing}")
        for module in shipped:
            magic = vermagic(root / directory / module)
            require(magic is not None and magic.split()[0] == release,
                    f"{directory}/{module}: vermagic {magic!r} does not match {release}")
    return prov


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        prov = verify(args.root)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    if prov is None:
        print("[INFO] no prebuilt kernel release committed yet")
    else:
        print(f"[PASS] {len(prov['files'])} prebuilt files match provenance: kernel "
              f"{prov['sources']['kernel']['commit'][:12]}, modules {prov['sources']['modules']['commit'][:12]}, "
              f"DT {prov['sources']['devicetrees']['commit'][:12]}, {prov['toolchain']['clang']}, "
              f"CI run {prov['ci']['run_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
