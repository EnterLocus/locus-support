# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Let `python3 -m unittest discover -s tests` also run the black-hole View tool
tests under tools/black_hole/tests/ (see that folder's README.md).

They need NumPy and Pillow (`python3 -m pip install numpy pillow`); without
them the suite is reported as skipped. No network is used: a tiny View is baked
from a synthetic sky. `python3 -m unittest discover -s tools/black_hole/tests`
runs the same tests directly from that folder.
"""
import importlib.util
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_DIR = os.path.join(ROOT, "tools", "black_hole")
TOOL_TESTS_DIR = os.path.join(TOOL_DIR, "tests")
MISSING = [name for name in ("numpy", "PIL") if importlib.util.find_spec(name) is None]


class BlackHoleToolDependencies(unittest.TestCase):
    @unittest.skipUnless(MISSING, "NumPy and Pillow are installed")
    def test_dependencies_missing(self):
        self.skipTest("black-hole tool tests need %s (python3 -m pip install numpy pillow)" % ", ".join(MISSING))


def load_tests(loader, standard_tests, pattern):
    """unittest's load_tests protocol: replace this module's tests with the tool suite.

    A fresh TestLoader is used for the same reason as in test_real_object_tools.py:
    Python 3.9's TestLoader.discover() leaves its top-level directory changed.
    """
    del pattern
    if MISSING:
        return standard_tests
    sys.path.insert(0, TOOL_DIR)
    sys.path.insert(0, TOOL_TESTS_DIR)
    return unittest.TestLoader().discover(TOOL_TESTS_DIR, pattern="test_*.py", top_level_dir=TOOL_TESTS_DIR)


if __name__ == "__main__":
    unittest.main()
