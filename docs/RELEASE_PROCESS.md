# Releasing otgctl

Releases are created from GitHub Releases, never directly from a developer workstation. The release tag, the version in `pyproject.toml`, and the release section in `CHANGELOG.md` must agree. Tags and published package versions are immutable: if anything goes wrong after a publication attempt, fix the issue, increment the version, and make a new tag and release.

## One-time GitHub configuration

Before the first release, a repository administrator must:

- Make `main` the default branch and protect it with pull requests, the CI workflow checks, and no force pushes.
- In **Settings → Rules → Rulesets**, create a tag rule for `v*`. Permit only the release-manager team to create matching tags; block updates and deletion.
- In **Settings → Actions → General**, set the default `GITHUB_TOKEN` permission to read-only. The workflows request their small additional permissions explicitly.
- Create protected deployment environments named `pypi` and `testpypi`. Require release-manager approval for `pypi`; approval for `testpypi` is optional.
- Register PyPI trusted publishers for repository `aristanetworks/otgctl`, workflow file `pypi.yaml`, and environment `pypi`. Register a separate TestPyPI trusted publisher with the same repository and workflow file, using environment `testpypi`.

No PyPI token, personal access token, or other long-lived publishing credential is stored in GitHub. PyPI and TestPyPI publishing uses the short-lived OIDC identity issued to the deployment job.

## Prepare a release

1. Update the version in `pyproject.toml`.
2. Move the relevant entries from `Unreleased` in `CHANGELOG.md` into a dated release section.
3. Commit and merge the release-preparation pull request into `main`.
4. From that merged commit, run the local checks:

   ```bash
   python3 -m pytest
   sh ci/test.sh
   OTGCTL_RELEASE_TAG=v1.0.0 sh ci/build-release.sh
   ```

   The last command verifies the tag/version match and runs `twine check`; it does not publish anything.
5. An authorized release manager creates an annotated, protected tag:

   ```bash
   git tag -a v1.0.0 -m "otgctl 1.0.0"
   git push github v1.0.0
   ```

   Never move or recreate that tag. If a tag is wrong, create a higher version instead.

## Rehearse with TestPyPI

Use a new PEP 440 prerelease, for example `0.9.2rc1`, before the first stable production release. After the tag is pushed, create a GitHub Release from the tag and select **Set as a pre-release**, then publish it. The `pypi.yaml` workflow verifies that the prerelease checkbox agrees with the package version, tests the tagged code on Python 3.9, 3.12, and 3.14, and publishes only through the `testpypi` environment.

Download the GitHub Release assets and verify them:

```bash
sha256sum -c SHA256SUMS
python3 -m venv .venv-testpypi
. .venv-testpypi/bin/activate
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple otgctl==0.9.2rc1
otgctl --version
otgctl --help
```

## Publish a stable release

For a stable version, create and publish a normal GitHub Release (do not select pre-release). The same workflow validates and builds the release once, attaches the wheel, source distribution, and `SHA256SUMS` to the GitHub Release, creates a provenance attestation, and then waits for approval in the protected `pypi` environment. After approval, its separate deployment job publishes the already built artifacts to PyPI via OIDC.

Verify the PyPI project page, GitHub Release assets and checksums, and a clean install from production PyPI. GitHub's automatic source archives are distinct from the packaged Python source distribution attached by the workflow.
