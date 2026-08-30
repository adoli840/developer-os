from __future__ import annotations

import unittest
from pathlib import Path


class PostgresBackupVerificationDeploymentTests(unittest.TestCase):
    def test_cleanup_removes_anonymous_restore_volume(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        verifier = (
            repository / "deployment" / "console" / "verify-postgres-backup.sh"
        ).read_text(encoding="utf-8")

        self.assertIn('docker rm -fv "$verification_container"', verifier)
        self.assertNotIn('docker rm -f "$verification_container"', verifier)


if __name__ == "__main__":
    unittest.main()
