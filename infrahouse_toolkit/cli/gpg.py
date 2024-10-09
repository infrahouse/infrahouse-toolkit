"""
.. topic:: ``gpg.py``

    GPG helper functions.
"""

from contextlib import contextmanager
from logging import getLogger
from os import path as osp
from subprocess import Popen
from tempfile import NamedTemporaryFile, TemporaryDirectory

from botocore.exceptions import ClientError

from infrahouse_toolkit import DEFAULT_ENCODING, DEFAULT_OPEN_ENCODING
from infrahouse_toolkit.aws import get_client

LOG = getLogger()


@contextmanager
def gpg_home() -> str:
    """
    :return: GPG home directory
    """
    with TemporaryDirectory() as path:
        LOG.debug("GPG home is %s", path)
        yield path


@contextmanager
def gpg(secret_key=None, role_arn=None, secret_passphrase=None, region: str = None) -> str:
    """
    Prepare GPG keyring and yield path to it.
    If no function arguments are specified, it will return the default path ~/.gnupg.

    If secret_key is specified, the function will pull the GPG key from this secret.
    Optionally, it will assume a role, if given.

    If secret_passphrase isn't specified, gpg and reprepro will ask a passphrase from a terminal.
    If specified, the function will pull the passprase from AWS secretsmanager secret secret_passphrase,
    save it in a temporary file, and create a GPG config so gpg can read the passphrase from
    the temporary file.

    The GPG private key will be imported. Again, if secret_key is specified.
    So the GPG home will include the private key.

    :param secret_key: AWS secret id (name or ARN) with a GPG private key.
    :type secret_key: str
    :param role_arn: If specified, assume this role in AWS client.
    :type role_arn: str
    :param secret_passphrase: AWS secret id (name or ARN) with a passphrase for the GPG private key.
    :type secret_passphrase: str
    :param region: AWS region name.
    :type region: str
    :return: Path to GPG homedir.
    :rtype: str
    """
    if secret_key:
        LOG.debug("Reading GPG key from %s", secret_key)
        try:
            secrets_manager = get_client("secretsmanager", role_arn=role_arn, region=region)
            key = secrets_manager.get_secret_value(SecretId=secret_key)["SecretString"]
        except ClientError as err:
            LOG.error(err)
            if err.response["Error"]["Code"] == "ResourceNotFoundException":
                LOG.error("Make sure that you set a secret value to the key %s:", secret_key)
                LOG.error("ih-s3-reprepro ... set-secret-value %s /path/to/file/with/%s-value", secret_key, secret_key)
            raise

        with gpg_home() as homedir, NamedTemporaryFile() as gpg_key_desc, NamedTemporaryFile() as gpg_passphrase_desc:
            gpg_key_desc.write(key.encode(DEFAULT_ENCODING))
            gpg_key_desc.flush()

            cmd = ["gpg", "--homedir", homedir]

            if secret_passphrase:
                LOG.debug("Reading GPG key passphrase from %s", secret_passphrase)
                passphrase = secrets_manager.get_secret_value(SecretId=secret_passphrase)["SecretString"]
                gpg_passphrase_desc.write(passphrase.encode(DEFAULT_ENCODING))
                gpg_passphrase_desc.flush()
                write_gpg_cong(
                    osp.join(homedir, "gpg.conf"),
                    {"batch": None, "passphrase-file": gpg_passphrase_desc.name, "pinentry-mode": "loopback"},
                )

            cmd.extend(["--import", gpg_key_desc.name])
            LOG.debug("Executing: %s", " ".join(cmd))
            proc = Popen(cmd)
            proc.communicate()
            yield homedir
    else:
        yield osp.expanduser("~/.gnupg")


def write_gpg_cong(path: str, options: dict):
    """
    Prepare GPG config file.

    :param path: Path name to the GPG config file.
    :type path: str
    :param options: A dictionary with options. For one word options the key value is None.
    :type options: dict
    """
    LOG.debug("Saving GPG config in %s", path)
    with open(path, "w", encoding=DEFAULT_OPEN_ENCODING) as gpg_conf_desc:
        for key, value in options.items():
            gpg_conf_desc.write(f"{key}")
            if value:
                gpg_conf_desc.write(f" {value}")
            gpg_conf_desc.write("\n")
