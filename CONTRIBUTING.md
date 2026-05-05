# Contributing

Thanks for contributing.

## Local setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Contribution guidelines

- Keep the CLI behavior deterministic.
- Preserve privacy in examples and fixtures. Do not commit real identity documents.
- Add or update tests for behavior changes.
- Keep README examples copy-pasteable.
- Prefer small, reviewable pull requests.

## Good first contributions

- Add more geometry heuristics for broken scanner exports.
- Improve fixture coverage for rotated and mixed-size PDFs.
- Add packaging or platform integration improvements.
