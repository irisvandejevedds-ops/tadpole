import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from tadpole import clock  # noqa: E402
from tadpole.config import Config, set_config  # noqa: E402
from tadpole.db import open_db  # noqa: E402


def env(tmp_path, **kw):
    e = {"TADPOLE_DATA_DIR": str(tmp_path), "TADPOLE_TZ": "America/Toronto", "TADPOLE_REQUIRE_TS_HEADER": "0", "TADPOLE_COOKIE_SECURE": "0"}
    e.update(kw)
    return e


@pytest.fixture
def cfg(tmp_path):
    c = Config(env(tmp_path))
    set_config(c)
    return c


@pytest.fixture
def db(cfg):
    d = open_db(cfg.db_path)
    yield d
    d.close()
    clock.set_now(None)
