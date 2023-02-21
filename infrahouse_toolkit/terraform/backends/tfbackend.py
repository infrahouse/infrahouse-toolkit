"""
Module for :py:class:`TFBackend`.
A generic class that defines the API for all kind of Terraform backends.
"""

from abc import ABC, abstractmethod


class TFBackend(ABC):
    """API to a Terraform backend."""

    # pylint: disable=invalid-name,too-few-public-methods
    # this is an abstract class, so it's OK to have fewer methods/attributes.
    @property
    @abstractmethod
    def id(self) -> str:  # pylint: disable=invalid-name
        """
        A unique identifier of the Terraform backend.
        """
