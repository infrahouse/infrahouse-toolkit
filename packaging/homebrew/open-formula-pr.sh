#!/usr/bin/env bash
# Opens, or updates, the pull request in infrahouse/homebrew-tap that moves Formula/infrahouse-toolkit.rb to the
# release v$VERSION. publish-homebrew (python-CD.yml) runs it after check-release.sh, and after it assumed the role
# that may sign as the GitHub App infrahouse-homebrew-tap.
#
# 1. Clones the tap, which is public, and reads the formula's version from its url. If the formula already has
#    this version, or a newer one, it stops with a notice and exit 0, before it mints a token.
# 2. Changes url and sha256 (and version, if the formula has that line) and checks the diff: exactly those lines,
#    and the new url is the release's.
# 3. Mints the App's token (mint_token.py) and masks it at once. The token stays in this process and its
#    children: in GH_TOKEN for gh, and git reads it from there through a credential helper. It's in no URL, file,
#    argument, step output or $GITHUB_ENV.
# 4. Pushes the branch toolkit-$VERSION, authored by the App, and opens the pull request, or updates the one that
#    is open. It never merges it and never enables auto-merge: Aleks merges it.
#
# Every failure is an ::error:: that says what to do, and exit 1.
#
# Environment:
# - VERSION: the release, X.Y.Z.
# - TARBALL_SHA256: the release's checksum, from check-release.sh.
# - HOMEBREW_TOKEN_PYTHON: the Python of the virtualenv with infrahouse-core 1.4 (install-venv.sh).
# - HOMEBREW_TAP_APP_ID and HOMEBREW_TAP_KMS_ALIAS_ARN: for mint_token.py.
# - GITHUB_SERVER_URL, GITHUB_REPOSITORY, GITHUB_RUN_ID, GITHUB_RUN_ATTEMPT: the run's link in the pull request.
# - GITHUB_STEP_SUMMARY (optional).
# - TAP_GIT_URL replaces https://github.com/infrahouse/homebrew-tap.git for the tests (test.sh) only.
#
# See the "How a release reaches the Homebrew formula" section of packaging/README.md.
set -euo pipefail
# Never trace: the token is in a variable below, and xtrace would print it before it's masked.
set +x

readonly TAP_REPO="infrahouse/homebrew-tap"
readonly TAP_GIT_URL="${TAP_GIT_URL:-https://github.com/${TAP_REPO}.git}"
readonly FORMULA="Formula/infrahouse-toolkit.rb"
# The App's bot user (GET /users/infrahouse-homebrew-tap[bot]). GitHub links a commit to it by this address.
readonly APP_NAME="infrahouse-homebrew-tap[bot]"
readonly APP_EMAIL="361738287+infrahouse-homebrew-tap[bot]@users.noreply.github.com"
readonly VERSION_PATTERN='[0-9]+\.[0-9]+\.[0-9]+'

export GH_PROMPT_DISABLED=1 GH_NO_UPDATE_NOTIFIER=1 GIT_TERMINAL_PROMPT=0

die() {
    echo "::error::$*"
    exit 1
}

# The url the formula gets for version $1. users download it; check-release.sh checked it.
formula_url() {
    local download="https://github.com/infrahouse/infrahouse-toolkit/releases/download"
    echo "${download}/v$1/infrahouse-toolkit-$1-macos-arm64.tar.gz"
}

