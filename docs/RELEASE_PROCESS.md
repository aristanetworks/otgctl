# Releasing otgctl

Releases are made from a protected version tag. The tag, the version in
`pyproject.toml`, and the release section in `CHANGELOG.md` must agree.

The repository scripts build and validate artifacts but do not publish them.
Publishing should happen from a protected CI job or from an explicitly
authenticated release-manager workstation.

## Prerequisites

Install the release tools in a virtual environment or build environment:

```bash
python3 -m pip install ".[release]"
```

The project build requires setuptools 61 or newer and `wheel`.

## Protect release tags

Tag protection is a server-side
repository policy that prevents unapproved users or jobs from creating,
rewriting, or deleting release tags.

Configure a protected-tag rule for `v*` before the first release:

- **GitLab:** Settings → Repository → Protected tags. Set the pattern to
  `v*` and allow only Maintainers or a dedicated Release Managers group to
  create tags. Do not allow force-push or deletion.
- **GitHub:** Repository Settings → Rules → Rulesets. Add a tag rule for
  `v*`, restrict tag creation to the release-manager team, and prevent updates
  and deletion.
- **Gerrit:** Grant `Create Reference` for `refs/tags/v*` only to the release
  manager or release automation group, and deny force-update and deletion.

After the release commit is merged, an authorized release manager creates and
pushes an annotated tag:

```bash
git tag -a v1.0.0 -m "otgctl 1.0.0"
git push origin v1.0.0
```

The protected-tag CI job should build and publish only when the tag matches
the project version. Release tags should never be moved; if a release needs
correction, publish a new patch version.

## Prepare a release

1. Update the version in `pyproject.toml`.
2. Move the relevant entries from `Unreleased` in `CHANGELOG.md` into a
   dated release section.
3. Commit and merge the release-preparation change.
4. From a checkout of that release commit, run the local tests:

   ```bash
   python3 -m pytest
   ```

5. Run the clean installed-wheel test:

   ```bash
   sh ci/test.sh
   ```

6. Optionally build and validate the release artifacts locally:

   ```bash
   OTGCTL_RELEASE_TAG=v1.0.0 sh ci/build-release.sh
   ```

   The script builds the current checkout; it does not check out the tag.
   It verifies that the requested tag matches the project version and runs
   `twine check`.

7. Create the matching protected tag, for example `v1.0.0`:

   ```bash
   git tag -a v1.0.0 -m "otgctl 1.0.0"
   git push origin v1.0.0
   ```

The tag should be created only after the release commit is merged. The
tag-triggered CI pipeline checks out that tag, repeats the tests and build, and
publishes the CI-produced artifacts rather than trusting a developer's local
build.

## Publishing to PyPI

Configure a PyPI account or a CI trusted publisher before the first release.
For a rehearsal, use TestPyPI first:

```bash
python3 -m twine upload --repository testpypi dist/*
```

The production upload is:

```bash
python3 -m twine upload dist/*
```

Do not commit credentials or put tokens in command history. Prefer CI trusted
publishing or an environment-provided token. PyPI does not allow replacing a
published version, so verify the version and artifacts before uploading.

## Publishing to an internal PyPI-compatible registry

The same artifacts can be uploaded to GitLab, Artifactory, Nexus, or another
internal registry with a repository URL:

```bash
python3 -m twine upload \
  --repository-url https://gitlab.example.com/api/v4/projects/PROJECT_ID/packages/pypi \
  dist/*
```

The exact URL and credential mechanism depend on the registry. In CI, use the
registry's job token or secret rather than a personal token where possible.

## Hosting migration

Source hosting and package hosting are independent. During a GitLab-to-GitHub
or Gerrit migration, keep one authoritative publishing job and disable the
others. GitLab CI, GitHub Actions, and Gerrit/Jenkins or Zuul jobs should all
invoke the shared scripts in `ci/`; only their event and credential wiring
should differ.
