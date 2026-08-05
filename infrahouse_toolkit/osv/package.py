"""
Module for Package class - a package osv-scanner found in a dependency lock file.
"""


class Package:
    """
    A package osv-scanner found in a dependency lock file.

    :param package: A ``package`` section of the osv-scanner JSON report.
    :type package: dict
    """

    def __init__(self, package: dict):
        self._package = package

    def __str__(self) -> str:
        """
        :return: Package name and version, e.g. ``aiohttp==3.14.1``.
        :rtype: str
        """
        return f"{self.name}=={self.version}"

    @property
    def ecosystem(self) -> str:
        """
        :return: Ecosystem the package comes from, e.g. ``PyPI``.
        :rtype: str
        """
        return self._package["ecosystem"]

    @property
    def name(self) -> str:
        """
        :return: Package name, e.g. ``aiohttp``.
        :rtype: str
        """
        return self._package["name"]

    @property
    def version(self) -> str:
        """
        :return: Installed version of the package, e.g. ``3.14.1``.
        :rtype: str
        """
        return self._package["version"]
