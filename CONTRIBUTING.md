# Contributing to otgctl

Thank you for contributing to `otgctl`. Contributions should preserve the
tool's small, predictable command-line interface and should include tests and
documentation when user-visible behavior changes.

## Development setup

The project requires Python 3.9 or newer. Create a virtual environment and
install the development dependencies with:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[test]"
```

The release tools can be installed separately when working on packaging:

```bash
python -m pip install -e ".[release]"
```

## Running tests

Run the local test suite with:

```bash
python -m pytest
```

Run the clean installed-wheel test with:

```bash
sh ci/test.sh
```

The Docker test accepts a Python version override:

```bash
PYTHON_VERSION=3.13 sh ci/test.sh
```

Tests do not require a live OTG server. HTTP requests should be mocked in unit
tests so the suite remains deterministic and safe to run in CI.

## Making changes

- Keep changes focused and maintain the existing Python 3.9 compatibility.
- Add or update tests for changed behavior and failure cases.
- Update `README.md` for user-facing command-line behavior.
- Add a note under `Unreleased` in `CHANGELOG.md` for meaningful user-facing
  changes.
- Run `python -m pytest`, `sh ci/test.sh`, and `git diff --check` before
  submitting a change.
- Never commit credentials, certificates, private keys, generated build
  artifacts, or environment-specific configuration.

There is no requirement to preserve internal implementation details when a
clearer design improves behavior, but changes to command syntax, input formats,
exit codes, or HTTP behavior should be called out explicitly in the change
description.

## Submitting changes for review

Submit changes through the review system configured for the repository.
(Expected to be a pull request on GitHub when we get there.)

Keep review changes focused. The description should explain the problem, the
behavioral change, and the tests that were run. Include examples for changes
to command-line syntax or output.

Address review feedback with follow-up commits or an amended change according
to your normal workflow. Do not rewrite shared branches or release tags.

## Security and sensitive data

Do not put passwords, access tokens, private keys, client certificates, or
production OTG data in issues, review discussions, fixtures, or logs. Use
private reporting mechanisms provided by the hosting organization for security
issues rather than opening a public issue.

## Releases

Contributors do not need to publish packages. The release checklist,
tag protection guidance, and package-publishing instructions are in
[`docs/RELEASE_PROCESS.md`](docs/RELEASE_PROCESS.md).

## License

By contributing, you agree that your contribution is provided under the
project's [Apache License 2.0](LICENSE).
