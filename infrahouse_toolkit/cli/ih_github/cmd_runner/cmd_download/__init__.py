"""
.. topic:: ``ih-github runner download``

    A ``ih-github runner download`` subcommand.

    See ``ih-github runner download --help`` for more details.
"""

import json
import logging
import sys

import click
from requests import get

LOG = logging.getLogger()


@click.command(
    name="download",
)
@click.option(
    "--os",
    help="Operating system",
    type=click.Choice(["linux", "osx", "win"]),
    default="linux",
    show_default=True,
)
@click.option(
    "--arch",
    help="Architecture",
    type=click.Choice(["arm", "arm64", "x64"]),
    default="x64",
    show_default=True,
)
@click.argument(
    "dest_file",
    required=False,
)
def cmd_download(**kwargs):
    """
    Download an actions-runner release tar-ball.
    """
    response = get(
        "https://api.github.com/repos/actions/runner/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    response.raise_for_status()
    for asset in response.json()["assets"]:
        if f"-{kwargs['os']}-" in asset["name"] and f"-{kwargs['arch']}-" in asset["name"]:
            dest_file = kwargs["dest_file"] or asset["name"]
            LOG.debug("Saving %s in %s", asset["name"], dest_file)
            LOG.debug("Found asset: %s", json.dumps(asset, indent=4))
            download_file(asset["browser_download_url"], dest_file)
            LOG.info("Saved %s", dest_file)
            sys.exit(0)

    LOG.error("Actions runner for %s-%s not found.", kwargs["os"], kwargs["arch"])
    sys.exit(1)


def download_file(url: str, dst: str):
    """
    Download a file from a URL to a local destination file.

    :param url: URL of the file to download
    :param dst: Local path to save the downloaded file
    """
    # Make a GET request to the server
    with get(url, stream=True, timeout=30) as response:
        # Check if the request was successful
        response.raise_for_status()

        # Open the destination file in binary write mode
        with open(dst, "wb") as file:
            # Iterate over the content in chunks
            for chunk in response.iter_content(chunk_size=8192):
                # Write each chunk to the file
                if chunk:  # filter out keep-alive new chunks
                    file.write(chunk)
