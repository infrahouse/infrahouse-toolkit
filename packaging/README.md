# Standalone package

`make package-standalone` builds a self-contained infrahouse-toolkit Debian package for the host's architecture
into `dist/`: a python-build-standalone CPython, the dependencies from `requirements.lock` and nfpm, run by
`build.sh` in the container from `Dockerfile`. `make package-smoke-test` installs it on a clean `ubuntu:noble`
and runs `smoke_test.py`. CI and CD do both for noble on amd64 and arm64 (`.github/workflows/standalone-package.yml`).

The standalone package is the released package. Puppet never downgrades, so a bad release is fixed by releasing a
higher version; see [Roll-forward](#roll-forward).

The same interpreter and lock also make the macOS arm64 tarball that the Homebrew formula installs
(`make package-macos`); see [macOS tarball](#macos-tarball).

## Release

`.github/workflows/python-CD.yml` runs on every push to `main`. It builds and tests everything before it publishes
anything:

- `plan` reads this commit's version and whether this commit bumped it.
- `test` runs the unit and contract tests and builds the wheel and sdist.
- `standalone` builds the release package, without a version suffix, for amd64 and arm64, and smoke-tests each on
  a native runner.
- `publish` then publishes PyPI and the release repository (`https://release-noble.infrahouse.com/`, codename
  `noble`), in that order. It needs all of the above, so a broken package blocks the PyPI publish too.

`publish` runs only on `main`, and only for the commit that raised the version (`make release-*`, then
`git push && git push --tags`). The bump commit must be the last commit of its push: if another commit follows it in
the same push, nothing is released, and the fix is another bump. A later push of the same version publishes nothing,
and neither does a revert of a bump. Each target is published only
when it lacks this version: PyPI when `https://pypi.org/pypi/infrahouse-toolkit/<version>/json` is 404, and each
architecture when its pool file
`https://release-noble.infrahouse.com/pool/main/i/infrahouse-toolkit/infrahouse-toolkit_<version>-1_<arch>.deb`
is 403 or 404 (the bucket can't be listed, so a missing file is 403). Any other answer fails the job.

- **A release that failed halfway:** "Re-run all jobs" on its run. It publishes only what is still missing, for
  example arm64 after amd64 made it. "Re-run failed jobs" also finishes the release, but if `publish-testing` is
  among the failed jobs it fails again: the candidates of the earlier attempt carry that attempt's version.
- **One release at a time:** `publish` is in the `release-repo-noble` concurrency group and is never cancelled.
- **The publisher is the last release:** `publish` and `publish-testing` install the newest infrahouse-toolkit from
  the release repository and publish with its `ih-s3-reprepro`, whose `includedeb` (s3fs mount, GPG import,
  reprepro) no smoke test runs. After each release,
  run the CD workflow by hand on `main` (Actions, Python Continuous Deployment, Run workflow): `publish` finds
  everything published and publishes nothing, and `publish-testing` publishes a candidate with the new release's
  `ih-s3-reprepro`. Its log must show `Setting up infrahouse-toolkit (<new version>-1)`. If it shows the previous
  version, CloudFront still served the old index: wait a few minutes and run it again.

Puppet installs the toolkit with `ensure => latest` every 30 minutes, so a release reaches every node within about
30 minutes, and Puppet never downgrades.

## Roll-forward

There is no rollback: Puppet never downgrades, so a node keeps a bad release until a higher version is published. A
bad release is fixed by releasing that higher version. Puppet moves the fleet to it within about 30 minutes, and new
instances install it, because it is the highest version in the repository.

1. **If new instances mustn't install the bad release meanwhile:** remove it from the release repository (below).
   Nodes that have it keep it, and new instances install the release before it.
2. Revert the bad change in a pull request and merge it. That push publishes only a candidate: it doesn't bump the
   version.
3. On `main`, `make release-patch`, then `git push && git push --tags`. CD publishes the new version to PyPI and the
   release repository, amd64 and arm64, like any release.
4. Check `https://release-noble.infrahouse.com/dists/noble/main/binary-amd64/Packages` and `…/binary-arm64/Packages`
   list the new version, and on a couple of nodes, within the next hour, that `dpkg-query -W infrahouse-toolkit`
   shows it.

Canary nodes need nothing: the revert's candidate has a higher run number than the bad release's, and the new release
sorts above both. On the Homebrew side, the new release's `publish-homebrew` opens the formula pull request for it and
names the bad release's if that one is still open, to close without merging.

If `publish` fails inside `ih-s3-reprepro`, the newest release's publisher is broken (see "The publisher is the last
release" above). If the bad release is removed from the repository, `publish` installs the release before it, whose
publisher published the bad one. Otherwise, in a PR, pin the install step of `publish` to that release,
`sudo apt-get -y install --allow-downgrades infrahouse-toolkit=<version>-1`, merge it (that push publishes nothing),
then release. Drop the pin in the next release.

### Removing a version from the release repository

`publish`'s own flags, with `remove` in place of `includedeb`:

```bash
ih-s3-reprepro \
  --aws-region us-west-1 \
  --bucket infrahouse-release-noble \
  --gpg-key-secret-id packager-key-noble \
  --gpg-passphrase-secret-id packager-passphrase-noble \
  remove noble infrahouse-toolkit=<version>-1
```

- `infrahouse-toolkit=<version>-1` removes exactly that version, from amd64 and arm64, and deletes its pool files.
  Every other version stays. Without `=<version>-1`, reprepro removes whichever version is the newest.
- It needs Linux, where `ih-s3-reprepro` mounts the bucket with s3fs, and the reprepro from the release repository
  (5.4.5, which installing the toolkit from there pulls in), because the repository keeps every version (`Limit: 0`).
  Ubuntu noble's own reprepro, 5.3.1, can't read that configuration.
- It needs a role that may write the bucket and read the signing key: `bucket_admin_roles` and
  `signing_key_readers` of `release.infrahouse.com.tf` in aws-control-493370826424. The jumphost's role is in both.
  If the bad release broke `ih-s3-reprepro`, install the release before it there first.
- The `Packages` index stops listing the version once CloudFront serves the new one, which can take a few minutes.
- Until the revert is on `main`, don't re-run the bad release's CD run or run CD by hand on `main`: the pool file is
  gone now, so `publish` would publish the bad release again.
- PyPI keeps the version; the next release supersedes it there.

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

## macOS tarball

`make package-macos` builds `dist/infrahouse-toolkit-<version>-macos-arm64.tar.gz` and its `.sha256`, the
self-contained tree the Homebrew formula installs. `build-macos.sh` is the twin of `build.sh`: the same
python-build-standalone interpreter, fetched by the same uv version, the same `requirements.lock` and the same toolkit
wheel. It runs natively on an arm64 Mac, without Docker, and builds arm64 only.
`make package-macos-smoke-test` tests the tarball as Homebrew installs it.

- **The tarball** is the interpreter tree itself, `bin/`, `lib/`, `include/`, `share/` and python-build-standalone's
  `BUILD`, with no top-level directory: the formula does `libexec.install Dir["*"]` and links `libexec/bin/ih-*` into
  its `bin`. It has no `._*` or `.DS_Store` files and no extended attributes. The `.sha256` is one line,
  `<sha256>  <file name>`, as `shasum -a 256` writes it.
- **One uv version.** It decides which python-build-standalone build `uv python install` fetches, so both builds use
  the version `packaging/Dockerfile` pins. `build-macos.sh` reads it from there (`build-macos.sh --uv-version` prints
  it) and fails if the `uv` on `PATH` is another version. Renovate's Dockerfile update moves both builds.
- **Relocatable scripts.** uv writes console scripts with an absolute path to the build tree. `build-macos.sh`
  replaces that header with `macos-script-header`, which runs the `python3` next to the script's real path.
  `realpath` matters: Homebrew links `/opt/homebrew/bin/ih-ec2` → `Cellar/…/bin/ih-ec2` → `libexec/bin/ih-ec2`. The
  build fails if any file in `bin/` still contains the build directory's path.
- **The macOS floor**, `MACOS_FLOOR`, is 13.0, the first macOS with `realpath(1)`, which the header needs. uv chooses
  wheels for it (`MACOSX_DEPLOYMENT_TARGET`), not for the runner's macOS. Then the build reads the minimum macOS of
  every Mach-O file in the tree with `otool -l` (`minos` of `LC_BUILD_VERSION`, or `LC_VERSION_MIN_MACOSX`) and fails
  if one is newer. Wheel tags aren't enough: protobuf's wheel is tagged `macosx_10_9_universal2`, but its arm64
  `_message.abi3.so` needs 12.0, today's newest.
- **The smoke test** deletes the build tree (`build/macos-arm64`), checks the `.sha256`, unpacks the tarball into a
  directory whose path contains a space, and links each `ih-*` script through two relative symlinks, as Homebrew
  does. With only those links and the system directories on `PATH`, it checks each script's header and that it
  resolves through the links, runs `smoke_test.py --no-deb` with the unpacked interpreter (every `ih-*` `--help` as a
  process, through both links), and imports `nacl.bindings` and `cryptography.hazmat.bindings._rust`.
  `smoke_test.py --no-deb` skips the Debian package checks; without it, `smoke_test.py` runs exactly what it runs on
  the .deb.

### Building it on a Mac

Install the pinned uv next to any other, for example in a virtualenv, and put it first on `PATH`:

```bash
python3 -m venv /tmp/uv-pinned && /tmp/uv-pinned/bin/pip install "uv==$(packaging/build-macos.sh --uv-version)"
```

```bash
PATH="/tmp/uv-pinned/bin:$PATH" make package-macos
```

```bash
make package-macos-smoke-test
```

The build takes about 20 seconds and leaves the tree in `build/macos-arm64` until the smoke test deletes it.

### How it reaches the release

`.github/workflows/macos-package.yml` builds and smoke-tests the tarball on a `macos-15` runner and uploads it as an
artifact. `python-CI.yml` runs it on every pull request (check `macOS package / macOS arm64`), and `python-CD.yml` on
every push to `main`. On the push that bumps the version, `publish-macos` attaches both files to the GitHub release
`v<version>`, which the formula downloads
(`https://github.com/infrahouse/infrahouse-toolkit/releases/download/v<version>/infrahouse-toolkit-<version>-macos-arm64.tar.gz`):

- It needs `plan`, `test` and the macOS build, so a version whose unit tests failed gets no tarball.
- It is independent of `publish`: neither waits for the other, so a macOS runner outage can't hold back PyPI or the
  release apt repository. A failure in either fails the run.
- It checks the artifact holds exactly the tarball and its `.sha256` for this version, and that they match.
- `release.yml` creates the release when the tag is pushed, after the push to `main`. `publish-macos` checks for it
  every 30 seconds for up to 15 minutes, then fails with a message that the release doesn't exist. It also fails if
  the tag isn't the commit this run built.
- It never replaces an asset: builds aren't byte-reproducible, and a formula may already pin the first upload's
  checksum. If the release has both files (a re-run), it uploads nothing. If it has only one, it fails and names it.
  Otherwise it uploads the tarball, then the `.sha256`, with the job's `GITHUB_TOKEN`. Last, it downloads both from
  the release and checks the checksum.
- It is the only job with `contents: write`, and has no AWS role and no PyPI token.

If `publish-macos` failed:

- **The release didn't appear:** push the tag (`git push --tags`), check `release.yml`'s run, then re-run the failed
  jobs.
- **The macOS build failed:** fix it and re-run the failed jobs: `macos`, `publish-macos` and then
  `publish-homebrew`, which waited for it, run again, nothing else.
- **The release has one of the two files:** check it, delete it (`gh release delete-asset v<version> <file>`), and
  re-run the failed jobs.

### How a release reaches the Homebrew formula

On the push that bumps the version, after `publish-macos` attached the tarball, `publish-homebrew` opens the pull
request in [infrahouse/homebrew-tap](https://github.com/infrahouse/homebrew-tap) that moves
`Formula/infrahouse-toolkit.rb` to the release. The tap's CI, `infrahouse-toolkit formula`, installs and tests the
formula on it, and Aleks merges it. Then `brew update && brew upgrade infrahouse-toolkit` installs the release. The
credential follows the design document
[GitHub credentials for automation](https://linear.app/infrahouse/document/design-github-credentials-for-automation-token-app-key-in-secrets-b7f0b1e54767)
(IH-190).

- **The job graph.** `publish-homebrew` needs `plan` and `publish-macos`, and runs only on `main`, only when the
  commit bumped the version and `publish-macos` succeeded. Nothing needs it, so it can't hold back or change PyPI, the
  apt repositories or the tarball. One runs at a time (concurrency group `homebrew-tap-formula`), and a running one is
  never cancelled.
- **The release, not the build.** `check-release.sh` downloads the release's tarball and `.sha256` from the url the
  formula gets, and checks one against the other. The formula gets that checksum, never this run's build.
- **Only forward.** `open-formula-pr.sh` clones the tap and reads the formula's version from its `url`. If the formula
  is already at the release, or newer (a re-run of an older release), or the tap has an open pull request for a newer
  release, it stops with a notice, green, and opens nothing. A formula at the release with another `sha256` is an
  error: it wouldn't install. When it opens a pull request, a notice names any open one for an older release, to close
  without merging.
- **The change.** It changes `url` and `sha256`, and `version` if the formula has that line, then checks the diff:
  exactly those lines, and the new `url` is
  `https://github.com/infrahouse/infrahouse-toolkit/releases/download/v<version>/infrahouse-toolkit-<version>-macos-arm64.tar.gz`.
  A formula with another layout (a second `url`, a `mirror`, a `resource` or `bottle` block) fails the job before
  anything is pushed.
- **The pull request.** The branch is `toolkit-<version>`, one commit authored by the App, on the tap's `main`. The
  title is `infrahouse-toolkit <version>`, and the body links the release and the CD run. A re-run updates the open
  pull request instead of opening a second one; the branch belongs to CD, and a re-run resets it to `main` plus the
  change if `main` moved or someone changed it. Nothing merges the pull request or enables auto-merge.

#### The App, the key, the role and the environment

- **The App** is `infrahouse-homebrew-tap` (App ID 5944221, client ID `Iv23lilC1EyHKXYysFqn`), installed on
  `infrahouse/homebrew-tap` only, with Contents and Pull requests read and write, and Metadata read. An App token
  starts the tap's CI on the pull request; a `GITHUB_TOKEN` one wouldn't, and couldn't write to the tap anyway.
- **The key** is the KMS key `aws_kms_external_key.homebrew_tap_app` in `aws-control-493370826424` (`RSA_2048`,
  `SIGN_VERIFY`, origin `EXTERNAL`, KMS's default key policy, which delegates to IAM), with the alias
  `alias/github-app-infrahouse-homebrew-tap` and the tag `github_app = infrahouse-homebrew-tap`. `publish-homebrew`
  names it by the alias. The App's private key was imported into it by hand: the AWS provider can't import an RSA
  private key. It can't be exported, and the PEM is deleted. Whoever may call `kms:Sign` on it has the App's full
  power on the tap.
- **The role** `ih-tf-infrahouse-toolkit-homebrew`, in `aws-control-493370826424`, is the only principal with
  `kms:Sign` on the key, with `kms:SigningAlgorithm = RSASSA_PKCS1_V1_5_SHA_256`, and it has no other permission. It
  trusts GitHub's OIDC provider only for the subject
  `repo:infrahouse/infrahouse-toolkit:environment:homebrew-tap`, with `StringEquals`. It isn't the CD role
  `ROLE_ARN`: that one also publishes the candidates on the same push to `main`, and GitHub's OIDC token can't tell
  those jobs apart by branch. CloudTrail (493370826424, `us-west-1`) records every `Sign` on the key with the role.
- **The environment** `homebrew-tap`, set in `infrahouse/github-control`, allows `main` only and has no secrets or
  variables. Only `publish-homebrew` names it. A job on another branch that names it is refused by GitHub, so no pull
  request can get the subject the role trusts.
- **The token** comes from infrahouse-core's `GitHubAppTokenSource` and `KMSSigner` (`mint_token.py`), down-scoped to
  `contents: write` and `pull_requests: write`. infrahouse-core 1.4 runs in a virtualenv of its own
  (`install-venv.sh`), from `packaging/homebrew/requirements.lock`: hash-pinned, wheels only, apart from the toolkit's
  own environment, which pins an older infrahouse-core. `open-formula-pr.sh` mints the token only once there is a
  change to push, checks that `mint_token.py`'s stdout is one line, `ghs_` then token characters (`::add-mask::` masks
  one line; anything else, even a newline at the end, fails the job and isn't printed), masks it, and uses it in that
  step only: `gh` reads it from `GH_TOKEN`, and `git` through a credential helper that reads the same variable. It's
  in no URL, argument, file, step output or `$GITHUB_ENV`.
- **The token's format.** Installation tokens are opaque and about 520 characters long since GitHub's
  [stateless installation tokens](https://github.blog/changelog/2026-10-02-stateless-github-app-installation-tokens-rolled-out/)
  (rolled out April to October 2026): `ghs_<App ID>_<JWT>`, with `.` and `-` besides letters, digits and `_`. The
  check takes `^ghs_[A-Za-z0-9._-]{36,}$`: the prefix and at least a legacy token's 36 characters, with no upper
  bound, and it doesn't parse the JWT. A legacy 40-character token still passes.

`make homebrew-test` runs both scripts against a local release and tap, with `gh` and the token stubbed
(`packaging/homebrew/test.sh`); CI runs it on every pull request. `make lock` regenerates
`packaging/homebrew/requirements.lock` from its `requirements.in`, and CI fails when it would change.

#### Rotating the App's key

An App can hold several keys at once, and `publish-homebrew` signs through the alias, so a rotation changes nothing in
this repository.

1. On the App's settings page, generate a new private key.
2. In `aws-control-493370826424`, add a second `aws_kms_external_key` next to `homebrew_tap_app`
   (`aws_kms_external_key.homebrew-tap-app.tf`), with `key_spec = "RSA_2048"`, the same other arguments, and no
   `import` block. Merge it: its apply creates the key, waiting for its material.
3. Import the new App key into it and check it, with the "GitHub App key in KMS" runbook
   ([terraform-aws-actions-runner#118](https://github.com/infrahouse/terraform-aws-actions-runner/pull/118), in the
   module's README once it merges), from its import step on. Delete the PEM.
4. In `aws-control-493370826424`, point the alias and the role's grant at the new key, and delete the old key's
   resource and its `import` block (an `import` block whose resource is gone fails the plan). Merge it: its apply
   moves the alias and the grant, and schedules the old KMS key's deletion in 30 days. A release that signs during the
   apply may fail: re-run it.
5. On the App's settings page, delete the old key.

A KMS key that is lost or deleted can't be restored: generate a new App key and import it, as above.

#### When publish-homebrew fails

The run is red, and the job's `::error::` says what failed. Nothing else in the run is affected. Fix the cause, then
re-run the failed jobs: a re-run is safe, and updates the same pull request.

- **The release has no tarball or `.sha256`, or they don't match:** `publish-macos` attaches them; check its run and
  the release's assets (see "How it reaches the release" above).
- **Couldn't assume the role:** the role doesn't exist yet (merge the aws-control PR first), or the job's OIDC subject
  isn't `repo:infrahouse/infrahouse-toolkit:environment:homebrew-tap` (the environment's name in the job and in the
  role's trust must match).
- **KMS refused to sign:** the alias in `HOMEBREW_TAP_KMS_ALIAS_ARN` doesn't exist (the aws-control apply creates
  it), the role's policy doesn't name the key the alias points to, or the key is disabled or pending deletion.
- **mint_token.py printed something other than one token:** something besides `mint_token.py` writes to its stdout
  (a library's `print`, a newline after the token), or GitHub's token format moved outside the check (see "The
  token's format" above). Nothing of it is printed. Find what writes there and fix it, or widen the check and its
  tests in `test.sh`. A fix in this repository needs a new release: a re-run runs the release's own scripts.
- **GitHub refused the JWT (401):** the key in KMS is no longer one of the App's keys: rotate it, as above.
  **GitHub refused the token (422) or there's no installation:** the App lacks Contents or Pull requests write, or
  isn't installed on `infrahouse/homebrew-tap`.
- **The formula's layout or the diff:** update the formula by hand (below), and teach `open-formula-pr.sh` the new
  layout.
- **A closed pull request for the version:** if it was closed on purpose, there is nothing to do. Otherwise reopen it
  and re-run the job.
- **The push or the pull request failed:** check the App's permissions on the tap, then re-run.

The fallback is a hand edit, as before IH-190: the "Updating the Formula for a New Release" section of the tap's
`CLAUDE.md`.
