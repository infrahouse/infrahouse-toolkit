"""
.. topic:: ``utils.py``

    Various helper functions.
"""

import sys
from contextlib import contextmanager
from os import getgid, getuid
from subprocess import CalledProcessError, Popen, check_call
from tempfile import TemporaryDirectory

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.cli.ih_s3_reprepro.aws import assume_role
from infrahouse_toolkit.cli.ih_s3_reprepro.gpg import gpg

DEPENDENCIES = ["reprepro", "gpg", "s3fs"]


def check_dependencies(binaries: list):
    """
    Ensure that dependencies are installed. The function calls each of the binary
    with a ``--help`` option.

    :param binaries: Dependency commands. List of strings.
    :type binaries: list
    """
    for dep in binaries:
        try:
            with open("/dev/null", "w", encoding=DEFAULT_OPEN_ENCODING) as devnull:
                check_call([dep, "--help"], stdout=devnull, stderr=devnull)
        except FileNotFoundError:
            print(f"Looks like {dep} is not installed")
            print(f"Try installing it by \n\n\tapt-get install {dep}\n")
            sys.exit(1)


def mount_s3(bucket: str, path: str, role_arn: str = None):
    """
    Mount an S3 bucket at a path.

    :param bucket: AWS S3 bucket name.
    :type bucket: str
    :param path: Local filesystem path name.
    :type path: str
    :param role_arn: Assume role if specified.
    """
    env = {}
    cmd = ["s3fs", bucket, path, "-o", f"uid={getuid()}", "-o", f"gid={getgid()}"]
    if role_arn:
        env = assume_role(role_arn)
    check_call(cmd, env=env)


def umount_s3(path: str):
    """
    Unmount an S3 bucket at a path.

    :param path: Local filesystem path name where the S3 bucket is mounted at.
    :type path: str
    """
    try:
        check_call(["umount", path])
    except CalledProcessError:
        sys.exit(1)


@contextmanager
def local_s3(bucket, role_arn=None) -> str:
    """
    Mount an S3 bucket locally and return a mount point.

    :param bucket: AWS S3 bucket name.
    :type bucket: str
    :param role_arn: Assume role if specified.
    :type role_arn: str
    :return: Local filesystem path where the S3 bucket is mounted at.
    """
    with TemporaryDirectory() as mnt_dir:
        try:
            mount_s3(bucket, mnt_dir, role_arn=role_arn)
            yield mnt_dir

        except Exception as err:
            print(type(err), err)
            raise

        finally:
            umount_s3(mnt_dir)


def execute(cmd: list):
    """
    Execute a command and exit with 1 if the command raises CalledProcessError.

    :param cmd: A command to execute. It's passed to check_call() and therefore must be a list.
    :type cmd: list
    """
    try:
        with Popen(cmd) as proc:
            try:
                proc.communicate()
            except KeyboardInterrupt:
                print("Exiting on <ctrl>+c")
                proc.terminate()
                print(f"Process {cmd[0]} is terminated. Waiting for it to exit.")
                proc.wait(60)

    except CalledProcessError:
        sys.exit(1)


@contextmanager
def repo_env(bucket, role_arn, gpg_key_secret_id, gpg_passphrase_secret_id):
    """
    Prepare locally a repo and GPG so "reprepro" can manage it.

    :param bucket: AWS S3 bucket with the repo. The repo must be in the root.
    :type bucket: str
    :param role_arn: Optional role ARN. If specified, AWS client will assume it.
    :type role_arn: str
    :param gpg_key_secret_id: AWS secretsmanager secret (name or ARN) that stores the private GPG key,
        needed by ``reprepro`` to sign the repo.
    :type gpg_key_secret_id: str
    :param gpg_passphrase_secret_id: AWS secretsmanager secret (name or ARN) that stores a passphrase for
        the private GPG key. Note, it's not the passphrase itself, it's a secret that stores it.
    :type gpg_passphrase_secret_id: str
    :return: A tuple with two strings: Local filesystem directory with a mounted S3 bucket
        and GPG home directory.
    """
    with local_s3(bucket, role_arn) as path:
        with gpg(
            secret_key=gpg_key_secret_id, role_arn=role_arn, secret_passphrase=gpg_passphrase_secret_id
        ) as gpg_home:
            yield path, gpg_home
