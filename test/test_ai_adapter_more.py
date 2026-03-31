import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import utils.ai_adapter as ai_adapter
from utils.ai_adapter import (
    PromptLoader,
    generate_cache_key,
    generate_content_hash,
    get_adapter,
)


@contextmanager
def _prompts_dir_single(name: str, body: str):
    with tempfile.TemporaryDirectory() as d:
        Path(d, f"{name}.md").write_text(body, encoding="utf-8")
        yield Path(d)


class GenerateHashTests(unittest.TestCase):
    def test_content_hash_stable(self):
        self.assertEqual(generate_content_hash("abc"), generate_content_hash("abc"))

    def test_cache_key_includes_model(self):
        k1 = generate_cache_key("gh", "n", "c", "m1")
        k2 = generate_cache_key("gh", "n", "c", "m2")
        self.assertNotEqual(k1, k2)


class PromptLoaderTests(unittest.TestCase):
    def test_load_replaces_placeholders(self):
        with _prompts_dir_single("t_hello", "Hello {{name}}") as pdir:
            pl = PromptLoader(prompts_dir=str(pdir))
            self.assertEqual(pl.load("t_hello", {"name": "World"}), "Hello World")

    def test_load_missing_template_raises(self):
        pl = PromptLoader(prompts_dir=str(_ROOT / "nonexistent_prompt_dir_xyz"))
        with self.assertRaises(FileNotFoundError):
            pl.load("missing_template_xyz")


class GetAdapterSingletonTests(unittest.TestCase):
    def test_returns_same_instance(self):
        prev = ai_adapter._adapter_instance
        try:
            ai_adapter._adapter_instance = None
            a = get_adapter()
            b = get_adapter()
            self.assertIs(a, b)
        finally:
            ai_adapter._adapter_instance = prev


if __name__ == "__main__":
    unittest.main()
