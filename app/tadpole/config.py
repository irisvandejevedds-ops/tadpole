import os
import pathlib
from zoneinfo import ZoneInfo


class Config:
    def __init__(self, env=None):
        e = os.environ if env is None else env
        self.data_dir = pathlib.Path(e.get("TADPOLE_DATA_DIR", "./data"))
        self.tz = ZoneInfo(e.get("TADPOLE_TZ", "America/Toronto"))
        self.require_ts_header = e.get("TADPOLE_REQUIRE_TS_HEADER", "1") == "1"
        self.ts_logins = {x.strip().lower() for x in e.get("TADPOLE_TS_LOGINS", "").split(",") if x.strip()}
        self.cookie_secure = e.get("TADPOLE_COOKIE_SECURE", "1") == "1"

    @property
    def db_path(self):
        return self.data_dir / "tadpole.db"

    @property
    def apk_dir(self):
        return self.data_dir / "apk"


_cfg = None


def get_config() -> Config:
    global _cfg
    if _cfg is None:
        _cfg = Config()
    return _cfg


def set_config(cfg: Config):
    global _cfg
    _cfg = cfg
