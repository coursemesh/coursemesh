import os
from pathlib import Path
import tempfile
import unittest

from coursemesh.config import load_config


class ConfigTests(unittest.TestCase):
    def test_loads_local_source(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            cfg = root / "coursemesh.toml"
            cfg.write_text('''[coursemesh]\nstate_dir = ".state"\n[[sources]]\nid="demo"\nname="Demo"\ntype="ics"\npath="demo.ics"\n''')
            loaded = load_config(cfg)
            self.assertEqual(loaded.sources[0].id, "demo")
            self.assertEqual(loaded.state_dir, (root / ".state").resolve())

    def test_url_env_is_resolved_lazily(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            cfg = root / "coursemesh.toml"
            cfg.write_text('''[[sources]]\nid="demo"\nurl_env="COURSEMESH_TEST_URL"\n''')
            source = load_config(cfg).sources[0]
            os.environ["COURSEMESH_TEST_URL"] = "https://example.invalid/calendar.ics"
            try:
                self.assertEqual(source.resolved_url(), "https://example.invalid/calendar.ics")
            finally:
                del os.environ["COURSEMESH_TEST_URL"]

    def test_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as raw:
            cfg = Path(raw) / "coursemesh.toml"
            cfg.write_text('''[[sources]]\nid="x"\npath="a.ics"\n[[sources]]\nid="x"\npath="b.ics"\n''')
            with self.assertRaisesRegex(ValueError, "Duplicate source id"):
                load_config(cfg)

    def test_rejects_output_path_outside_config_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            project = root / "project"
            project.mkdir()
            cfg = project / "coursemesh.toml"
            cfg.write_text(
                '[coursemesh]\noutput_calendar="../outside.ics"\n'
                '[[sources]]\nid="demo"\npath="demo.ics"\n'
            )
            with self.assertRaisesRegex(ValueError, "output_calendar must stay inside"):
                load_config(cfg)

    def test_rejects_source_path_outside_config_directory(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            project = root / "project"
            project.mkdir()
            cfg = project / "coursemesh.toml"
            cfg.write_text('[[sources]]\nid="demo"\npath="../private.ics"\n')
            with self.assertRaisesRegex(ValueError, "path must stay inside"):
                load_config(cfg)


if __name__ == "__main__":
    unittest.main()
