"""
.. topic:: ``ih-aws resources list``

    A ``ih-aws resources list`` subcommand.

    See ``ih-aws resources list --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import (
    find_resources_by_tags,
    format_resources_arns,
    format_resources_json,
    format_resources_table,
)
from infrahouse_toolkit.cli.ih_aws.cmd_resources.tag_filters import build_tag_filters

LOG = getLogger(__name__)


@click.command(name="list")
@click.option(
    "--tag",
    "-t",
    "tags",
    multiple=True,
    help="Tag filter as key=value or just key (any value).  May be repeated; multiple tags use AND logic.",
)
@click.option(
    "--service",
    default=None,
    help="Shorthand for --tag service=VALUE.",
)
@click.option(
    "--environment",
    default=None,
    help="Shorthand for --tag environment=VALUE.",
)
@click.option(
    "--output",
    "-o",
    "output_format",
    type=click.Choice(["table", "json", "arns"]),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--no-verify",
    is_flag=True,
    default=False,
    help="Skip per-resource existence checks (faster, may show stale entries).",
)
@click.option(
    "--no-tags",
    is_flag=True,
    default=False,
    help="Hide tags column in table output.",
)
@click.pass_context
def cmd_list(  # pylint: disable=too-many-arguments
    ctx: click.Context,
    tags: tuple,
    service: str,
    environment: str,
    output_format: str,
    no_verify: bool,
    no_tags: bool,
) -> None:
    """
    List AWS resources matching the given tag filters.
    """
    tag_filters = build_tag_filters(tags, service, environment)
    if not tag_filters:
        raise click.UsageError("At least one tag filter is required.  Use --tag, --service, or --environment.")

    aws_session = ctx.obj["aws_session"]

    try:
        resources = find_resources_by_tags(aws_session, tag_filters, verify=not no_verify)
    except ClientError as exc:
        LOG.error("AWS error: %s", exc)
        sys.exit(1)

    if not resources:
        click.echo("No resources found.")
        return

    if output_format == "table":
        click.echo(format_resources_table(resources, show_tags=not no_tags))
    elif output_format == "json":
        click.echo(format_resources_json(resources))
    elif output_format == "arns":
        click.echo(format_resources_arns(resources))
