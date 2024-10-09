"""Top level exceptions.

The exception hierarchy repeats the structure of the infrahouse_toolkit package.
Each module in the package has its own exceptions.py module.
The module exceptions are inherited from the upper module exceptions.

"""


class IHException(Exception):
    """Generic InfraHouse exception"""


class IHRetriableError(IHException):
    """Operation failed, but can be retried."""

    def __init__(self, returncode=None, cmd=None, output=None, stderr=None):
        self.returncode = returncode
        self.cmd = " ".join(cmd) if isinstance(cmd, list) else cmd
        self.output = output
        self.stderr = stderr

    def __str__(self):
        return f"Command '{self.cmd}' returned non-zero exit status {self.returncode}."
