#!/usr/bin/env bash
# Runs publish-homebrew's two steps, check-release.sh then open-formula-pr.sh, as python-CD.yml runs them, against
# a local release and a local tap, with gh and the token's Python stubbed. git is the real one: the tap is a bare
# repository that the scripts clone with a file:// URL. Nothing here reaches GitHub or AWS, and nothing calls aws:
# KMS and STS are behind the token's Python, which is stubbed. python-CI.yml runs it on every pull request;
# make homebrew-test runs it locally.
#
# Each case checks the exit code, the ::notice:: or ::error:: the job shows, what reached the tap (the branch, its
# formula and author), the gh calls, whether a token was minted, and that the token appears in the output only in
# the ::add-mask:: line, which the runner consumes. The output is printed indented, so that the runner of CI doesn't
# take its ::error:: lines for its own.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(mktemp -d)"
trap 'rm -rf "${root}"' EXIT

# Shaped like an installation token.
export STUB_TOKEN="ghs_stubToken0123456789ABCDEFGHIJKLMNOPQRSTUV"
readonly APP_AUTHOR="infrahouse-homebrew-tap[bot] <361738287+infrahouse-homebrew-tap[bot]@users.noreply.github.com>"
readonly DOWNLOAD="https://github.com/infrahouse/infrahouse-toolkit/releases/download"
SED="$(command -v sed)"
readonly SED
cases=0
failed_cases=()

sha256_of() {
    if command -v sha256sum > /dev/null; then
        sha256sum "$1" | cut -d' ' -f1
    else
        shasum -a 256 "$1" | cut -d' ' -f1
    fi
}

# --- Stubs ---

mkdir -p "${root}/bin" "${root}/sabotage"

# gh, stubbed. The pull requests are in $STUB_STATE/prs.json. It refuses to run without the token in GH_TOKEN, and
# logs its arguments, so a case can check the token never was one.
cat > "${root}/bin/gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%q ' "$@" >> "${STUB_STATE}/gh.log"
echo >> "${STUB_STATE}/gh.log"
if [[ "${GH_TOKEN:-}" != "${STUB_TOKEN}" ]]; then
    echo "gh stub: GH_TOKEN isn't the token" >&2
    exit 4
fi
command="$1 $2"
shift 2
number="" head="" state="" title="" body=""
while (( $# > 0 )); do
    case "$1" in
        --repo)
            [[ "$2" == infrahouse/homebrew-tap ]] || { echo "gh stub: --repo $2" >&2; exit 2; }
            shift 2
            ;;
        --head) head="$2"; shift 2 ;;
        --state) state="$2"; shift 2 ;;
        --title) title="$2"; shift 2 ;;
        --body) body="$2"; shift 2 ;;
        --base | --limit | --json) shift 2 ;;
        -*) echo "gh stub: unexpected option $1" >&2; exit 2 ;;
        *) number="$1"; shift ;;
    esac
done
prs="${STUB_STATE}/prs.json"
case "${command}" in
    "pr list")
        jq --arg head "${head}" --arg state "${state}" \
            '[.[] | select($head == "" or .headRefName == $head)
                  | select($state == "all" or .state == ($state | ascii_upcase))]' "${prs}"
        ;;
    "pr create")
        if [[ -e "${STUB_STATE}/fail-create" ]]; then
            echo "pull request create failed: GraphQL: Resource not accessible by integration (createPullRequest)" >&2
            exit 1
        fi
        number=$(( $(jq length "${prs}") + 10 ))
        jq --argjson number "${number}" --arg head "${head}" \
            '. + [{number: $number, state: "OPEN", headRefName: $head, isCrossRepository: false}]' "${prs}" \
            > "${prs}.new"
        mv "${prs}.new" "${prs}"
        printf '%s\n' "${title}" > "${STUB_STATE}/title"
        printf '%s\n' "${body}" > "${STUB_STATE}/body"
        echo "https://github.com/infrahouse/homebrew-tap/pull/${number}"
        ;;
    "pr edit")
        printf '%s\n' "${title}" > "${STUB_STATE}/title"
        printf '%s\n' "${body}" > "${STUB_STATE}/body"
        ;;
    *)
        echo "gh stub: unexpected command ${command}" >&2
        exit 2
        ;;
