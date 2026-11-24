"""A stand-in for the ``CancelInstanceRefresh`` API, which moto doesn't implement."""

from typing import Dict, List, Optional

from botocore.client import BaseClient
from botocore.exceptions import ClientError

_MAKE_API_CALL = BaseClient._make_api_call  # pylint: disable=protected-access


class CancelInstanceRefreshAPI:
    """
    Answers ``CancelInstanceRefresh`` and passes every other call to the original
    ``BaseClient._make_api_call``, so moto handles it.

    :param error_code: If given, ``CancelInstanceRefresh`` fails with this error code.
    :type error_code: str
    """

    def __init__(self, error_code: Optional[str] = None):
        self._calls = []
        self._error_code = error_code

    @property
    def calls(self) -> List[Dict]:
        """
        :return: Parameters of every ``CancelInstanceRefresh`` call.
        """
        return self._calls

    def make_api_call(self, client: BaseClient, operation_name: str, api_params: Dict) -> Dict:
        """
        Replacement for ``BaseClient._make_api_call``.

        :param client: The boto3 client that makes the call.
        :type client: botocore.client.BaseClient
        :param operation_name: API operation name.
        :type operation_name: str
        :param api_params: API call parameters.
        :type api_params: dict
        :return: The API response.
        :rtype: dict
        """
        if operation_name != "CancelInstanceRefresh":
            return _MAKE_API_CALL(client, operation_name, api_params)

        self._calls.append(api_params)
        if self._error_code:
            raise ClientError(
                {"Error": {"Code": self._error_code, "Message": f"{self._error_code} from the test"}}, operation_name
            )
        return {"InstanceRefreshId": "08b91cf7-8fa6-48af-b6a6-d227f40f1b9b"}
