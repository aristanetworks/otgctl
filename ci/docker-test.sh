#!/bin/sh
set -eu

# Optional local wrapper for the same clean-wheel test used by GitHub Actions.
image="${OTGCTL_TEST_IMAGE:-otgctl-test}"
python_version="${PYTHON_VERSION:-3.9}"

docker build \
    --build-arg "PYTHON_VERSION=${python_version}" \
    --tag "${image}" \
    --file ci/Dockerfile.test \
    .
docker run --rm "${image}"
