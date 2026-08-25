#!/bin/sh
set -eu

image="${OTGCTL_TEST_IMAGE:-otgctl-test}"
python_version="${PYTHON_VERSION:-3.9}"

docker build \
    --build-arg "PYTHON_VERSION=${python_version}" \
    --tag "${image}" \
    --file ci/Dockerfile.test \
    .
docker run --rm "${image}"
