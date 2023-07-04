"""
.. topic:: ``ih-plan min-permissions``

    A ``ih-plan min-permissions`` subcommand.

    See ``ih-plan min-permissions --help`` for more details.
"""
import json
from json import JSONDecodeError

import click

from infrahouse_toolkit import DEFAULT_OPEN_ENCODING


@click.command(name="min-permissions")
@click.argument("trace_file")
def cmd_min_permissions(trace_file):
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
    with open(trace_file, encoding=DEFAULT_OPEN_ENCODING) as f_decs:
        for line in f_decs.readlines():
            try:
                operation = json.loads(line)
                if "aws.operation" in operation:
                    actions.append(f'{operation["aws.service"].lower()}:{operation["aws.operation"]}')
            except JSONDecodeError:
                pass

    print(json.dumps(sorted(list(set(actions))), indent=4))