# Prints -1, 0 or 1 as the X.Y.Z version $1 is lower than, equal to or higher than $2.
compare_versions() {
    local -a a b
    local i
    IFS=. read -ra a <<< "$1"
    IFS=. read -ra b <<< "$2"
    for i in 0 1 2; do
        if (( 10#${a[i]} < 10#${b[i]} )); then
            echo -1
            return
        fi
        if (( 10#${a[i]} > 10#${b[i]} )); then
            echo 1
            return
        fi
    done
    echo 0
}

# git in the tap's clone, with the token for github.com. The helper reads GH_TOKEN from the environment when git
# asks for a password; the empty helper first drops any other one.
git_tap() {
    # The single quotes are deliberate: the helper's shell expands $1 and ${GH_TOKEN}, not this one.
    # shellcheck disable=SC2016
    local helper='!f() { test "$1" = get || exit 0; echo username=x-access-token; echo "password=${GH_TOKEN}"; }; f'
    git -C "${tap}" -c credential.helper= -c "credential.helper=${helper}" "$@"
}

: "${VERSION:?VERSION is the release, X.Y.Z}"
: "${TARBALL_SHA256:?TARBALL_SHA256 is the release tarball checksum, from check-release.sh}"
if [[ ! "${VERSION}" =~ ^${VERSION_PATTERN}$ ]]; then
    die "VERSION is '${VERSION}', not X.Y.Z"
fi
if [[ ! "${TARBALL_SHA256}" =~ ^[0-9a-f]{64}$ ]]; then
    die "TARBALL_SHA256 is '${TARBALL_SHA256}', not a sha256"
fi
for tool in git gh jq sed awk; do
    command -v "${tool}" > /dev/null || die "${tool} isn't installed"
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
branch="toolkit-${VERSION}"
new_url="$(formula_url "${VERSION}")"
release_url="https://github.com/infrahouse/infrahouse-toolkit/releases/tag/v${VERSION}"
run_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}/attempts/${GITHUB_RUN_ATTEMPT}"
work="$(mktemp -d)"
trap 'rm -rf "${work}"' EXIT
tap="${work}/tap"

# 1. The formula on the tap's main, and its version.
if ! git clone --quiet --no-tags --branch main "${TAP_GIT_URL}" "${tap}"; then
    die "Couldn't clone ${TAP_GIT_URL} (the error above says why). Re-run publish-homebrew."
fi
file="${tap}/${FORMULA}"
[[ -f "${file}" ]] || die "${TAP_REPO} has no ${FORMULA} on main"

# The edit below changes exactly one url line and one sha256 line, and the version line if there is one. A formula
# with others (mirror, resource, bottle or on_arm blocks) needs a hand edit and a change here.
layout_error="Update the formula by hand (infrahouse/homebrew-tap's CLAUDE.md), and teach open-formula-pr.sh"
layout_error+=" the new layout."
for key in url sha256 version mirror; do
    count="$(grep -cE "^[[:space:]]*${key}[[:space:]]" "${file}" || true)"
    case "${key}:${count}" in
        url:1 | sha256:1 | version:0 | version:1 | mirror:0) ;;
        *)
            die "${FORMULA} has ${count} '${key}' lines; open-formula-pr.sh expects one url, one sha256, at most" \
                "one version and no mirror. ${layout_error}"
            ;;
    esac
done

download_pattern="https://github\\.com/infrahouse/infrahouse-toolkit/releases/download"
tarball_pattern="infrahouse-toolkit-(${VERSION_PATTERN})-macos-arm64\\.tar\\.gz"
url_line_pattern="^  url \"${download_pattern}/v(${VERSION_PATTERN})/${tarball_pattern}\"$"
sha256_line_pattern='^  sha256 "([0-9a-f]{64})"$'
version_line_pattern="^  version \"(${VERSION_PATTERN})\"$"

url_line="$(grep -E '^[[:space:]]*url[[:space:]]' "${file}")"
if [[ ! "${url_line}" =~ ${url_line_pattern} || "${BASH_REMATCH[1]}" != "${BASH_REMATCH[2]}" ]]; then
    die "${FORMULA}'s url isn't a toolkit release's macOS tarball: ${url_line}. ${layout_error}"
fi
old_version="${BASH_REMATCH[1]}"
old_url="$(formula_url "${old_version}")"

sha256_line="$(grep -E '^[[:space:]]*sha256[[:space:]]' "${file}")"
if [[ ! "${sha256_line}" =~ ${sha256_line_pattern} ]]; then
    die "${FORMULA}'s sha256 line isn't '  sha256 \"<sha256>\"': ${sha256_line}. ${layout_error}"
fi
old_sha256="${BASH_REMATCH[1]}"

version_line="$(grep -E '^[[:space:]]*version[[:space:]]' "${file}" || true)"
if [[ -n "${version_line}" ]]; then
    if [[ ! "${version_line}" =~ ${version_line_pattern} || "${BASH_REMATCH[1]}" != "${old_version}" ]]; then
        die "${FORMULA}'s version line doesn't match its url's version ${old_version}: ${version_line}. ${layout_error}"
    fi
fi

echo "The formula on ${TAP_REPO}'s main is at ${old_version}; the release is ${VERSION}"
case "$(compare_versions "${old_version}" "${VERSION}")" in
    0)
        if [[ "${old_sha256}" != "${TARBALL_SHA256}" ]]; then
            die "${FORMULA} is already at ${VERSION}, but its sha256 is ${old_sha256}, not the release's" \
                "${TARBALL_SHA256}: it won't install. Fix it by hand (infrahouse/homebrew-tap's CLAUDE.md)."
        fi
        echo "::notice::The formula is already at ${VERSION}, with the release's sha256. Nothing to do."
        exit 0
        ;;
    1)
        echo "::notice::The formula is at ${old_version}, newer than ${VERSION}. A formula only moves forward:" \
            "nothing to do."
        exit 0
        ;;
