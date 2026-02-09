"""Shared tag filter helpers for ``ih-aws resources`` subcommands."""

from typing import Dict, List


def build_tag_filters(tags: tuple, service: str, environment: str) -> List[Dict]:
    """
    Build a list of tag filter dicts from CLI options.

    Each tag spec can be ``key=value`` (match specific value) or just
    ``key`` (match any resource that has the tag, regardless of value).

    :param tags: Tuple of ``key=value`` or ``key`` strings from ``--tag`` options.
    :param service: Shorthand value for ``--service`` option.
    :param environment: Shorthand value for ``--environment`` option.
    :return: List of dicts.  Each dict has a ``"key"`` entry and an
        optional ``"value"`` entry (omitted for key-only filters).
    """
    tag_filters: List[Dict] = []
    for tag_spec in tags:
        if "=" in tag_spec:
            key, value = tag_spec.split("=", 1)
            tag_filters.append({"key": key, "value": value})
        else:
            tag_filters.append({"key": tag_spec})

    if service:
        tag_filters.append({"key": "service", "value": service})
    if environment:
        tag_filters.append({"key": "environment", "value": environment})

    return tag_filters
