"""
Module for AWSConfig class.
"""
from configparser import ConfigParser
from os import path as osp


class AWSConfig:
    """
    Class AWSConfig parses AWS CLI config file, ``~/.aws/config`` by default,
    and provides a convenient interfaces to certain configuration options.

    :param aws_home: Path to a directory with AWS configs. By default, ``~/.aws/``.
    :type aws_home: str
    """

    def __init__(self, aws_home=None):
        self._aws_home = aws_home
        self._config_parser = None

    @property
    def aws_home(self):
        """Path to AWS config directory."""
        if self._aws_home is None:
            self._aws_home = osp.join(osp.expanduser("~"), ".aws")
        return self._aws_home

    @property
    def config_path(self):
        """Path to AWS config file."""
        return osp.join(self.aws_home, "config")

    @property
    def config_parser(self) -> ConfigParser:
        """ConfigParser object that represents ``~/.aws/config``."""
        if self._config_parser is None:
            self._config_parser = ConfigParser()
            self._config_parser.read(self.config_path)

        return self._config_parser

    @property
    def profiles(self) -> list:
        """List of configured AWS profiles."""
        return [
            "default" if section == "default" else section.split(" ")[1]
            for section in self.config_parser.sections()
            if (section.startswith("profile") or section == "default")
        ]

    def get_account_id(self, profile_name):
        """Read account id for given profile."""
        return self.config_parser.get(self._get_section(profile_name), "sso_account_id")

    def get_region(self, profile_name):
        """Read AWS region for given profile."""
        return self.config_parser.get(self._get_section(profile_name), "region")

    def get_role(self, profile_name):
        """Read AWS IAM role for given profile."""
        return self.config_parser.get(self._get_section(profile_name), "sso_role_name")

    def get_start_url(self, profile_name):
        """Read SSO URL for given profile."""
        sso_session = self.config_parser.get(self._get_section(profile_name), "sso_session")
        return self.config_parser.get(f"sso-session {sso_session}", "sso_start_url")

    @staticmethod
    def _get_section(profile_name):
        return profile_name if profile_name == "default" else f"profile {profile_name}"
