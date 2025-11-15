# markitdown-batch

A small CLI utility to batch-convert source files to Markdown using `markitdown`.
By default the script writes a single combined Markdown file containing each
input file as a fenced code block with a `## <relative/path>` header.

This repository contains a compact, dependency-light project scaffold so you can
publish this tool as a small public project or run it locally.

## Features

- Convert multiple source files into a single combined Markdown file
- Optional per-file output mode
- Safe code fencing (avoids collisions with backticks inside source)
- Language hints for common file extensions (e.g. `.py` → `python`)
- Optional light `.gitignore` support to skip files
 - Supports web projects including React + TypeScript (`.ts`, `.tsx`, `.js`, `.jsx`)

## Quick start

1. Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Run the tool (default: combined output `output/combined.md`):

```bash
# convert files under ./src (default ext: .py)
.venv/bin/python batch_converter.py ./src -o output/combined.md

# or use the installed console entry (after `pip install .`):
markitdown-batch ./src -o output/combined.md
```

## CLI options

- `input_dir` (positional): directory to scan (default `.`)
- `-o, --output`: output path — if it ends with `.md` a single file is written; otherwise a directory is used for per-file output
- `--separate`: write separate `.md` files per source file
- `-e, --ext`: list of extensions to include (default `.py`)
- `--gitignore`: respect `./.gitignore` and skip matching files

## Packaging

This scaffold includes a `pyproject.toml` so you can install locally:

```bash
pip install --editable .
# now `markitdown-batch` is available as a console command
markitdown-batch ./src -o output/combined.md
```

## Contributing

Small patches and bug reports welcome. This project includes `pathspec` in
`requirements.txt` and the script will use it when you run with `--gitignore`
to provide accurate `.gitignore` matching. If you prefer not to install
that dependency the script will fall back to a simpler matching implementation.

## License

This project is available under the MIT License. See `LICENSE`.
