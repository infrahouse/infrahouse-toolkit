"""
.. topic:: ``ih-elastic snapshots policy``

    A ``ih-elastic snapshots policy`` subcommand.

    See ``ih-elastic snapshots policy --help`` for more details.
"""

import json
from logging import getLogger

import click
import requests

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING

LOG = getLogger()


@click.command(name="policy")
@click.argument("policy_path")
@click.pass_context
def cmd_policy(ctx, **kwargs):
    """
    Apply a snapshot policy from a specified JSON file.

    Example of the policy definition:

    \b
    {
      "daily-snapshots": {
        "policy": {
          "name": "<daily-snap-{now/d}>",
          "schedule": "0 30 1 * * ?",
          "repository": "backups",
          "config": {
            "feature_states": [],
            "include_global_state": true
          },
          "retention": {
            "expire_after": "14d",
            "min_count": 2,
            "max_count": 14
          }
        }
      },
      "hourly-snapshots": {
        "policy": {
          "name": "<hourly-snap-{now/H}>",
          "schedule": "0 0 * * * ?",
          "repository": "backups",
          "config": {
            "feature_states": [],
            "include_global_state": true
          },
          "retention": {
            "expire_after": "48h",
            "min_count": 1,
            "max_count": 48
          }
        }
      }
    }
    """
    url = ctx.obj["url"]
    request_kwargs = {"auth": ctx.obj["auth"], "headers": {"Content-Type": "application/json"}, "timeout": 10}

    with open(kwargs["policy_path"], encoding=DEFAULT_OPEN_ENCODING) as fd:
        for policy_name, item in json.load(fd).items():
            uri = f"_slm/policy/{policy_name}"
            full_url = f"{url}/{uri.lstrip('/')}"
            policy_desired = item["policy"]
            LOG.debug("Sending request %s", full_url)
            response = requests.get(full_url, **request_kwargs)

            if response.status_code == 404:
                LOG.debug("Policy %s does not exist", policy_name)
                LOG.debug("Sending request %s", full_url)
                response = requests.put(full_url, **request_kwargs, data=json.dumps(policy_desired))
                LOG.debug(json.dumps(response.json(), indent=4))

            else:
                policy_actual = response.json()[policy_name]["policy"]
                LOG.debug("Desired policy %s:\n%s", policy_name, json.dumps(policy_desired, indent=4))
                LOG.debug("Actual policy %s:\n%s", policy_name, json.dumps(policy_actual, indent=4))

                if policy_actual != policy_desired:
                    LOG.debug("Policies do not match")
                    LOG.debug("Sending request %s", full_url)
                    response = requests.put(full_url, **request_kwargs, data=json.dumps(policy_desired))
                    LOG.debug(json.dumps(response.json(), indent=4))
                else:
                    LOG.debug("Policies do match")