esac
EOF

# The token's Python, stubbed: open-formula-pr.sh runs it as <python> -I mint_token.py.
cat > "${root}/bin/token-python" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[[ "$1" == -I && "$2" == */mint_token.py ]] || { echo "token stub: called with $*" >&2; exit 2; }
echo minted >> "${STUB_STATE}/mint.log"
if [[ -e "${STUB_STATE}/fail-mint" ]]; then
    echo "::error::KMS refused to sign the App's JWT: An error occurred (AccessDeniedException) when calling" \
        "the Sign operation." >&2
    exit 1
fi
# Something else on stdout before the token, as a library's print would put there.
if [[ -e "${STUB_STATE}/mint-chatter" ]]; then
    echo "some library chatter"
fi
printf '%s' "${STUB_TOKEN}"
EOF

# A sed that also changes another line of the formula, for the case where the edit would touch one.
cat > "${root}/sabotage/sed" <<EOF
#!/usr/bin/env bash
"${SED}" "\$@" | "${SED}" 's/^  license "Apache-2.0"\$/  license "MIT"/'
EOF
chmod +x "${root}/bin/gh" "${root}/bin/token-python" "${root}/sabotage/sed"
export PATH="${root}/bin:${PATH}"

# --- Fixtures ---

# The tap's formula as IH-189 left it, at version $1 with checksum $2. $3: "version-line" adds a version line,
# "resource" a resource block with a url and a sha256 of its own.
formula() {
    cat <<EOF
class InfrahouseToolkit < Formula
  desc "Command-line tools for InfraHouse infrastructure"
  homepage "https://github.com/infrahouse/infrahouse-toolkit"
  url "${DOWNLOAD}/v$1/infrahouse-toolkit-$1-macos-arm64.tar.gz"
  sha256 "$2"
EOF
    if [[ "${3:-}" == version-line ]]; then
        echo "  version \"$1\""
    fi
    cat <<'EOF'
  license "Apache-2.0"

  depends_on arch: :arm64
  depends_on :macos
EOF
    if [[ "${3:-}" == resource ]]; then
        cat <<'EOF'

  resource "extra" do
    url "https://example.com/extra-1.0.tar.gz"
    sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  end
EOF
    fi
    cat <<'EOF'

  def install
    libexec.install Dir["*"]
    Dir[libexec/"bin/ih-*"].each { |script| bin.install_symlink script }
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/ih-ec2 --version")
    system libexec/"bin/python3", "-I", "-c",
           "import nacl.bindings, cryptography.hazmat.bindings._rust, infrahouse_toolkit, " \
           "infrahouse_toolkit.cli.ih_registry.cmd_upload"
  end
end
EOF
}

# A bare repository with the formula on main, as formula "$@" writes it. Sets TAP to its directory.
make_tap() {
    TAP="${case_dir}/tap.git"
    local work="${case_dir}/tap-work"
    git init --quiet --bare --initial-branch=main "${TAP}"
    git init --quiet --initial-branch=main "${work}"
    mkdir -p "${work}/Formula"
    formula "$@" > "${work}/Formula/infrahouse-toolkit.rb"
    echo "# InfraHouse Homebrew Tap" > "${work}/README.md"
    git -C "${work}" add --all
    git -C "${work}" -c user.name=Aleks -c user.email=aleks@example.com commit --quiet -m "The formula at $1"
    git -C "${work}" push --quiet "${TAP}" main
}

# Another commit on the tap's main, as a merge of another pull request would make.
move_tap_main() {
    local work="${case_dir}/tap-work"
    echo "More docs." >> "${work}/README.md"
    git -C "${work}" -c user.name=Aleks -c user.email=aleks@example.com commit --quiet --all -m "Docs"
    git -C "${work}" push --quiet "${TAP}" main
}

