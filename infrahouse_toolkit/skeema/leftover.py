"""
Module for Leftover class - an object an interrupted online schema change left behind.
"""


class Leftover:
    """
    A table or trigger ``pt-online-schema-change`` creates for the duration of a change.

    If one survives, the next run on that table refuses to start because the triggers exist,
    and skeema wants to ``DROP`` the shadow table, which it won't do unless unsafe changes
    are allowed.

    :param instance: Instance the object is on.
    :type instance: str
    :param schema: Schema the object is in.
    :type schema: str
    :param kind: ``table`` or ``trigger``.
    :type kind: str
    :param name: Name of the object.
    :type name: str
    """

    def __init__(self, instance: str, schema: str, kind: str, name: str):
        self._instance = instance
        self._schema = schema
        self._kind = kind
        self._name = name

    # --- Public properties ---

    @property
    def instance(self) -> str:
        """
        :return: Instance the object is on.
        :rtype: str
        """
        return self._instance

    @property
    def kind(self) -> str:
        """
        :return: ``table`` or ``trigger``.
        :rtype: str
        """
        return self._kind

    @property
    def name(self) -> str:
        """
        :return: Name of the object.
        :rtype: str
        """
        return self._name

    @property
    def schema(self) -> str:
        """
        :return: Schema the object is in.
        :rtype: str
        """
        return self._schema
