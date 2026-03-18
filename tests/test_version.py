"""Tests for the --version CLI flag."""

import subprocess
from pathlib import Path

from lap import __version__

PROJECT_DIR = Path(__file__).parent.parent
CLI = str(PROJECT_DIR / 'lap/cli/main.py')


def test_version_flag():
    result = subprocess.run(
        ['python', CLI, '--version'],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert f"lapsh {__version__}" in result.stdout.strip()