# The release v$1's assets, under $case_dir/release. $2: "missing-tarball", "bad-sha256" or "two-lines".
make_release() {
    local tarball="infrahouse-toolkit-$1-macos-arm64.tar.gz"
    local dir="${case_dir}/release/v$1"
    mkdir -p "${dir}"
    printf 'The tarball of %s\n' "$1" > "${dir}/${tarball}"
    echo "$(sha256_of "${dir}/${tarball}")  ${tarball}" > "${dir}/${tarball}.sha256"
    case "${2:-}" in
        missing-tarball) rm "${dir}/${tarball}" ;;
        bad-sha256) echo "$(printf '1%.0s' {1..64})  ${tarball}" > "${dir}/${tarball}.sha256" ;;
        two-lines) echo "$(sha256_of "${dir}/${tarball}")  other.tar.gz" >> "${dir}/${tarball}.sha256" ;;
    esac
}

release_sha256() {
    sha256_of "${case_dir}/release/v$1/infrahouse-toolkit-$1-macos-arm64.tar.gz"
}

# --- Running the job's two steps ---

# publish <version> [<PATH prefix>]: check-release.sh, then open-formula-pr.sh if it passed, as the job runs them.
# The output goes to $case_dir/output, the exit code to $status.
publish() {
    local output="${case_dir}/github_output"
    : > "${output}"
    status=0
    {
        VERSION="$1" RELEASE_DOWNLOAD_BASE="file://${case_dir}/release" GITHUB_OUTPUT="${output}" \
            "${here}/check-release.sh" \
        && VERSION="$1" TARBALL_SHA256="$("${SED}" -n 's/^sha256=//p' "${output}")" \
            TAP_GIT_URL="file://${TAP}" HOMEBREW_TOKEN_PYTHON="${root}/bin/token-python" \
            HOMEBREW_TAP_APP_ID=5944221 \
            HOMEBREW_TAP_KMS_KEY_ARN="arn:aws:kms:us-west-1:493370826424:key/ed26150d-e589-4cd1-8d4d-26ec30f0c709" \
            GITHUB_SERVER_URL=https://github.com GITHUB_REPOSITORY=infrahouse/infrahouse-toolkit \
            GITHUB_RUN_ID=1234 GITHUB_RUN_ATTEMPT=1 GITHUB_STEP_SUMMARY="${case_dir}/summary" \
            PATH="${2:+$2:}${PATH}" \
            "${here}/open-formula-pr.sh"
    } >> "${case_dir}/output" 2>&1 || status=$?
}

# --- Checks ---

fail() {
    echo "    FAIL: $*"
    case_failed=1
}

expect_status() {
    [[ "${status}" == "$1" ]] || fail "exit code ${status}, expected $1"
}

expect_output() {
    grep -qF -- "$1" "${case_dir}/output" || fail "no '$1' in the output"
}

# The token appears only in ::add-mask:: lines, and in exactly $1 of them.
expect_token_masked() {
    local masks leaks
    masks="$(grep -cxF "::add-mask::${STUB_TOKEN}" "${case_dir}/output" || true)"
    leaks="$(grep -F "${STUB_TOKEN}" "${case_dir}/output" | grep -vxF "::add-mask::${STUB_TOKEN}" || true)"
    [[ "${masks}" == "$1" ]] || fail "${masks} ::add-mask:: lines for the token, expected $1"
    [[ -z "${leaks}" ]] || fail "the token is in the output outside ::add-mask::: ${leaks}"
    if [[ -e "${STUB_STATE}/gh.log" ]] && grep -qF "${STUB_TOKEN}" "${STUB_STATE}/gh.log"; then
        fail "the token was an argument of gh"
    fi
}

