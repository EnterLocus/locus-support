"""Stage the static website without development dependencies or local evidence."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '.site'
EXCLUDED = {'.git', '.github', '.scratch', '.site', 'node_modules', '__pycache__',
            'test-results', 'playwright-report', 'tests', 'package.json',
            'package-lock.json', 'playwright.config.js'}


def build():
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(ROOT, OUTPUT, ignore=lambda directory, names:
                    [name for name in names if name in EXCLUDED])


if __name__ == '__main__':
    build()
