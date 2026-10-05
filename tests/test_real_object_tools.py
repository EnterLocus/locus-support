# Copyright 2026 EnterLocus.com
# SPDX-License-Identifier: Apache-2.0
"""Let `python3 -m unittest discover -s tests` also run the Real Objects command-line
tool tests under tools/real-objects/tests/ (see that folder's README.md).

No network, Create ML training or photogrammetry job runs here: the Swift tools compile
once with `xcrun swiftc -O` (needs Xcode's command-line tools) and `train` is exercised
against a fake `createml` executable. `/usr/bin/python3 -m unittest discover -s
tools/real-objects/tests` runs the same tests directly from that folder.
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL_DIR = os.path.join(ROOT, "tools", "real-objects")
TOOL_TESTS_DIR = os.path.join(TOOL_DIR, "tests")


def load_tests(loader, standard_tests, pattern):
    """unittest's load_tests protocol: replace this (empty) module's tests with the
    Real Objects tool suite, discovered from its own folder so its relative imports work.

    Uses a fresh TestLoader rather than the outer ``loader``: TestLoader.discover()
    mutates self._top_level_dir, and Python 3.9's loader (Xcode's /usr/bin/python3)
    does not restore it afterwards, which corrupts the outer discovery's path handling
    for files found later in tests/. A separate loader avoids touching that state.
    """
    del standard_tests, pattern
    sys.path.insert(0, TOOL_DIR)
    sys.path.insert(0, TOOL_TESTS_DIR)
    return unittest.TestLoader().discover(TOOL_TESTS_DIR, pattern="test_*.py", top_level_dir=TOOL_TESTS_DIR)


if __name__ == "__main__":
    unittest.main()
