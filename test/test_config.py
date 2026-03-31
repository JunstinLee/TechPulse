import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import utils.config as config_module


class GetBoolEnvTests(unittest.TestCase):
    def test_truthy_variants(self):
        for val in ("1", "true", "TRUE", "yes", "on"):
            with patch.dict(os.environ, {"T_BOOL": val}, clear=False):
                self.assertTrue(config_module._get_bool_env("T_BOOL", "false"), msg=val)

    def test_falsy_default(self):
        with patch.dict(os.environ, {"T_BOOL": "0"}, clear=False):
            self.assertFalse(config_module._get_bool_env("T_BOOL", "false"))


class ConfigReloadInSubprocessTests(unittest.TestCase):
    """避免污染父进程已导入的 Config，在子进程中 reload 验证环境变量。"""

    def test_ai_comment_max_chars_from_env(self):
        code = (
            "import os, sys, importlib\n"
            f"sys.path.insert(0, {str(_ROOT)!r})\n"
            "os.environ['AI_COMMENT_MAX_CHARS'] = '777'\n"
            "import utils.config as c\n"
            "importlib.reload(c)\n"
            "assert c.Config.AI_COMMENT_MAX_CHARS == 777\n"
        )
        subprocess.run([sys.executable, "-c", code], check=True, env={**os.environ}, cwd=str(_ROOT))


if __name__ == "__main__":
    unittest.main()