expect_minted() {
    local count=0
    [[ ! -e "${STUB_STATE}/mint.log" ]] || count="$(wc -l < "${STUB_STATE}/mint.log" | tr -d ' ')"
    [[ "${count}" == "$1" ]] || fail "minted ${count} tokens, expected $1"
}

# expect_gh <count> <command>: how many times gh ran <command> ("pr create", "pr edit", "pr list" or "" for any).
expect_gh() {
    local count=0
    [[ ! -e "${STUB_STATE}/gh.log" ]] || count="$(grep -c "^${2}" "${STUB_STATE}/gh.log" || true)"
    [[ "${count}" == "$1" ]] || fail "gh ran '${2:-anything}' ${count} times, expected $1"
}

expect_no_branch() {
    if git --git-dir="${TAP}" rev-parse --verify --quiet "refs/heads/$1" > /dev/null; then
        fail "the tap has a branch $1"
    fi
}

# expect_branch <version> <sha256> [<formula variant>]: toolkit-<version> is the tap's main plus one commit by the
# App, whose formula is the one at <version> and <sha256>.
expect_branch() {
    local branch="toolkit-$1"
    if ! git --git-dir="${TAP}" rev-parse --verify --quiet "refs/heads/${branch}" > /dev/null; then
        fail "the tap has no branch ${branch}"
        return
    fi
    [[ "$(git --git-dir="${TAP}" rev-parse "${branch}^")" == "$(git --git-dir="${TAP}" rev-parse main)" ]] \
        || fail "${branch} isn't one commit on top of main"
    [[ "$(git --git-dir="${TAP}" log -1 --format='%an <%ae>' "${branch}")" == "${APP_AUTHOR}" ]] \
        || fail "${branch}'s author is $(git --git-dir="${TAP}" log -1 --format='%an <%ae>' "${branch}")"
    [[ "$(git --git-dir="${TAP}" log -1 --format='%cn <%ce>' "${branch}")" == "${APP_AUTHOR}" ]] \
        || fail "${branch}'s committer isn't the App"
    local on_branch
    on_branch="$(git --git-dir="${TAP}" show "${branch}:Formula/infrahouse-toolkit.rb")"
    [[ "${on_branch}" == "$(formula "$1" "$2" "${3:-}")" ]] \
        || fail "${branch}'s formula isn't the one at $1 and $2"
    local numstat lines=2
    [[ "${3:-}" != version-line ]] || lines=3
    numstat="$(git --git-dir="${TAP}" diff --numstat main "${branch}")"
    [[ "${numstat}" == "${lines}"$'\t'"${lines}"$'\t'"Formula/infrahouse-toolkit.rb" ]] \
        || fail "${branch} doesn't change exactly ${lines} lines of the formula: ${numstat}"
}

# --- Cases ---

# run_case <name> <description>: runs the function case_<name> in a directory of its own, then prints its output.
run_case() {
    case_dir="${root}/cases/$1"
    STUB_STATE="${case_dir}/state"
    export STUB_STATE
    mkdir -p "${STUB_STATE}"
    echo "[]" > "${STUB_STATE}/prs.json"
    : > "${case_dir}/output"
    case_failed=0
    cases=$((cases + 1))
    "case_$1"
    if (( case_failed )); then
        failed_cases+=("$1")
        echo "FAIL $1: $2"
    else
        echo "PASS $1: $2"
    fi
    "${SED}" 's/^/    | /' "${case_dir}/output"
}

old_sha256="dba5904b612e420cb6472fd8f10bb4c3c43f0a7581946d9cbd2bc2949621e0e9"

case_new_version() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    publish 2.68.2
    expect_status 0
    expect_output "::notice::Opened https://github.com/infrahouse/homebrew-tap/pull/10: infrahouse-toolkit 2.68.2"
    expect_branch 2.68.2 "$(release_sha256 2.68.2)"
    expect_minted 1
    expect_gh 1 "pr create"
    expect_token_masked 1
    grep -qxF "infrahouse-toolkit 2.68.2" "${STUB_STATE}/title" || fail "the title isn't 'infrahouse-toolkit 2.68.2'"
    grep -qF "/releases/tag/v2.68.2" "${STUB_STATE}/body" || fail "the body doesn't link the release"
    grep -qF "/actions/runs/1234/attempts/1" "${STUB_STATE}/body" || fail "the body doesn't link the CD run"
}

