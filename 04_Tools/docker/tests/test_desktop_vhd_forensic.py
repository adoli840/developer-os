from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "desktop_vhd_forensic.py"
SPEC = importlib.util.spec_from_file_location("desktop_vhd_forensic", MODULE_PATH)
assert SPEC and SPEC.loader
forensic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(forensic)


class DesktopVhdForensicTests(unittest.TestCase):
    def test_container_projection_excludes_environment_and_secret_fields(self) -> None:
        inspected = [{
            "Id": "abc",
            "Name": "/sample",
            "Created": "now",
            "Image": "sha256:image",
            "Config": {"Image": "sample:latest", "Labels": {"project": "sample"}, "Env": ["PASSWORD=secret"]},
            "HostConfig": {"Binds": []},
            "State": {"Status": "exited", "ExitCode": 0},
            "NetworkSettings": {"Networks": {}},
            "Mounts": [],
            "SizeRw": 1,
            "SizeRootFs": 2,
        }]
        with patch.object(forensic, "_ids", return_value=["abc"]), patch.object(
            forensic, "_inspect", return_value=inspected
        ), patch.object(forensic, "_run", return_value=""):
            result = forensic._containers(["docker"])
        self.assertNotIn("environment", result[0])
        self.assertNotIn("Env", str(result[0]))
        self.assertNotIn("secret", str(result[0]))

    def test_inventory_commands_are_read_only_queries(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        for forbidden in (" prune", " rm", " rmi", " volume remove", " container stop"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
