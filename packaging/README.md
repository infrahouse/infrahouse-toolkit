# Standalone package

`make package-standalone` builds a self-contained infrahouse-toolkit Debian package for the host's architecture
into `dist/`: a python-build-standalone CPython, the dependencies from `requirements.lock` and nfpm, run by
`build.sh` in the container from `Dockerfile`. `make package-smoke-test` installs it on a clean `ubuntu:noble`
and runs `smoke_test.py`. CI and CD do both for noble on amd64 and arm64 (`.github/workflows/standalone-package.yml`).

The release still ships the Omnibus package (`make package`) until IH-185.

## Testing repository

CD publishes every `main` build of the standalone package to a testing apt repository, never to the release
repository: Puppet installs the toolkit with `ensure => latest`, so anything in the release repository reaches
every node within about 30 minutes. Only canary nodes use the testing repository.

- `https://testing-noble.infrahouse.com/`, codename `noble-testing`, component `main`, `amd64` and `arm64`.
- Signed with the release key. It keeps the last 5 versions.
- The `publish-testing` job in `.github/workflows/python-CD.yml` publishes to it; only infrahouse-toolkit's CD role
  can. The repository is defined in aws-control-493370826424 (`testing.infrahouse.com.tf`).

### Candidate version

A candidate's version is `<toolkit version>+candidate.<run number>.<run attempt>`, for example
`2.67.0+candidate.214.1-1`. `build.sh` appends `PACKAGE_VERSION_SUFFIX` to the Debian version only: the
toolkit's `__version__` stays `2.67.0`.

- It sorts above the release of the same toolkit version (`2.67.0-1`) and below the next release (`2.67.1-1`),
  so a node with both repositories installs the candidate.
- Every CD run and re-run gets a new version, because reprepro refuses a second file with the same version and
  different contents, and the build isn't reproducible. Re-run all jobs, not only the failed ones:
  `publish-testing` checks that both packages carry this attempt's version.
- A release and its candidate publish in parallel. If the Omnibus release lands first, a canary node may run it
  until the candidate lands and its next Puppet run upgrades it.

### Canary node

Add the testing repository next to the release repository, for example in
`/etc/apt/sources.list.d/infrahouse-testing.list`. It is signed with the release key, which
`make install-infrahouse-repo` installs at `/etc/apt/cloud-init.gpg.d/infrahouse.gpg`:

```
deb [signed-by=/etc/apt/cloud-init.gpg.d/infrahouse.gpg] https://testing-noble.infrahouse.com/ noble-testing main
```

With terraform-aws-cloud-init, add it to `extra_repos` with `signed-by=$KEY_FILE` and the release key, which
`https://testing-noble.infrahouse.com/DEB-GPG-KEY-testing-noble.infrahouse.com` also serves.
`apt-cache policy infrahouse-toolkit` shows which version the node will install.
