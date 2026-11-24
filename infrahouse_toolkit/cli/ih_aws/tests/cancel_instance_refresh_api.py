"""A stand-in for the ``CancelInstanceRefresh`` API, which moto doesn't implement."""

from typing import Optional

from infrahouse_toolkit.cli.ih_aws.tests.intercepted_operation import (
    InterceptedOperation,
)


class CancelInstanceRefreshAPI(InterceptedOperation):
    """
    Answers ``CancelInstanceRefresh`` and passes every other call to moto.

    :param error_code: If given, ``CancelInstanceRefresh`` fails with this error code.
    :type error_code: str
    """

    def __init__(self, error_code: Optional[str] = None):
        super().__init__(
            "CancelInstanceRefresh",
            response={"InstanceRefreshId": "08b91cf7-8fa6-48af-b6a6-d227f40f1b9b"},
            error_code=error_code,
        )
