"""Secret initialization must preserve existing local credentials."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import init_local_env  # noqa: E402


class LocalEnvironmentTests(unittest.TestCase):
    def test_initialization_is_idempotent_and_does_not_print_secrets(self):
        original = init_local_env.SECRETS
        try:
            with tempfile.TemporaryDirectory() as directory:
                init_local_env.SECRETS = Path(directory)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    init_local_env.main()
                password = (Path(directory) / "postgres_password.txt").read_text(encoding="utf-8")
                orthanc = (Path(directory) / "orthanc.secret.json").read_text(encoding="utf-8")
                hl7_secret = (Path(directory) / "hl7_service_secret.txt").read_text(encoding="utf-8")
                self.assertGreater(len(password.strip()), 30)
                self.assertGreater(len(hl7_secret.strip()), 30)
                config = json.loads(orthanc)
                self.assertTrue(config["AuthenticationEnabled"])
                self.assertGreater(len(config["RegisteredUsers"]["demo"]), 30)
                with contextlib.redirect_stdout(output):
                    init_local_env.main()
                self.assertEqual((Path(directory) / "postgres_password.txt").read_text(encoding="utf-8"), password)
                self.assertEqual((Path(directory) / "orthanc.secret.json").read_text(encoding="utf-8"), orthanc)
                self.assertEqual((Path(directory) / "hl7_service_secret.txt").read_text(encoding="utf-8"), hl7_secret)
                self.assertNotIn(password.strip(), output.getvalue())
                self.assertNotIn(hl7_secret.strip(), output.getvalue())
                self.assertNotIn(config["RegisteredUsers"]["demo"], output.getvalue())
        finally:
            init_local_env.SECRETS = original


if __name__ == "__main__":
    unittest.main()
