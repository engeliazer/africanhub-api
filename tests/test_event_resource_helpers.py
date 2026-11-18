"""Pure helper checks for event zip resources (no Flask required)."""
import ast
import os
import re
import tempfile
import types
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EventResourceHelpersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src = (ROOT / "events/services/event_resource_service.py").read_text()
        tree = ast.parse(src)
        names = {
            "attendance_number_from_request",
            "unsafe_zip_member",
            "zip_archive_error",
            "resource_download_name",
        }
        ns = {
            "os": os,
            "re": re,
            "zipfile": zipfile,
            "UPLOAD_FOLDER": "/tmp",
            "Optional": None,
            "Dict": dict,
            "Any": object,
        }
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                exec(compile(ast.Module([node], type_ignores=[]), "<f>", "exec"), ns)
        cls.helpers = ns

    def test_attendance_number_prefers_named_param(self):
        args = {"attendance_number": " A/B ", "serial_no": "ignored"}
        self.assertEqual(self.helpers["attendance_number_from_request"](args), "A/B")
        self.assertEqual(
            self.helpers["attendance_number_from_request"]({"serial_no": " X/Y "}),
            "X/Y",
        )

    def test_zip_safety_and_download_name(self):
        self.assertTrue(self.helpers["unsafe_zip_member"]("../x.txt"))
        self.assertTrue(self.helpers["unsafe_zip_member"]("/etc/passwd"))
        self.assertFalse(self.helpers["unsafe_zip_member"]("notes/a.pdf"))

        resource = types.SimpleNamespace(id=4, name="Week 1 pack")
        self.assertEqual(self.helpers["resource_download_name"](resource), "Week 1 pack.zip")

    def test_zip_archive_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = os.path.join(tmp, "ok.zip")
            with zipfile.ZipFile(good, "w") as archive:
                archive.writestr("a.txt", "hi")
            self.assertIsNone(self.helpers["zip_archive_error"](good))

            empty = os.path.join(tmp, "empty.zip")
            with zipfile.ZipFile(empty, "w"):
                pass
            self.assertEqual(self.helpers["zip_archive_error"](empty), "Zip archive is empty")

            slip = os.path.join(tmp, "slip.zip")
            with zipfile.ZipFile(slip, "w") as archive:
                archive.writestr("../evil.txt", "nope")
            self.assertEqual(
                self.helpers["zip_archive_error"](slip),
                "Zip archive contains unsafe paths",
            )


if __name__ == "__main__":
    unittest.main()