case_version_line() {
    make_tap 2.68.1 "${old_sha256}" version-line
    make_release 2.68.2
    publish 2.68.2
    expect_status 0
    expect_branch 2.68.2 "$(release_sha256 2.68.2)" version-line
    expect_gh 1 "pr create"
    expect_token_masked 1
}

case_already_at_version() {
    make_release 2.68.2
    make_tap 2.68.2 "$(release_sha256 2.68.2)"
    publish 2.68.2
    expect_status 0
    expect_output "::notice::The formula is already at 2.68.2, with the release's sha256. Nothing to do."
    expect_no_branch toolkit-2.68.2
    expect_minted 0
    expect_gh 0 ""
}

case_at_version_other_sha256() {
    make_release 2.68.2
    make_tap 2.68.2 "${old_sha256}"
    publish 2.68.2
    expect_status 1
    expect_output "::error::Formula/infrahouse-toolkit.rb is already at 2.68.2, but its sha256 is ${old_sha256}"
    expect_minted 0
    expect_gh 0 ""
}

case_formula_ahead() {
    make_tap 2.69.0 "${old_sha256}"
    make_release 2.68.2
    publish 2.68.2
    expect_status 0
    expect_output "::notice::The formula is at 2.69.0, newer than 2.68.2."
    expect_no_branch toolkit-2.68.2
    expect_minted 0
    expect_gh 0 ""
}

case_newer_pr_open() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    echo '[{"number": 7, "state": "OPEN", "headRefName": "toolkit-2.69.0", "isCrossRepository": false}]' \
        > "${STUB_STATE}/prs.json"
    publish 2.68.2
    expect_status 0
    expect_output "::notice::infrahouse/homebrew-tap has an open pull request for a newer release (toolkit-2.69.0)"
    expect_no_branch toolkit-2.68.2
    expect_gh 0 "pr create"
    expect_token_masked 1
}

case_rerun_branch_and_pr_exist() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    publish 2.68.2
    local first
    first="$(git --git-dir="${TAP}" rev-parse toolkit-2.68.2)"
    echo "--- the re-run ---" >> "${case_dir}/output"
    publish 2.68.2
    expect_status 0
    expect_output "The branch toolkit-2.68.2 is already main with this change: nothing to push"
    expect_output "::notice::Updated https://github.com/infrahouse/homebrew-tap/pull/10: infrahouse-toolkit 2.68.2"
    [[ "$(git --git-dir="${TAP}" rev-parse toolkit-2.68.2)" == "${first}" ]] || fail "the re-run moved the branch"
    expect_branch 2.68.2 "$(release_sha256 2.68.2)"
    expect_gh 1 "pr create"
    expect_gh 1 "pr edit"
    [[ "$(jq length "${STUB_STATE}/prs.json")" == 1 ]] || fail "there is more than one pull request"
    expect_token_masked 2
}

case_rerun_after_main_moved() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    publish 2.68.2
    move_tap_main
    echo "--- the re-run, after another merge to the tap's main ---" >> "${case_dir}/output"
    publish 2.68.2
    expect_status 0
    expect_output "The branch toolkit-2.68.2 isn't main with this change: resetting it to that"
    expect_output "::notice::Updated https://github.com/infrahouse/homebrew-tap/pull/10"
    expect_branch 2.68.2 "$(release_sha256 2.68.2)"
    expect_gh 1 "pr create"
    expect_gh 1 "pr edit"
    expect_token_masked 2
}

