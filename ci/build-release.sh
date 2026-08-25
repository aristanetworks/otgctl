#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_root"

python_bin=${OTGCTL_PYTHON_BIN:-python3}
dist_dir=${OTGCTL_DIST_DIR:-dist}
release_tag=${1:-${OTGCTL_RELEASE_TAG:-}}

if [ -e "$dist_dir" ] && [ -n "$(find "$dist_dir" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    printf '%s\n' "Refusing to build into non-empty directory: $dist_dir" >&2
    printf '%s\n' "Set OTGCTL_DIST_DIR to an empty directory or clean it first." >&2
    exit 1
fi
mkdir -p "$dist_dir"

package_version=$(
    "$python_bin" -c 'import re, sys; from pathlib import Path; text=Path("pyproject.toml").read_text(encoding="utf-8"); match=re.search(r"^version\s*=\s*\"([^\"]+)\"", text, re.MULTILINE); sys.exit("Could not find project version") if match is None else print(match.group(1))'
)

if [ -n "$release_tag" ]; then
    case "$release_tag" in
        v*) tag_version=${release_tag#v} ;;
        *) tag_version=$release_tag ;;
    esac
    if [ "$tag_version" != "$package_version" ]; then
        printf '%s\n' "Release tag $release_tag does not match project version $package_version" >&2
        exit 1
    fi
fi

build_args=""
if [ "${OTGCTL_NO_BUILD_ISOLATION:-0}" = "1" ]; then
    build_args="--no-isolation"
fi

# shellcheck disable=SC2086
"$python_bin" -m build --sdist --wheel $build_args --outdir "$dist_dir"

sdist="$dist_dir/otgctl-$package_version.tar.gz"
if [ ! -f "$sdist" ]; then
    printf '%s\n' "Expected source archive was not produced: $sdist" >&2
    exit 1
fi

wheel_count=$(find "$dist_dir" -mindepth 1 -maxdepth 1 -type f \
    -name "otgctl-$package_version-*.whl" | wc -l)
if [ "$wheel_count" -ne 1 ]; then
    printf '%s\n' "Expected exactly one wheel for version $package_version; found $wheel_count" >&2
    exit 1
fi

wheel=$(find "$dist_dir" -mindepth 1 -maxdepth 1 -type f \
    -name "otgctl-$package_version-*.whl" -print -quit)
"$python_bin" -m twine check "$sdist" "$wheel"

printf '%s\n' "Release artifacts are ready in $dist_dir:"
printf '  %s\n' "$sdist" "$wheel"
printf '%s\n' "This script does not publish artifacts. Follow docs/RELEASE_PROCESS.md for upload instructions."
