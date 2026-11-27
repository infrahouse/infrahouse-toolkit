"""
Print an installation token of the GitHub App that opens the formula pull requests in infrahouse/homebrew-tap.

publish-homebrew (``.github/workflows/python-CD.yml``) runs it from ``open-formula-pr.sh``, in a virtualenv of its
own with infrahouse-core 1.4 (``requirements.lock`` here), after it assumed the role that may call ``kms:Sign`` on
the App's key. The App's private key never leaves KMS: :class:`KMSSigner` signs the App's JWTs there, and GitHub
exchanges them for a token that expires in an hour.

The token is the only thing on stdout, without a newline, so that the caller can capture it and mask it before
anything prints it. Errors go to stderr as ``::error::`` workflow commands. Nothing here logs: at DEBUG, PyGithub
logs response bodies, the token among them, so no logging is configured.

Environment:

- ``HOMEBREW_TAP_APP_ID``: the App ID.
- ``HOMEBREW_TAP_KMS_ALIAS_ARN``: the ARN of the alias of the KMS key that holds the App's private key. Its region
  is the key's. aws-control-493370826424 points the alias at the key, so a new key changes nothing here.

See the "How a release reaches the Homebrew formula" section of ``packaging/README.md``.
"""

import os
import re
import sys

from botocore.exceptions import BotoCoreError, ClientError
from github import GithubException
from infrahouse_core.github import GitHubAppTokenSource, KMSSigner
from requests import RequestException

# The App is installed on infrahouse/homebrew-tap only, so the token reaches no other repository.
GITHUB_ORG = "infrahouse"
# What the pull request needs: push a branch, open or update the pull request. Nothing else, even if the App
# is later given more.
PERMISSIONS = {"contents": "write", "pull_requests": "write"}

APP_ID_PATTERN = re.compile(r"^[0-9]+$")
KMS_ALIAS_ARN_PATTERN = re.compile(r"^arn:aws:kms:(?P<region>[a-z0-9-]+):[0-9]{12}:alias/[A-Za-z0-9/_-]+$")


class MintError(Exception):
    """
    The token couldn't be minted. The message says what failed and what to do about it, on one line.
    """


class TapToken:
    """
    The App's installation token for infrahouse/homebrew-tap, minted with a JWT that KMS signs.

    :param app_id: The App ID.
    :param kms_alias_arn: The ARN of the alias of the KMS key that holds the App's private key. Its region is the
        key's.
    :raises MintError: If either isn't what it should be.
    """

    def __init__(self, app_id: str, kms_alias_arn: str):
        alias_match = KMS_ALIAS_ARN_PATTERN.match(kms_alias_arn)
        if not APP_ID_PATTERN.match(app_id) or alias_match is None:
            raise MintError(
                f"HOMEBREW_TAP_APP_ID is '{app_id}' and HOMEBREW_TAP_KMS_ALIAS_ARN is '{kms_alias_arn}'."
                " Set them in publish-homebrew's env in python-CD.yml to the App ID and the key's alias ARN."
            )
        self._app_id = app_id
        self._kms_alias_arn = kms_alias_arn
        self._region = alias_match.group("region")

    # --- Public properties ---

    @property
    def app_id(self) -> str:
        """
        :return: The App ID.
        """
        return self._app_id

    @property
    def kms_alias_arn(self) -> str:
        """
        :return: The ARN of the alias of the KMS key that holds the App's private key.
        """
        return self._kms_alias_arn

    # --- Public methods ---

    def mint(self) -> str:
        """
        Mint the token: the App's JWT signed with ``kms:Sign``, exchanged for an installation token.

        :return: The token, which expires in an hour.
        :raises MintError: If KMS, AWS or GitHub refused, with what to do about it.
        """
        source = GitHubAppTokenSource(self.app_id, KMSSigner(self.kms_alias_arn, region=self._region))
        try:
            return source.installation_token(GITHUB_ORG, permissions=PERMISSIONS)
        except ClientError as err:
            raise MintError(
                f"KMS refused to sign the App's JWT with {self.kms_alias_arn}: {err}."
                " Check that the job assumed the homebrew-tap role, that the alias exists, that the role's policy"
                " allows kms:Sign with RSASSA_PKCS1_V1_5_SHA_256 on the key the alias points to, and that the key"
                " is enabled."
            ) from err
        except BotoCoreError as err:
            raise MintError(
                f"No AWS credentials or no answer from KMS: {err}."
                " Check the 'Assume the role that may sign as the App' step."
            ) from err
        except GithubException as err:
            raise MintError(
                f"GitHub refused the App's JWT or the token ({err.status}: {err.data})."
                f" Check that the key in KMS is a current private key of App {self.app_id}, and that the App"
                " has Contents and Pull requests read and write on infrahouse/homebrew-tap."
            ) from err
        except RequestException as err:
            raise MintError(
                f"GitHub didn't answer when looking up App {self.app_id}'s installations: {err}. Re-run the job."
            ) from err
        except RuntimeError as err:
            raise MintError(f"{err}. Install App {self.app_id} on infrahouse/homebrew-tap.") from err


def main() -> int:
    """
    Mint the token and print it on stdout, or an ``::error::`` on stderr.

    :return: The exit code: 0 with the token on stdout, 1 with an error on stderr and nothing on stdout.
    """
    try:
        token = TapToken(
            os.environ.get("HOMEBREW_TAP_APP_ID", ""), os.environ.get("HOMEBREW_TAP_KMS_ALIAS_ARN", "")
        ).mint()
    except MintError as err:
        print(f"::error::{err}", file=sys.stderr)
        return 1

    sys.stdout.write(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