case_branch_without_pr() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    touch "${STUB_STATE}/fail-create"
    publish 2.68.2
    rm "${STUB_STATE}/fail-create"
    echo "--- the re-run, with the branch pushed and no pull request ---" >> "${case_dir}/output"
    publish 2.68.2
    expect_status 0
    expect_output "The branch toolkit-2.68.2 is already main with this change: nothing to push"
    expect_output "::notice::Opened https://github.com/infrahouse/homebrew-tap/pull/10"
    expect_branch 2.68.2 "$(release_sha256 2.68.2)"
    expect_gh 2 "pr create"
    expect_token_masked 2
}

case_closed_pr() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    echo '[{"number": 9, "state": "CLOSED", "headRefName": "toolkit-2.68.2", "isCrossRepository": false}]' \
        > "${STUB_STATE}/prs.json"
    publish 2.68.2
    expect_status 1
    expect_output "::error::Pull request #9 (toolkit-2.68.2) was closed without merging. Nothing was pushed."
    expect_no_branch toolkit-2.68.2
    expect_gh 0 "pr create"
    expect_token_masked 1
}

case_tarball_missing() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2 missing-tarball
    publish 2.68.2
    expect_status 1
    expect_output "::error::Release v2.68.2 has no infrahouse-toolkit-2.68.2-macos-arm64.tar.gz at file://"
    expect_no_branch toolkit-2.68.2
    expect_minted 0
    expect_gh 0 ""
}

case_bad_sha256() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2 bad-sha256
    publish 2.68.2
    expect_status 1
    expect_output "::error::The release's infrahouse-toolkit-2.68.2-macos-arm64.tar.gz has sha256 "
    expect_no_branch toolkit-2.68.2
    expect_minted 0
    expect_gh 0 ""
}

case_malformed_sha256() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2 two-lines
    publish 2.68.2
    expect_status 1
    expect_output "::error::The release's infrahouse-toolkit-2.68.2-macos-arm64.tar.gz.sha256 isn't one line"
    expect_minted 0
}

case_diff_touches_another_line() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    publish 2.68.2 "${root}/sabotage"
    expect_status 1
    expect_output "::error::The change to Formula/infrahouse-toolkit.rb isn't exactly its url, sha256 and version lines"
    expect_output '+  license "MIT"'
    expect_no_branch toolkit-2.68.2
    expect_minted 0
    expect_gh 0 ""
}

case_formula_layout_changed() {
    make_tap 2.68.1 "${old_sha256}" resource
    make_release 2.68.2
    publish 2.68.2
    expect_status 1
    expect_output "::error::Formula/infrahouse-toolkit.rb has 2 'url' lines"
    expect_no_branch toolkit-2.68.2
    expect_minted 0
}

case_mint_fails() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    touch "${STUB_STATE}/fail-mint"
    publish 2.68.2
    expect_status 1
    expect_output "::error::KMS refused to sign the App's JWT"
    expect_output "::error::Couldn't mint a token for infrahouse/homebrew-tap (the error above says why)."
    expect_no_branch toolkit-2.68.2
    expect_minted 1
    expect_gh 0 ""
    expect_token_masked 0
}

case_mint_prints_more() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    touch "${STUB_STATE}/mint-chatter"
    publish 2.68.2
    expect_status 1
    expect_output "::error::mint_token.py printed something other than one token on stdout. Nothing of it is printed"
    expect_no_branch toolkit-2.68.2
    expect_minted 1
    expect_gh 0 ""
    # Not masked, because not printed: the token is nowhere in the output.
    expect_token_masked 0
}

case_older_pr_open() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.3
    echo '[{"number": 7, "state": "OPEN", "headRefName": "toolkit-2.68.2", "isCrossRepository": false}]' \
        > "${STUB_STATE}/prs.json"
    publish 2.68.3
    expect_status 0
    expect_output "::notice::Opened https://github.com/infrahouse/homebrew-tap/pull/11: infrahouse-toolkit 2.68.3"
    expect_output "::notice::infrahouse/homebrew-tap still has open pull requests for older releases (toolkit-2.68.2)."
    expect_branch 2.68.3 "$(release_sha256 2.68.3)"
    expect_gh 1 "pr create"
    expect_token_masked 1
}

