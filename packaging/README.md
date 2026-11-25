# Standalone package

`make package-standalone` builds a self-contained infrahouse-toolkit Debian package for the host's architecture
into `dist/`: a python-build-standalone CPython, the dependencies from `requirements.lock` and nfpm, run by
`build.sh` in the container from `Dockerfile`. `make package-smoke-test` installs it on a clean `ubuntu:noble`
and runs `smoke_test.py`. CI and CD do both for noble on amd64 and arm64 (`.github/workflows/standalone-package.yml`).

The standalone package is the released package. The Omnibus package (`make package`) is kept as the rollback for
a few releases (IH-186); see [Rollback](#rollback).

## Release

`.github/workflows/python-CD.yml` runs on every push to `main`. It builds and tests everything before it publishes
anything:

- `plan` reads `RELEASE_PACKAGE` and whether this commit bumped the version.
- `test` runs the unit and contract tests and builds the wheel and sdist.
- `standalone` builds the release package, without a version suffix, for amd64 and arm64, and smoke-tests each on
  a native runner.
- `publish` then publishes PyPI and the release repository (`https://release-noble.infrahouse.com/`, codename
  `noble`), in that order. It needs all of the above, so a broken package blocks the PyPI publish too.

`publish` runs only on `main`, and only for the commit that bumped the version (`make release-*`, then
`git push && git push --tags`). A later push of the same version publishes nothing. Each target is published only
when it lacks this version: PyPI when `https://pypi.org/pypi/infrahouse-toolkit/<version>/json` is 404, and each
architecture when its pool file
`https://release-noble.infrahouse.com/pool/main/i/infrahouse-toolkit/infrahouse-toolkit_<version>-1_<arch>.deb`
is 403 or 404 (the bucket can't be listed, so a missing file is 403). Any other answer fails the job.

- **A release that failed halfway:** "Re-run all jobs" on its run. It publishes only what is still missing, for
  example arm64 after amd64 made it. "Re-run failed jobs" also finishes the release, but if `publish-testing` is
  among the failed jobs it fails again: the candidates of the earlier attempt carry that attempt's version.
- **One kind of package per version:** before it adds an architecture to a version that is already published for
  another, `publish` checks the published one is the same package (standalone or Omnibus), by its description.
- **One release at a time:** `publish` is in the `release-repo-noble` concurrency group and is never cancelled.

Puppet installs the toolkit with `ensure => latest` every 30 minutes, so a release reaches every node within about
30 minutes, and Puppet never downgrades.

## Rollback

A rollback is a higher version, built with Omnibus. Puppet moves the fleet to it within about 30 minutes, and new
instances install it, because it is the highest version in the repository.

1. Set the repository variable `RELEASE_PACKAGE` to `omnibus` (Settings, Secrets and variables, Actions,
   Variables), or `gh variable set RELEASE_PACKAGE --body omnibus --repo infrahouse/infrahouse-toolkit`.
2. On `main`, `make release-patch`, then `git push && git push --tags`.
3. CD builds the Omnibus package (`make package`, noble amd64) and publishes it, with PyPI, at the new version.
   The standalone release packages are still built and smoke-tested, and must pass, but aren't published.
4. Check `https://release-noble.infrahouse.com/dists/noble/main/binary-amd64/Packages` lists the new version, and
   on a couple of nodes, within the next hour, that `dpkg-query -W infrahouse-toolkit` shows it.
5. Set `RELEASE_PACKAGE` back to `standalone`, or delete it: `gh variable delete RELEASE_PACKAGE --repo
   infrahouse/infrahouse-toolkit`. The next release ships the standalone package again.

Under `omnibus` only amd64 is published, as before the standalone package. arm64 nodes stay on the version they
have until the next standalone release.

`RELEASE_PACKAGE` unset or `standalone` releases the standalone package, `omnibus` the Omnibus one. Any other value
fails the CD run before anything is published, the testing repository's candidate included.

To check the Omnibus build still works without releasing it: set `RELEASE_PACKAGE` to `omnibus`, run the CD
workflow by hand on a branch other than `main` (Actions, Python Continuous Deployment, Run workflow), and set it
back. A run outside `main` publishes nothing. Don't release while the variable is set.

## Testing repository

CD publishes every `main` build of the standalone package to a testing apt repository as a candidate, with a
version above the release: Puppet installs the toolkit with `ensure => latest`, so anything in the release
repository reaches every node within about 30 minutes. Only canary nodes use the testing repository.

- `https://testing-noble.infrahouse.com/`, codename `noble-testing`, component `main`, `amd64` and `arm64`.
- Signed with the release key. It keeps the last 5 versions.
- The `publish-testing` job in `.github/workflows/python-CD.yml` publishes to it; only infrahouse-toolkit's CD role
  can. The repository is defined in aws-control-493370826424 (`testing.infrahouse.com.tf`).
- The candidate is a separate build (`standalone-candidate`) from the release (`standalone`). Their artifacts are
  named `infrahouse-toolkit-candidate-noble-<arch>` and `infrahouse-toolkit-release-noble-<arch>`, and each publish
  job checks the version of every package it publishes, so neither can publish the other's.

### Candidate version

A candidate's version is `<toolkit version>+candidate.<run number>.<run attempt>`, for example
`2.67.0+candidate.214.1-1`. `build.sh` appends `PACKAGE_VERSION_SUFFIX` to the Debian version only: the
toolkit's `__version__` stays `2.67.0`.

- It sorts above the release of the same toolkit version (`2.67.0-1`) and below the next release (`2.67.1-1`),
  so a node with both repositories installs the candidate.
- Every CD run and re-run gets a new version, because reprepro refuses a second file with the same version and
  different contents, and the build isn't reproducible. Re-run all jobs, not only the failed ones:
  `publish-testing` checks that both packages carry this attempt's version.
- A release and its candidate publish in parallel. If the release lands first, a canary node may run it until the
  candidate lands and its next Puppet run upgrades it.

### Canary node

Add the testing repository next to the release repository, for example in
`/etc/apt/sources.list.d/infrahouse-testing.list`. It is signed with the release key, which is already on the node,
but not at the same path everywhere: InfraHouse nodes have it at `/etc/apt/keyrings/infrahouse.gpg`, and
`make install-infrahouse-repo` installs it at `/etc/apt/cloud-init.gpg.d/infrahouse.gpg`. Copy the `signed-by=`
path from the node's existing InfraHouse source line:

```bash
grep -rh infrahouse.com /etc/apt/sources.list.d/
```

```
deb [signed-by=/etc/apt/keyrings/infrahouse.gpg] https://testing-noble.infrahouse.com/ noble-testing main
```

With terraform-aws-cloud-init, add it to `extra_repos` with `signed-by=$KEY_FILE` and the release key, which
`https://testing-noble.infrahouse.com/DEB-GPG-KEY-testing-noble.infrahouse.com` also serves.
`apt-cache policy infrahouse-toolkit` shows which version the node will install.
