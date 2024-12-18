"""
.. topic:: ``utils.py``

    Various helper functions.
"""

import json
import os
import pathlib
import sys
from contextlib import contextmanager
from logging import getLogger
from os import getgid, getuid
from os import path as osp
from subprocess import PIPE, CalledProcessError, Popen, check_call, run
from tempfile import TemporaryDirectory
from time import sleep, time

import boto3

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.aws import (
    assume_role,
    get_credentials_from_environ,
    get_credentials_from_profile,
)
from infrahouse_toolkit.cli.gpg import gpg
from infrahouse_toolkit.exceptions import IHRetriableError

DEPENDENCIES = ["reprepro", "gpg", "s3fs"]
LOG = getLogger()


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
                LOG.debug("Checking if %s is installed.", dep)
                check_call([dep, "--help"], stdout=devnull, stderr=devnull)
        except FileNotFoundError:
            LOG.error("Looks like %s is not installed", dep)
            LOG.info("Try installing it by \n\n\tapt-get install %s\n", dep)
            sys.exit(1)


def mount_s3(bucket: str, path: str, role_arn: str = None, region: str = None):
    """
    Mount an S3 bucket at a path.

    :param bucket: AWS S3 bucket name.
    :type bucket: str
    :param path: Local filesystem path name.
    :type path: str
    :param role_arn: Assume role if specified.
    :param region: AWS region name.
    :type region: str
    """
    LOG.debug("Mounting bucket %s on %s", bucket, path)
    env = {}
    cmd = ["s3fs", bucket, path, "-o", f"uid={getuid()}", "-o", f"gid={getgid()}"]
    if role_arn:
        LOG.debug("Using AWS credentials from IAM role %s", role_arn)
        env = assume_role(role_arn)
        sts = boto3.client(
            "sts",
            aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=env["AWS_SESSION_TOKEN"],
            region_name=region,
        )
        response = sts.get_caller_identity()
        LOG.debug("Assumed role: %s", response)
    elif "AWS_ACCESS_KEY_ID" in os.environ:
        env = get_credentials_from_environ()
    else:
        env = get_credentials_from_profile()

    LOG.debug(
        "To reproduce environment: \n%s",
        "\n".join([f'export {key}="{value}"' for key, value in sanitize_env(env).items()]),
    )
    LOG.debug("Command to debug: mkdir -p %s; %s -o dbglevel=info -f -o curldbg", path, " ".join(cmd))
    execute(cmd, env=env)


def umount_s3(path: str):
    """
    Unmount an S3 bucket at a path.

    :param path: Local filesystem path name where the S3 bucket is mounted at.
    :type path: str
    """
    try:
        check_call(["umount", path])
    except CalledProcessError as err:
        LOG.exception(err)
        sys.exit(1)


@contextmanager
def local_s3(bucket, role_arn=None, retry_timeout=60, region=None, check_file="conf/distributions") -> str:
    """
    Mount an S3 bucket locally and return a mount point.

    :param bucket: AWS S3 bucket name.
    :type bucket: str
    :param role_arn: Assume role if specified.
    :type role_arn: str
    :param retry_timeout: How many second to keep trying to mount the bucket.
    :type retry_timeout: int
    :param check_file: When this file exists, the bucket is considered mounted.
    :type check_file: str
    :param region: AWS region name.
    :type region: str
    :return: Local filesystem path where the S3 bucket is mounted at.
    """
    with TemporaryDirectory() as mnt_dir:
        try:
            now = time()
            timeout = now + retry_timeout
            mount_s3(bucket, mnt_dir, role_arn=role_arn, region=region)
            while True:
                if osp.exists(osp.join(mnt_dir, check_file)):
                    LOG.debug("Mounted successfully %s on %s", bucket, mnt_dir)
                    break
                LOG.warning("Waiting until s3://%s is mounted at %s", bucket, mnt_dir)
                sleep(1)
                if time() > timeout:
                    raise RuntimeError(f"s3://{bucket} is not mounted after {retry_timeout} seconds")
            yield mnt_dir
        # except Exception as err:
        #     LOG.critical(err)
        #     raise

        finally:
            umount_s3(mnt_dir)


