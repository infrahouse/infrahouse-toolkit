"""
AWS classes.
"""

import sys
import time
import webbrowser
from logging import getLogger
from os import path as osp
from pprint import pformat
from time import sleep

import boto3
from boto3 import Session
from botocore.exceptions import (
    NoCredentialsError,
    SSOTokenLoadError,
    TokenRetrievalError,
)
from diskcache import Cache

from infrahouse_toolkit.aws.config import AWSConfig
from infrahouse_toolkit.aws.exceptions import IHAWSException
from infrahouse_toolkit.fs import ensure_permissions

LOG = getLogger()


def aws_sso_login(aws_config: AWSConfig, profile_name: str, region: str = None):
    """
    Login into AWS using SSO.

    Credit:
    https://stackoverflow.com/questions/62311866/how-to-use-the-aws-python-sdk-while-connecting-via-sso-credentials
    """
    cache_directory = osp.expanduser("~/.infrahouse-toolkit")
    with Cache(directory=cache_directory) as cache_reference:
        cache_key = f"ih-ec2-credentials-{profile_name}"
        credentials = cache_reference.get(cache_key)
        if not credentials:
            credentials = _get_credentials(aws_config, profile_name)
            cache_reference.set(
                cache_key, credentials, expire=int(int(credentials["expiration"]) / 1000 - int(time.time()))
            )

    ensure_permissions(cache_directory, 0o700)
    return Session(
        region_name=region or aws_config.get_region(profile_name),
        aws_access_key_id=credentials["accessKeyId"],
        aws_secret_access_key=credentials["secretAccessKey"],
        aws_session_token=credentials["sessionToken"],
    )


def get_aws_client(service_name: str, profile: str, region: str, session=None):
    """
    Get a client instance for an AWS service.

    :param service_name: AWS service e.g. ``ec2``.
    :param profile: AWS profile for authentication.
    :param region: AWS region.
    :param session: if an AWS session is passed, use it to create a client.
    :type session: Session
    :return: A client instance.
    """
    session = session or Session(region_name=region, profile_name=profile)
    return session.client(service_name)


def get_aws_session(aws_config: AWSConfig, aws_profile: str, aws_region: str) -> Session:
    """

    :param aws_config:
    :param aws_profile:
    :param aws_region:
    :return: Authenticated AWS session, or None if boto3 can connect to AWS without extra steps.
    """
    if aws_profile is None and "default" in aws_config.profiles:
        aws_profile = "default"

    try:
        response = get_aws_client("sts", aws_profile, aws_region).get_caller_identity()
        LOG.info("Connected to AWS as %s", response["Arn"])

    except (SSOTokenLoadError, TokenRetrievalError) as err:
        if not aws_profile:
            LOG.error("Try to run ih-aws with --aws-profile option.")
            LOG.error("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
            sys.exit(1)
        LOG.debug(err)
        aws_session = aws_sso_login(aws_config, aws_profile, region=aws_region)
        response = get_aws_client("sts", aws_profile, aws_region, session=aws_session).get_caller_identity()
        LOG.info("Connected to AWS as %s", response["Arn"])
        return aws_session

    except NoCredentialsError as err:
        LOG.error(err)
        LOG.info("Try to run ih-aws with --aws-profile option.")
        LOG.info("Available profiles:\n\t%s", "\n\t".join(aws_config.profiles))
        sys.exit(1)

    return boto3.Session(region_name=aws_region)


def _get_credentials(aws_config: AWSConfig, profile_name: str):
    """
    Login into AWS using SSO.

    Credit:
    https://stackoverflow.com/questions/62311866/how-to-use-the-aws-python-sdk-while-connecting-via-sso-credentials

    :raise IHAWSException: If user didn't confirm auth
    """

    session = Session()
    sso_oidc = session.client("sso-oidc")
    client_creds = sso_oidc.register_client(
        clientName="infrahouse-toolkit",
        clientType="public",
    )
    LOG.debug("client_creds = %s", pformat(client_creds, indent=4))
    device_authorization = sso_oidc.start_device_authorization(
        clientId=client_creds["clientId"],
        clientSecret=client_creds["clientSecret"],
        startUrl=aws_config.get_start_url(profile_name),
    )

    LOG.debug("device_authorization = %s", pformat(device_authorization, indent=4))
    url = device_authorization["verificationUriComplete"]
    device_code = device_authorization["deviceCode"]
    expires_in = device_authorization["expiresIn"]
    interval = device_authorization["interval"]
    LOG.info("Verify user code: %s", device_authorization["userCode"])
    webbrowser.open(url, autoraise=True)
    for _ in range(1, expires_in // interval + 1):
        sleep(interval)
        try:
            token = sso_oidc.create_token(
                grantType="urn:ietf:params:oauth:grant-type:device_code",
                deviceCode=device_code,
                clientId=client_creds["clientId"],
                clientSecret=client_creds["clientSecret"],
            )
            access_token = token["accessToken"]
            sso = session.client("sso")
            role_creds = sso.get_role_credentials(
                roleName=aws_config.get_role(profile_name),
                accountId=aws_config.get_account_id(profile_name),
                accessToken=access_token,
            )["roleCredentials"]
            return role_creds
        except sso_oidc.exceptions.AuthorizationPendingException:
            pass

    raise IHAWSException(f"The verification code isn't confirmed by user in {expires_in} seconds")
