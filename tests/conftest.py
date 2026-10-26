"""Shared fixtures for GearCheck tests."""

from collections.abc import Iterator
from pathlib import Path
import sqlite3

import pytest

from gearcheck.db import open_database


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "gearcheck-test.db"


@pytest.fixture
def connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    with open_database(db_path) as database:
        yield database