@contextmanager
def tmpfs_s3(bucket, role_arn=None, volume_size="512M") -> str:
    """
    Mount a temporary file system, sync an S3 bucket onto it.
    Then sync the local volume back to S3 an umount it.

    :param bucket: AWS S3 bucket name.
    :type bucket: str
    :param role_arn: Assume role if specified.
    :type role_arn: str
    :param volume_size: Temporary memory partition size. By default, 512M.
    :type volume_size: str
    :return: Local filesystem path where the S3 bucket is mounted at.
    """
    with TemporaryDirectory() as mnt_dir:
        try:
            run(
                ["mount", "-t", "tmpfs", "-o", f"size={volume_size}", "tmpfs", mnt_dir],
                capture_output=True,
                check=True,
            )
            # check_call(["aws", "s3", "sync", "--quiet", f"s3://{bucket}", mnt_dir])
            yield mnt_dir
            env = assume_role(role_arn) if role_arn else {}
            run(
                ["aws", "s3", "sync", "--only-show-errors", mnt_dir, f"s3://{bucket}"],
                capture_output=True,
                check=True,
                env={**env, **{"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}},
            )
        except CalledProcessError as err:
            LOG.error(err)
            LOG.error("stdout: %s", err.output)
            LOG.error("stderr: %s", err.stderr)
            raise
        finally:
            check_call(["umount", mnt_dir])


def execute(cmd: list, cwd: str = None, env: dict = None, exit_on_error: bool = True):
    """
    Execute a command and exit with 1 if the command raises CalledProcessError.

    :param cmd: A command to execute. It's passed to check_call() and therefore must be a list.
    :type cmd: list
    :param cwd: Working directory for the command.
    :type cwd: str
    :param env: Pass a dictionary with environment
    :type env: dict
    :param exit_on_error: If False, let the caller decide what to do on CalledProcessError exception.
    :type exit_on_error: bool
    """
    try:
        LOG.debug("Executing: '%s'", " ".join(cmd))
        LOG.debug("Environment: %s", json.dumps(sanitize_env(env), indent=4) if env else "None")
        with Popen(cmd, env=env, cwd=cwd, stdout=PIPE, stderr=PIPE) as proc:
            try:
                cout, cerr = proc.communicate()
                ret_code = proc.returncode
                LOG.debug("Command: '%s': Return code: %d", " ".join(cmd), ret_code)
                if cout:
                    print(cout.decode())
                if ret_code != 0:
                    print(cerr.decode())
                    raise CalledProcessError(
                        returncode=ret_code, cmd=" ".join(cmd), output=cout.decode(), stderr=cerr.decode()
                    )
            except KeyboardInterrupt:
                LOG.info("Exiting on <ctrl>+c")
                proc.terminate()
                LOG.info("Process '%s' is terminated. Waiting for it to exit.", cmd[0])
                proc.wait(60)

    except CalledProcessError as err:
        LOG.exception(err)
        LOG.error("CWD: %s", cwd)
        if exit_on_error:
            sys.exit(1)
        raise IHRetriableError(returncode=ret_code, cmd=cmd, output=err.output, stderr=err.stderr) from err
        # raise CalledProcessError(returncode=ret_code, cmd=" ".join(cmd)) from err


@contextmanager
def repo_env(bucket, role_arn, gpg_key_secret_id, gpg_passphrase_secret_id, region=None):
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
    :param region: AWS region name.
    :type region: str
    :return: A tuple with two strings: Local filesystem directory with a mounted S3 bucket
        and GPG home directory.
    """
    with local_s3(bucket, role_arn, region=region) as path:
        # pylint: disable-next=contextmanager-generator-missing-cleanup
        with gpg(
            secret_key=gpg_key_secret_id, role_arn=role_arn, secret_passphrase=gpg_passphrase_secret_id, region=region
        ) as gpg_home:
            yield path, gpg_home


def sanitize_env(env: dict = None) -> dict:
    """
    Mask secrets in environment variables.

    :param env: original environment
    :return: Environment without secret values
    """
    secret_keys = [
        "AWSSECRETACCESSKEY",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "GITHUB_TOKEN",
        "GH_TOKEN",
        "AWSSESSIONTOKEN",
    ]
    return {key: value if key not in secret_keys else "***" for key, value in env.items()}


def mkdir_p(new_directory):
    """
    Equivalent of a shell command mkdir -p

    :param new_directory: Create a directory and its parents if needed.
    :type new_directory: str
    """
    pathlib.Path(new_directory).mkdir(parents=True, exist_ok=True)


def retry(func, args, kwargs, attempts: int = 5, retriable_exit_codes: list = None):
    """
    Execute a function and retry up to attempts times if it raised IHRetriableError

    :param func: Callable instance.
    :type func: callable
    :param args: Positional arguments to the function.
    :type args: tuple
    :param kwargs: Keyword arguments to the function.
    :type kwargs: dict
    :param attempts: Call the function up to this many times.
    :param retriable_exit_codes: IHRetriableError has a returncode. Retry only it the return code is in this list.
    """
    retriable_exit_codes = retriable_exit_codes or [1]
    sleep_time_sec = 1
    for attempt in range(attempts):
        try:
            return func(*args, **kwargs)
        except IHRetriableError as err:
            LOG.warning(err)
            LOG.warning("stdout: %s", err.output)
            LOG.warning("stderr: %s", err.stderr)
            if err.returncode in retriable_exit_codes:
                LOG.warning(
                    "Attempt %d out of %d failed. Will retry in %d second(s).", attempt, attempts, sleep_time_sec
                )
                sleep(sleep_time_sec)
                attempt += 1
                continue
            raise
    raise RuntimeError(f"Function didn't succeed after {attempts} attempts")
