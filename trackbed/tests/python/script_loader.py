"""Load Python scripts for in-process tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType


def load_script(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name} from {path}")

    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(name)
    previous_bytecode_setting = sys.dont_write_bytecode
    sys.modules[name] = module
    # Skill scanners and the converter read the source directory.
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if previous_module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous_module
        raise
    finally:
        sys.dont_write_bytecode = previous_bytecode_setting
    return module
