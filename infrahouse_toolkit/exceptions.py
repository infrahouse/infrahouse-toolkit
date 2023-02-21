"""Top level exceptions.

The exception hierarchy repeats the structure of the infrahouse_toolkit package.
Each module in the package has its own exceptions.py module.
The module exceptions are inherited from the upper module exceptions.

"""


class IHException(Exception):
    """Generic InfraHouse exception"""
