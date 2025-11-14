from __future__ import annotations

from pathlib import Path
import importlib.util
import sys


def _load_root_module():
    """Load the top-level `batch_converter.py` as a module and return it.

    This keeps the repository layout simple (single script file) while still
    providing a proper package entry point for `pip install -e .`.
    """
    root = Path(__file__).resolve().parents[1]
    script = root / "batch_converter.py"
    spec = importlib.util.spec_from_file_location("_markitdown_batch_script", str(script))
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def main(*args, **kwargs):
    """Package entry point. When invoked by the console script (no args),
    parse CLI args from the wrapped script and delegate. If `args` are
    provided programmatically, forward them to `batch_converter.main`.
    """
    mod = _load_root_module()

    # If no positional args provided, assume CLI invocation and parse
    if not args and not kwargs and hasattr(mod, "_parse_args"):
        parsed = mod._parse_args()
        exts = tuple(e if e.startswith(".") else f".{e}" for e in parsed.ext)
        # Pass through the --gitignore flag if it exists
        gitignore = getattr(parsed, "gitignore", False)
        return mod.main(parsed.input_dir, output=parsed.output, separate=parsed.separate, target_formats=exts, gitignore=gitignore)

    return mod.main(*args, **kwargs)
