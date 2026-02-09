"""
.. topic:: ``ih-aws resources delete``

    A ``ih-aws resources delete`` subcommand.

    See ``ih-aws resources delete --help`` for more details.
"""

import sys
from logging import getLogger

import click
from botocore.exceptions import ClientError

from infrahouse_toolkit.aws.resource_discovery import (
    find_resources_by_tags,
    resource_for_arn,
)
from infrahouse_toolkit.cli.ih_aws.cmd_resources.tag_filters import build_tag_filters

LOG = getLogger(__name__)


@click.command(name="delete")
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
    "--yes",
    "-y",
    is_flag=True,
    default=False,
    help="Non-interactive mode — delete all matching resources without prompting.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be deleted without actually deleting anything.",
)
@click.pass_context
def cmd_delete(  # pylint: disable=too-many-arguments,too-many-locals,too-many-branches
    ctx: click.Context, tags: tuple, service: str, environment: str, yes: bool, dry_run: bool
) -> None:
    """
    Delete AWS resources matching the given tag filters.

    By default the command prompts interactively for each resource.
    Use ``--yes`` to skip prompts or ``--dry-run`` to preview without deleting.
    """
    tag_filters = build_tag_filters(tags, service, environment)
    if not tag_filters:
        raise click.UsageError("At least one tag filter is required.  Use --tag, --service, or --environment.")

    aws_session = ctx.obj["aws_session"]

    try:
        resources = find_resources_by_tags(aws_session, tag_filters, verify=True)
    except ClientError as exc:
        LOG.error("AWS error: %s", exc)
        sys.exit(1)

    existing = [r for r in resources if r["exists"]]
    if not existing:
        click.echo("No existing resources found.")
        return

    click.echo(f"Found {len(existing)} resource(s) to delete.\n")

    if dry_run:
        click.echo("Dry run — the following resources would be deleted:\n")
        for item in existing:
            click.echo(f"  {item['arn']}")
            for key, value in sorted(item["tags"].items()):
                click.echo(f"    {key}: {value}")
            click.echo("")
        return

    deleted_count = 0
    failed_count = 0
    skipped_count = 0

    for idx, item in enumerate(existing, 1):
        arn = item["arn"]
        click.echo(f"[{idx}/{len(existing)}] {arn}")
        for key, value in sorted(item["tags"].items()):
            click.echo(f"    {key}: {value}")

        if not yes:
            response = click.prompt("  Delete this resource? [y/n/q]", type=str, default="n")
            response = response.strip().lower()
            if response in ("q", "quit"):
                click.echo("  Quitting deletion mode.")
                break
            if response not in ("y", "yes"):
                click.echo("  Skipped.\n")
                skipped_count += 1
                continue

        resource = resource_for_arn(arn, region=aws_session.region_name, session=aws_session)
        if resource is None:
            click.echo(f"  SKIPPED: no resource class available for {arn}\n")
            skipped_count += 1
            continue

        click.echo("  Deleting ...")
        try:
            resource.delete()
            click.echo(f"  OK: {type(resource).__name__} deleted.\n")
            deleted_count += 1
        except ClientError as exc:
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            click.echo(f"  FAILED: {error_msg}\n")
            failed_count += 1

    click.echo(f"Done. Deleted {deleted_count}, failed {failed_count}, skipped {skipped_count}.")
