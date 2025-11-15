from pathlib import Path
import re
import argparse
import fnmatch
import tempfile
import os
from typing import Iterable, List, Optional

from markitdown import MarkItDown

# Prefer pathspec for full .gitignore semantics; fall back to lightweight handling if unavailable
try:
    from pathspec import PathSpec
    _HAS_PATHSPEC = True
except Exception:
    PathSpec = None  # type: ignore
    _HAS_PATHSPEC = False


def main(
    input_dir: str,
    output: str = "output/combined.md",
    separate: bool = False,
    target_formats: Iterable[str] = (".py", ".js", ".jsx", ".ts", ".tsx", ".json"),
    gitignore: bool = False,
    include_tree: bool = True,
):
    """Convert files under `input_dir` and write Markdown.

    If `output` points to a `.md` file (or its name ends with `.md`) all converted
    files are appended into that single Markdown file with a heading containing
    the file path. If `output` is a directory, individual `.md` files are
    written there (backwards compatible behavior).

    If `include_tree` is True (default), a folder tree structure is prepended
    to combined output or written as a separate `.tree.md` file in separate mode.
    """
    input_path = Path(input_dir)
    md = MarkItDown()

    output_path = Path(output)

    def _language_for_suffix(suffix: str) -> str:
        return {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "jsx",
            ".ts": "typescript",
            # .tsx handled by _choose_language heuristic (JSX vs TS)
            ".tsx": "tsx",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".go": "go",
            ".json": "json",
            ".css": "css",
            ".html": "html",
        }.get(suffix.lower(), "")

    def _choose_language(file_path: Path, suffix: str) -> str:
        """Choose a language hint for code fences.

        For `.tsx` files attempt to detect JSX usage by scanning the file for
        common JSX patterns; if found return `tsx`, otherwise return
        `typescript` to favor TS highlighting for plain TSX files without JSX.
        """
        s = suffix.lower()
        if s == ".tsx":
            try:
                txt = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                txt = ""

            # Simple heuristics for JSX: angle-bracket start of an element, JSX fragment `<>`,
            # or `return (<` patterns inside functions/components.
            if re.search(r"<\s*[A-Za-z]", txt) or "<>" in txt or re.search(r"return\s*\(\s*<", txt):
                return "tsx"
            return "typescript"


    def _safe_fence(text: str) -> str:
        """Return a fence string (backticks) that is longer than any run
        of backticks inside `text` to avoid prematurely closing the fence.
        Always returns at least three backticks (```).
        """
        runs = re.findall(r"`+", text)
        max_run = max((len(r) for r in runs), default=0)
        return "`" * max(3, max_run + 1)

    # Decide mode: combined file by default, or separate files if requested
    combined_mode = not separate and (
        output_path.suffix.lower() == ".md" or output_path.name.lower().endswith(".md")
    )

    def _load_gitignore_spec(base: Path) -> Optional[object]:
        gitfile = base / ".gitignore"
        if not gitfile.exists():
            return None
        try:
            text = gitfile.read_text(encoding="utf-8")
        except Exception:
            return None

        # If pathspec is available, build a PathSpec for gitwildmatch
        if _HAS_PATHSPEC and PathSpec is not None:
            try:
                return PathSpec.from_lines("gitwildmatch", text.splitlines())
            except Exception:
                return None

        # fallback: create a minimal list of patterns (we'll match with fnmatch)
        patterns: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            patterns.append(line)
        # store as a simple PathSpec-like object: a tuple with the raw patterns
        return patterns  # type: ignore

    gitignore_spec = _load_gitignore_spec(input_path) if gitignore else None

    def _build_tree(base_path: Path, prefix: str = "", max_depth: int = 20, current_depth: int = 0) -> List[str]:
        """Recursively build a tree representation of directories and matched files.
        Returns a list of strings representing tree lines.
        """
        if current_depth > max_depth:
            return []
        lines = []
        try:
            items = sorted(base_path.iterdir())
        except (PermissionError, OSError):
            return lines

        dirs = []
        files = []
        for item in items:
            if item.is_dir():
                # Skip hidden and common ignored dirs
                if item.name.startswith(".") or item.name in ("node_modules", "__pycache__", ".venv", "venv"):
                    continue
                dirs.append(item)
            elif item.is_file() and item.suffix in target_formats:
                files.append(item)

        # Show files first, then directories
        for i, f in enumerate(files):
            is_last = (i == len(files) - 1) and len(dirs) == 0
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}{f.name}")

        for i, d in enumerate(dirs):
            is_last = i == len(dirs) - 1
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}{d.name}/")
            extension = "    " if is_last else "│   "
            lines.extend(_build_tree(d, prefix + extension, max_depth, current_depth + 1))

        return lines

    def _convert_with_fallback(src_path: Path):
        """Try to convert using MarkItDown; on decode errors create a temporary
        UTF-8-safe copy (with replacement) and convert that, cleaning up after.
        Returns the conversion `result` or raises the original exception if
        conversion still fails.
        """
        try:
            return md.convert(src_path)
        except Exception as e:
            # If this looks like a Unicode/decoding issue, try a fallback
            is_decode = isinstance(e, UnicodeDecodeError) or "UnicodeDecodeError" in repr(e)
            if not is_decode:
                raise

            try:
                raw = src_path.read_bytes()
            except Exception:
                # Can't read bytes; re-raise original
                raise

            # Decode with replacement to avoid errors and write a temporary file
            try:
                text = raw.decode("utf-8")
            except Exception:
                text = raw.decode("utf-8", errors="replace")

            tmp = None
            try:
                tf = tempfile.NamedTemporaryFile(delete=False, suffix=src_path.suffix)
                tmp = Path(tf.name)
                # write as utf-8 so the converter can read it
                tf.write(text.encode("utf-8"))
                tf.close()
                return md.convert(tmp)
            finally:
                if tmp is not None and tmp.exists():
                    try:
                        os.remove(str(tmp))
                    except Exception:
                        pass

    # Single combined file mode when output looks like a .md file
    if combined_mode:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as out_f:
            # Write tree at the beginning if requested
            if include_tree:
                out_f.write("# Folder Structure\n\n")
                out_f.write("```\n")
                tree_lines = _build_tree(input_path)
                out_f.write(f"{input_path.name}/\n")
                out_f.write("\n".join(tree_lines))
                out_f.write("\n```\n\n---\n\n")

            for file_path in input_path.rglob("*"):
                if file_path.suffix in target_formats:
                    try:
                        result = _convert_with_fallback(file_path)
                    except Exception as e:
                        print(f"✗ Error converting {file_path}: {e}")
                        continue
                    # skip files matched by .gitignore when requested
                    if gitignore_spec:
                        try:
                            rel = file_path.relative_to(input_path).as_posix()
                        except Exception:
                            rel = file_path.as_posix()

                        # If pathspec is available, use it for matching
                        if _HAS_PATHSPEC and PathSpec is not None and isinstance(gitignore_spec, PathSpec):
                            if gitignore_spec.match_file(rel):
                                print(f"- Skipped (gitignore) {rel}")
                                continue
                        else:
                            # fallback to simple fnmatch matching for patterns list
                            matched = False
                            for pat in gitignore_spec:  # type: ignore
                                p = pat.lstrip("/")
                                if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(Path(rel).name, p):
                                    matched = True
                                    break
                            if matched:
                                print(f"- Skipped (gitignore) {rel}")
                                continue
                    try:
                        rel_path = file_path.relative_to(input_path).as_posix()
                    except Exception:
                        rel_path = file_path.as_posix()

                    out_f.write(f"\n\n## {rel_path}\n\n")

                    content = result.markdown or ""
                    # If the converter already provided a top-level code fence, don't double-wrap
                    if not re.match(r"^\s*(```|~~~)", content):
                        fence = _safe_fence(content)
                        lang = _choose_language(file_path, file_path.suffix)
                        lang_hint = f"{lang}" if lang else ""
                        out_f.write(f"{fence}{lang_hint}\n")
                        out_f.write(content)
                        out_f.write(f"\n{fence}\n\n")
                    else:
                        out_f.write(content)

                    print(f"✓ Converted {file_path.name} → {output_path.name}")
    else:
        # Directory mode (previous behavior)
        output_dir = output_path
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write tree as a separate file if requested
        if include_tree:
            tree_file = output_dir / ".tree.md"
            with tree_file.open("w", encoding="utf-8") as tf:
                tf.write("# Folder Structure\n\n")
                tf.write("```\n")
                tree_lines = _build_tree(input_path)
                tf.write(f"{input_path.name}/\n")
                tf.write("\n".join(tree_lines))
                tf.write("\n```\n")
            print(f"✓ Wrote folder tree to {tree_file.name}")

        for file_path in input_path.rglob("*"):
            if file_path.suffix in target_formats:
                try:
                    result = _convert_with_fallback(file_path)
                except Exception as e:
                    print(f"✗ Error converting {file_path.name}: {e}")
                    continue

                # skip files matched by .gitignore when requested
                if gitignore_spec:
                    try:
                        rel = file_path.relative_to(input_path).as_posix()
                    except Exception:
                        rel = file_path.as_posix()

                    # If pathspec is available, use it for matching
                    if _HAS_PATHSPEC and PathSpec is not None and isinstance(gitignore_spec, PathSpec):
                        if gitignore_spec.match_file(rel):
                            print(f"- Skipped (gitignore) {rel}")
                            continue
                    else:
                        # fallback to simple fnmatch matching for patterns list
                        matched = False
                        for pat in gitignore_spec:  # type: ignore
                            p = pat.lstrip("/")
                            if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(Path(rel).name, p):
                                matched = True
                                break
                        if matched:
                            print(f"- Skipped (gitignore) {rel}")
                            continue

                output_file = output_dir / f"{file_path.stem}{file_path.suffix}.md"
                content = result.markdown or ""
                # Wrap per-file output similarly (skip if already fenced)
                if not re.match(r"^\s*(```|~~~)", content):
                    fence = _safe_fence(content)
                    lang = _choose_language(file_path, file_path.suffix)
                    lang_hint = f"{lang}" if lang else ""
                    wrapped = f"{fence}{lang_hint}\n" + content + f"\n{fence}\n"
                else:
                    wrapped = content

                output_file.write_text(wrapped, encoding="utf-8")
                print(f"✓ Converted {file_path.name} → {output_file.name}")


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Batch convert source files to Markdown (single combined file by default)."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=".",
        help="Input directory to scan (default: current directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="output/combined.md",
        help="Output file (if ends with .md) or output directory (for per-file output).",
    )
    parser.add_argument(
        "--separate",
        action="store_true",
        help="Write separate .md files per input file instead of a single combined file.",
    )
    parser.add_argument(
        "--gitignore",
        action="store_true",
        help="Respect ./ .gitignore and skip matching files.",
    )
    parser.add_argument(
        "--ext",
        "-e",
        nargs="+",
        default=[".py", ".js", ".jsx", ".ts", ".tsx", ".json"],
        help="File extensions to include (e.g. .py .js .ts .tsx). Defaults to a set including Python, JS and TS/TSX files",
    )
    parser.add_argument(
        "--no-tree",
        action="store_true",
        help="Skip folder tree structure output (by default, tree is included).",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    # Normalize extensions to start with a dot
    exts = tuple(e if e.startswith(".") else f".{e}" for e in args.ext)
    main(args.input_dir, output=args.output, separate=args.separate, target_formats=exts, gitignore=args.gitignore, include_tree=not args.no_tree)