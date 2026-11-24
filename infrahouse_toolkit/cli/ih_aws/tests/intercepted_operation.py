"""A stand-in for one AWS API operation that moto doesn't implement."""

from typing import Dict, List, Optional

from botocore.client import BaseClient
from botocore.exceptions import ClientError

_MAKE_API_CALL = BaseClient._make_api_call  # pylint: disable=protected-access


class InterceptedOperation:
    """
    Answers one API operation and passes every other call to the original ``BaseClient._make_api_call``,
    so moto handles it.

    Patch it in with
    ``mock.patch.object(BaseClient, "_make_api_call", autospec=True, side_effect=api.make_api_call)``.

    :param operation_name: The operation to answer, e.g. ``CompleteLifecycleAction``.
    :type operation_name: str
    :param response: What the operation returns. Defaults to an empty response.
    :type response: dict
    :param error_code: If given, the operation fails with this error code instead.
    :type error_code: str
    """

    def __init__(self, operation_name: str, response: Optional[Dict] = None, error_code: Optional[str] = None):
        self._calls = []
        self._error_code = error_code
        self._operation_name = operation_name
        self._response = response or {}

    @property
    def calls(self) -> List[Dict]:
        """
        :return: Parameters of every call of the operation.
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
        if operation_name != self._operation_name:
            return _MAKE_API_CALL(client, operation_name, api_params)

        self._calls.append(api_params)
        if self._error_code:
            raise ClientError(
                {"Error": {"Code": self._error_code, "Message": f"{self._error_code} from the test"}}, operation_name
            )
        return self._response
