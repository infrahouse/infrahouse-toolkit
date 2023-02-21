"""
Module for various Terraform backends.
"""

from typing import Union
from urllib.parse import urlparse

from infrahouse_toolkit.terraform.backends.exceptions import IHUnknownBackend
from infrahouse_toolkit.terraform.backends.s3backend import TFS3Backend


def get_backend(backend_id: str) -> Union[TFS3Backend,]:
    """
    Parse ``backend_id`` string and build a Terraform backend object based on the parsed values.

    :param backend_id: a straing that identifies a Terraform backend.
    :type backend_id: str
    :return: Terraform backend object.
    :rtype: Union[TFS3Backend, ]
    :raise IHUnknownBackend: If parsing failed or the encoded backend is not supported
    """
    result = urlparse(backend_id)
    if result.scheme == "s3":
        return TFS3Backend(result.netloc, result.path.lstrip("/"))
    raise IHUnknownBackend(f"Cannot find supported Terraform backend from {backend_id}.")
