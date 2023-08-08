"""
InfraHouse Lock interface.
"""


class BaseLock:
    """
    Base Lock interface.

    Provides public properties and methods.
    """

    def __init__(self):
        self._name = None

    @property
    def name(self):
        """Descriptive for humans lock name."""
        return self._name

    @property
    def exclusive(self):
        """Whether the lock is exclusive as opposite of shared."""
        return True

    @property
    def shared(self):
        """Whether the lock is shared as opposite of exclusive."""
        return not self.exclusive