esac

# 2. The change, and the check that it's exactly the change.
sed -E \
    -e "s|^  url \"[^\"]*\"\$|  url \"${new_url}\"|" \
    -e "s|^  sha256 \"[0-9a-f]{64}\"\$|  sha256 \"${TARBALL_SHA256}\"|" \
    -e "s|^  version \"[^\"]*\"\$|  version \"${VERSION}\"|" \
    "${file}" > "${work}/formula.rb"
cat "${work}/formula.rb" > "${file}"

expected_removed=("  url \"${old_url}\"" "  sha256 \"${old_sha256}\"")
expected_added=("  url \"${new_url}\"" "  sha256 \"${TARBALL_SHA256}\"")
if [[ -n "${version_line}" ]]; then
    expected_removed+=("  version \"${old_version}\"")
    expected_added+=("  version \"${VERSION}\"")
fi
diff_text="$(git -C "${tap}" diff --no-color --no-ext-diff -U0)"
changed="$(git -C "${tap}" status --porcelain)"
removed="$(awk '/^@@/ { hunk = 1; next } hunk && /^-/ { print substr($0, 2) }' <<< "${diff_text}" | sort)"
added="$(awk '/^@@/ { hunk = 1; next } hunk && /^\+/ { print substr($0, 2) }' <<< "${diff_text}" | sort)"
if [[ "${changed}" != " M ${FORMULA}" \
      || "${removed}" != "$(printf '%s\n' "${expected_removed[@]}" | sort)" \
      || "${added}" != "$(printf '%s\n' "${expected_added[@]}" | sort)" ]]; then
    echo "::error::The change to ${FORMULA} isn't exactly its url, sha256 and version lines, to" \
        "${new_url} and ${TARBALL_SHA256}. Nothing was pushed. ${layout_error} The change was:"
    echo "${changed}"
    echo "${diff_text}"
    exit 1
fi
echo "The change to ${FORMULA}:"
echo "${diff_text}"

git -C "${tap}" checkout --quiet -B "${branch}"
git -C "${tap}" -c user.name="${APP_NAME}" -c user.email="${APP_EMAIL}" commit --quiet \
    -m "infrahouse-toolkit ${VERSION}" \
    -m "The url and sha256 of the release's macOS tarball: ${release_url}" \
    -m "Opened by publish-homebrew: ${run_url}" \
    -- "${FORMULA}"

# 3. The token: only now that there is something to push.
if [[ ! -x "${HOMEBREW_TOKEN_PYTHON:-}" ]]; then
    die "HOMEBREW_TOKEN_PYTHON is '${HOMEBREW_TOKEN_PYTHON:-}', not a Python. publish-homebrew sets it to the" \
        "virtualenv that install-venv.sh makes."
