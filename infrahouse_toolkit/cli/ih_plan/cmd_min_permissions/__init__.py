"""
.. topic:: ``ih-plan min-permissions``

    A ``ih-plan min-permissions`` subcommand.

    See ``ih-plan min-permissions --help`` for more details.
"""
import json
from copy import deepcopy
from json import JSONDecodeError

import click

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING


@click.command(name="min-permissions")
@click.option("--existing-actions", help="A file with permissions.", default=None)
@click.argument("trace_file")
def cmd_min_permissions(existing_actions, trace_file):
    """
    Parse Terraform trace file and produce an action list from the trace.

    The trace file contains entries with AWS actions. The command
    finds the actions and AWS services to generate a list that
    you can add to an AWS policy.
    It's useful to prepare the least privileges policy.

    The output looks similar to this:

    \b
    [
        "ec2:DeleteNatGateway",
        "ec2:DescribeAddresses",
        "ec2:DescribeInternetGateways",
        "ec2:DescribeNatGateways",
    ]

    """
    actions = []
    if existing_actions:
        with open(existing_actions, encoding=DEFAULT_OPEN_ENCODING) as f_desc:
            actions = json.loads(f_desc.read())

    old_actions = deepcopy(actions)
    initial_count = len(old_actions)

    print(f"## Existing {initial_count} actions:")
    print(json.dumps(sorted(old_actions), indent=4))

    with open(trace_file, encoding=DEFAULT_OPEN_ENCODING) as f_decs:
        for line in f_decs.readlines():
            try:
                operation = json.loads(line)
                if "aws.operation" in operation:
                    actions.append(f'{operation["aws.service"].lower()}:{operation["aws.operation"]}')
            except JSONDecodeError:
                pass

    new_actions = list(set(actions))
    final_count = len(new_actions)
    print(f"## {final_count - initial_count} new action(s):")
    print(json.dumps([x for x in new_actions if x not in old_actions], indent=4))

    print(f"## Old and new actions together, {final_count} in total:")
    print(json.dumps(sorted(list(set(actions))), indent=4))
