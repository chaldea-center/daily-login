from pathlib import Path
from typing import Any

import orjson


def load_json(fp: str | Path, _default=None) -> Any:
    fp = Path(fp)
    if fp.exists():
        return orjson.loads(fp.read_bytes())
    return _default


def dump_json(obj, fp: str | Path | None = None, indent=False, default=None):
    option = orjson.OPT_NON_STR_KEYS
    if indent:
        option |= orjson.OPT_INDENT_2 | orjson.OPT_APPEND_NEWLINE
    result = orjson.dumps(obj, option=option, default=default)
    if fp:
        fp = Path(fp).resolve()
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(result)
    return result
