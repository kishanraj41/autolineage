"""Shared test fixtures for AutoLineage tests."""

import os
import tempfile
import shutil
import pytest


@pytest.fixture
def tmp_workdir():
    """Create a temporary working directory and clean up after."""
    original_dir = os.getcwd()
    test_dir = tempfile.mkdtemp()
    os.chdir(test_dir)
    yield test_dir
    os.chdir(original_dir)
    shutil.rmtree(test_dir)