fi
# The "." is stripped below. It keeps a newline at the end of the output, which $(...) alone would drop, for the
# check to see.
if ! token="$("${HOMEBREW_TOKEN_PYTHON}" -I "${script_dir}/mint_token.py" && echo .)"; then
    unset token
    die "Couldn't mint a token for ${TAP_REPO} (the error above says why). Nothing was pushed. Fix it, then re-run" \
        "publish-homebrew."
fi
token="${token%.}"
# Checked before it's masked: ::add-mask:: masks one line, and the runner would print any other line of the value.
# An installation token starts with ghs_. Since GitHub's stateless tokens (2026) it is ghs_<App ID>_<JWT>, about
# 520 characters, opaque, with '.' and '-' from the JWT; a legacy one is ghs_ and 36 characters. So the pattern takes
# ghs_ and at least 36 token characters, with no upper bound, and doesn't parse the JWT. Under bash's =~ (POSIX ERE)
# '.' and '-' are literal in the bracket ('-' because it's last), the bracket has no whitespace, and ^ and $ are the
# ends of the whole value, not of a line. So a second line, a newline at the end, a space, empty output and anything
# before or after the token fail: the value masked is one line, or nothing of it is printed at all.
token_pattern='^ghs_[A-Za-z0-9._-]{36,}$'
if [[ ! "${token}" =~ ${token_pattern} ]]; then
    unset token
    die "mint_token.py printed something other than one token on stdout: expected one line, ghs_ then 36 or more" \
        "letters, digits, '.', '_' or '-', with no newline. Nothing of it is printed, and nothing was pushed. Find" \
        "what writes to its stdout (mint_token.py prints only the token), or whether GitHub's token format changed" \
        "(\"The token's format\" in packaging/README.md). A fix needs a new release: a re-run runs this release's" \
        "scripts."
fi
echo "::add-mask::${token}"
export GH_TOKEN="${token}"
unset token

# 4. The branch and the pull request.
if ! open_prs="$(gh pr list --repo "${TAP_REPO}" --state open --limit 100 \
        --json number,headRefName,isCrossRepository)"; then
    die "Couldn't list ${TAP_REPO}'s pull requests (the error above says why). Re-run publish-homebrew."
fi
if ! pr_versions="$(jq -r '.[] | select(.isCrossRepository | not) | .headRefName
        | select(test("^toolkit-[0-9]+\\.[0-9]+\\.[0-9]+$")) | ltrimstr("toolkit-")' <<< "${open_prs}")"; then
    die "gh pr list printed something that isn't a list of pull requests. Re-run publish-homebrew."
fi
newer_prs=()
older_prs=()
while read -r pr_version; do
    [[ -n "${pr_version}" ]] || continue
    case "$(compare_versions "${pr_version}" "${VERSION}")" in
        1) newer_prs+=("toolkit-${pr_version}") ;;
        -1) older_prs+=("toolkit-${pr_version}") ;;
    esac
