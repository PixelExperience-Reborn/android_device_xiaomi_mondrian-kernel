# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from verify_prebuilt import verify  # noqa: E402

RELEASE = "5.10.81-gki-g2efda4cf1afa"


def module(release=RELEASE):
    return b"\x7fELF" + b"\0" * 16 + f"vermagic={release} SMP preempt mod_unload aarch64\0".encode()


class VerifyPrebuiltTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def release(self):
        self.write("Image", b"kernel")
        self.write("dtbo.img", b"dtbo")
        for dtb in ("cape", "capep", "cape-v2"):
            self.write(f"dtbs/{dtb}.dtb", dtb.encode())
        self.write("vendor_ramdisk/clk-rpmh.ko", module())
        self.write("vendor_ramdisk/modules.load", b"clk-rpmh.ko\n")
        self.write("vendor_ramdisk/modules.load.recovery", b"clk-rpmh.ko\n")
        self.write("vendor_dlkm/msm_drm.ko", module())
        self.write("vendor_dlkm/modules.load", b"msm_drm.ko\n")
        self.save_provenance()

    def save_provenance(self, **override):
        files = {}
        for path in sorted(self.root.rglob("*")):
            rel = str(path.relative_to(self.root))
            if path.is_file() and rel != "provenance.json":
                files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        prov = {
            "schema": 1,
            "device": "mondrian",
            "sources": {name: {"repository": f"https://github.com/PixelExperience-Reborn/{repo}",
                               "commit": "a" * 40}
                        for name, repo in (("kernel", "android_kernel_xiaomi_sm8450"),
                                           ("modules", "android_kernel_xiaomi_sm8450-modules"),
                                           ("devicetrees", "android_kernel_xiaomi_sm8450-devicetrees"))},
            "toolchain": {"clang": "clang-r614150", "prebuilt_commit": "c" * 40},
            "ci": {"repository": "PixelExperience-Reborn/android_kernel_xiaomi_sm8450-modules",
                   "workflow": "release", "run_id": 1},
            "kernel_release": RELEASE,
            "files": files,
        }
        prov.update(override)
        (self.root / "provenance.json").write_text(json.dumps(prov))

    def test_empty_repository_passes_before_first_release(self):
        self.assertIsNone(verify(self.root))

    def test_complete_release_passes(self):
        self.release()
        self.assertEqual(verify(self.root)["device"], "mondrian")

    def test_changed_file_is_rejected(self):
        self.release()
        self.write("Image", b"other kernel")
        with self.assertRaisesRegex(ValueError, "sha256 differs"):
            verify(self.root)

    def test_unlisted_file_is_rejected(self):
        self.release()
        self.write("vendor_dlkm/extra.ko", module())
        with self.assertRaisesRegex(ValueError, "file list differs"):
            verify(self.root)

    def test_load_list_naming_absent_module_is_rejected(self):
        self.release()
        self.write("vendor_dlkm/modules.load", b"msm_drm.ko\nmissing.ko\n")
        self.save_provenance()
        with self.assertRaisesRegex(ValueError, "not shipped"):
            verify(self.root)

    def test_module_from_another_kernel_is_rejected(self):
        self.release()
        self.write("vendor_dlkm/msm_drm.ko", module("5.10.236-android12-9"))
        self.save_provenance()
        with self.assertRaisesRegex(ValueError, "vermagic"):
            verify(self.root)

    def test_source_outside_our_organization_is_rejected(self):
        self.release()
        prov = json.loads((self.root / "provenance.json").read_text())
        prov["sources"]["kernel"]["repository"] = "https://github.com/LineageOS/android_kernel_xiaomi_sm8450"
        (self.root / "provenance.json").write_text(json.dumps(prov))
        with self.assertRaisesRegex(ValueError, "PixelExperience-Reborn"):
            verify(self.root)


if __name__ == "__main__":
    unittest.main()
