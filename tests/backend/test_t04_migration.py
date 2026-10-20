"""Apply the complete schema to a clean database and compare it to the ORM."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/src"))


class MigrationTests(unittest.TestCase):
    def test_domain_migration_matches_models(self):
        with tempfile.TemporaryDirectory() as directory:
            database_url = f"sqlite+pysqlite:///{(Path(directory) / 'schema.db').as_posix()}"
            previous_env = {key: os.environ.get(key) for key in ("APP_ENV", "DATABASE_URL")}
            os.environ.update(APP_ENV="test", DATABASE_URL=database_url)
            try:
                config = Config(str(ROOT / "backend/alembic.ini"))
                config.set_main_option("script_location", str(ROOT / "backend/migrations"))
                command.upgrade(config, "head")
                command.check(config)
                engine = create_engine(database_url)
                try:
                    tables = set(inspect(engine).get_table_names())
                    self.assertTrue({"patient", "encounter", "inbound_message", "lab_order",
                                     "lab_report", "lab_observation", "radiology_order",
                                     "radiology_exam", "radiology_report", "imaging_study"} <= tables)
                finally:
                    engine.dispose()
            finally:
                for key, old_value in previous_env.items():
                    if old_value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = old_value


if __name__ == "__main__":
    unittest.main()