done <<< "${pr_versions}"
if (( ${#newer_prs[@]} > 0 )); then
    echo "::notice::${TAP_REPO} has an open pull request for a newer release (${newer_prs[*]}). A formula only" \
        "moves forward: nothing to do for ${VERSION}."
    exit 0
fi

if ! branch_prs="$(gh pr list --repo "${TAP_REPO}" --head "${branch}" --state all --limit 100 \
        --json number,state,isCrossRepository)"; then
    die "Couldn't list ${TAP_REPO}'s pull requests for ${branch} (the error above says why). Re-run publish-homebrew."
fi
pr_number() {
    jq -r --arg state "$1" '[.[] | select(.isCrossRepository | not) | select(.state == $state)][0].number // empty' \
        <<< "${branch_prs}"
}
open_pr="$(pr_number OPEN)"
merged_pr="$(pr_number MERGED)"
closed_pr="$(pr_number CLOSED)"
if [[ -z "${open_pr}" && -n "${merged_pr}" ]]; then
    die "Pull request #${merged_pr} (${branch}) was merged, but ${FORMULA} on main is at ${old_version}." \
        "Check the tap's history, then fix the formula by hand (infrahouse/homebrew-tap's CLAUDE.md)."
fi
if [[ -z "${open_pr}" && -n "${closed_pr}" ]]; then
    die "Pull request #${closed_pr} (${branch}) was closed without merging. Nothing was pushed. If that was" \
        "deliberate, there's nothing to do. Otherwise reopen it and re-run publish-homebrew, which updates it."
fi

if ! remote_branch="$(git_tap ls-remote --heads origin "refs/heads/${branch}")"; then
    die "Couldn't read ${TAP_REPO}'s branches (the error above says why). Re-run publish-homebrew."
fi
remote_sha="$(cut -f1 <<< "${remote_branch}")"
push_args=()
if [[ -z "${remote_sha}" ]]; then
    echo "Pushing the new branch ${branch}"
    push_args=("HEAD:refs/heads/${branch}")
else
    if ! git_tap fetch --quiet --no-tags origin "refs/heads/${branch}"; then
        die "Couldn't fetch ${branch} from ${TAP_REPO} (the error above says why). Re-run publish-homebrew."
    fi
    # The branch is right when it is main plus this one change. Otherwise, a re-run after main moved, or a branch
    # someone changed, it is reset to that. The lease refuses the push if the branch moved since it was read.
    if [[ "$(git -C "${tap}" rev-parse 'FETCH_HEAD^{tree}')" == "$(git -C "${tap}" rev-parse 'HEAD^{tree}')" \
          && "$(git -C "${tap}" rev-parse 'FETCH_HEAD^')" == "$(git -C "${tap}" rev-parse 'HEAD^')" ]]; then
        echo "The branch ${branch} is already main with this change: nothing to push"
    else
        echo "The branch ${branch} isn't main with this change: resetting it to that"
        push_args=("--force-with-lease=refs/heads/${branch}:${remote_sha}" "HEAD:refs/heads/${branch}")
    fi
fi
if (( ${#push_args[@]} > 0 )) && ! git_tap push --quiet origin "${push_args[@]}"; then
    die "Couldn't push ${branch} to ${TAP_REPO} (the error above says why). Check that the App has Contents read" \
        "and write on ${TAP_REPO}, then re-run publish-homebrew."
fi

title="infrahouse-toolkit ${VERSION}"
# printf, not a here-document in $(...): bash 3.2, macOS's, can't parse one with an apostrophe in it.
printf -v body '%s\n' \
    "Moves the formula to infrahouse-toolkit [${VERSION}](${release_url}). \`url\` is the release's macOS" \
    "tarball, and \`sha256\` is the checksum in its \`.sha256\`, checked against the tarball before this pull" \
    "request was opened." \
    "" \
    "Opened by \`publish-homebrew\` in [this CD run](${run_url}). \`infrahouse-toolkit formula\` installs and" \
    "tests the formula. Nothing merges this pull request automatically."
if [[ -n "${open_pr}" ]]; then
    if ! gh pr edit "${open_pr}" --repo "${TAP_REPO}" --title "${title}" --body "${body}" > /dev/null; then
        die "Couldn't update pull request #${open_pr} in ${TAP_REPO} (the error above says why). Re-run" \
            "publish-homebrew."
    fi
    pr_url="https://github.com/${TAP_REPO}/pull/${open_pr}"
    action="Updated"
else
    if ! pr_url="$(gh pr create --repo "${TAP_REPO}" --base main --head "${branch}" \
            --title "${title}" --body "${body}")"; then
        die "Couldn't open the pull request for ${branch} in ${TAP_REPO} (the error above says why). Check that" \
            "the App has Pull requests read and write there, then re-run publish-homebrew."
    fi
    action="Opened"
fi

echo "::notice::${action} ${pr_url}: ${title}"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
    echo "${action} the formula pull request for ${VERSION}: ${pr_url}" >> "${GITHUB_STEP_SUMMARY}"
fi
# An older one can't merge after this one without a conflict on the same lines, but it stays open until closed.
if (( ${#older_prs[@]} > 0 )); then
    echo "::notice::${TAP_REPO} still has open pull requests for older releases (${older_prs[*]}). ${title}" \
        "replaces them: close them without merging."
fi