case_push_fails() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    printf '#!/bin/sh\necho "refused by the test"\nexit 1\n' > "${TAP}/hooks/pre-receive"
    chmod +x "${TAP}/hooks/pre-receive"
    publish 2.68.2
    expect_status 1
    expect_output "::error::Couldn't push toolkit-2.68.2 to infrahouse/homebrew-tap"
    expect_no_branch toolkit-2.68.2
    expect_gh 0 "pr create"
    expect_token_masked 1
}

case_pr_create_fails() {
    make_tap 2.68.1 "${old_sha256}"
    make_release 2.68.2
    touch "${STUB_STATE}/fail-create"
    publish 2.68.2
    expect_status 1
    expect_output "::error::Couldn't open the pull request for toolkit-2.68.2 in infrahouse/homebrew-tap"
    expect_branch 2.68.2 "$(release_sha256 2.68.2)"
    expect_token_masked 1
}

# git asks open-formula-pr.sh's credential helper for github.com's password: it answers with GH_TOKEN.
case_credential_helper() {
    local helper answer
    helper="$("${SED}" -n "s/^    local helper='\(.*\)'$/\1/p" "${here}/open-formula-pr.sh")"
    [[ -n "${helper}" ]] || fail "no credential helper in open-formula-pr.sh"
    answer="$(printf 'protocol=https\nhost=github.com\n\n' \
        | GH_TOKEN="${STUB_TOKEN}" git -c credential.helper= -c "credential.helper=${helper}" credential fill)"
    grep -qxF "username=x-access-token" <<< "${answer}" || fail "the helper's username isn't x-access-token"
    grep -qxF "password=${STUB_TOKEN}" <<< "${answer}" || fail "the helper's password isn't GH_TOKEN"
    echo "git credential fill: username=x-access-token, password=GH_TOKEN" >> "${case_dir}/output"
}

run_case new_version "a new version: branch, commit by the App, pull request"
run_case version_line "a formula with a version line: url, sha256 and version change"
run_case already_at_version "the formula already at the version: a notice, no token"
run_case at_version_other_sha256 "the formula at the version with another sha256: red"
run_case formula_ahead "the formula ahead (a re-run of an older release): a notice, no token"
run_case newer_pr_open "a newer release's pull request open: a notice, no pull request"
run_case older_pr_open "an older release's pull request open: this one opened, a notice to close the older one"
run_case rerun_branch_and_pr_exist "a re-run, branch and pull request there: the pull request updated, no second"
run_case rerun_after_main_moved "a re-run after the tap's main moved: the branch reset, the pull request updated"
run_case branch_without_pr "a re-run after the pull request failed: the branch kept, the pull request opened"
run_case closed_pr "a closed pull request for the version: red, nothing pushed"
run_case tarball_missing "the tarball missing from the release: red, no token"
run_case bad_sha256 "a .sha256 that doesn't match the tarball: red, no token"
run_case malformed_sha256 "a .sha256 that isn't one line for the tarball: red, no token"
run_case diff_touches_another_line "an edit that touches another line: red, nothing pushed, no token"
run_case formula_layout_changed "a formula with a second url (a resource block): red, no token"
run_case mint_fails "the token mint failing: red, nothing pushed"
run_case mint_prints_more "the mint printing a line before the token: red, the token printed nowhere"
run_case push_fails "the push refused: red, no pull request"
run_case pr_create_fails "the pull request refused: red"
run_case credential_helper "git's credential helper answers with GH_TOKEN"

echo
if (( ${#failed_cases[@]} > 0 )); then
    echo "${#failed_cases[@]} of ${cases} cases failed: ${failed_cases[*]}"
    exit 1
fi
echo "All ${cases} cases passed"
