#!/bin/sh
set -eu

# Build a wheel, install it into a new virtual environment, then run the
# tests.  This tests the installed package rather than the working tree and
# is suitable both for GitHub Actions and a developer workstation.
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"

python_bin=${OTGCTL_PYTHON_BIN:-python3}
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/otgctl-test.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT HUP INT TERM

venv_dir="$work_dir/venv"
dist_dir="$work_dir/dist"
"$python_bin" -m venv "$venv_dir"
venv_python="$venv_dir/bin/python"

"$venv_python" -m pip install --disable-pip-version-check --no-cache-dir \
    "setuptools>=61,<77" wheel build
"$venv_python" -m build --wheel --no-isolation --outdir "$dist_dir"

wheel=$(find "$dist_dir" -maxdepth 1 -type f -name 'otgctl-*.whl' -print -quit)
if [ -z "$wheel" ]; then
    printf '%s\n' "Wheel build did not produce an otgctl wheel" >&2
    exit 1
fi

"$venv_python" -m pip install --disable-pip-version-check --no-cache-dir \
    "${wheel}[snappi,test]"
"$venv_python" -m pytest -q --cov=otgctl --cov-branch --cov-report=term-missing
