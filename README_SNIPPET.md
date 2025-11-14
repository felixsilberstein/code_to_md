# Shareable README Snippet

Copy-paste this short snippet into a gist README or social post to show how to
use `markitdown-batch`.

```markdown
Batch convert source files to Markdown using `markitdown`.

Install and run (example):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python batch_converter.py ./src -o output/combined.md --gitignore -e .py
```

The script writes a single combined Markdown file by default. Use `--separate`
to write one Markdown file per source file. See `GIST_DRAFT.md` in the repo for
the complete script ready to paste into a new gist.
```

Suggested gist description: "Batch convert source files to Markdown with markitdown — combined output, safe fencing, .gitignore support."
