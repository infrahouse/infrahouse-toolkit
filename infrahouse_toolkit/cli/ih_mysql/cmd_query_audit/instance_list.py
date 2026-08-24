"""
DB instance listing for the ``query-audit`` commands.

Lets ``status`` and ``capture`` answer a missing ``INSTANCE_ID`` with the
choices instead of a bare usage error.  The table matches the format
``ih-ec2 list`` uses for EC2 instances.
"""

from logging import getLogger
from typing import List, Optional

import click
from tabulate import tabulate

from infrahouse_toolkit.aws.rds import RDSMySQLInstance

LOG = getLogger(__name__)


class InstanceList:
    """
    The RDS for MySQL instances in a region.

    :param session: Authenticated boto3 session.
    :type session: Session
    :param region: AWS region.
    :type region: str
    """

    def __init__(self, session, region: str = None) -> None:
        self._session = session
        self._region = region
        self._instances: Optional[List[RDSMySQLInstance]] = None

    # --- Public properties ---

    @property
    def instances(self) -> List[RDSMySQLInstance]:
        """
        :return: MySQL DB instances in the region, ordered by identifier.
        :rtype: List[RDSMySQLInstance]
        """
        if self._instances is None:
            self._instances = RDSMySQLInstance.list_instances(session=self._session, region=self._region)
        return self._instances

    @property
    def table(self) -> str:
        """
        The instances, formatted the way ``ih-ec2 list`` formats EC2 instances.

        :return: A rendered table.
        :rtype: str
        """
        rows = [
            [
                instance.tags.get("Name") or instance.tags.get("service"),
                instance.db_instance_id,
                f"{instance.engine} {instance.engine_version}",
                instance.description["DBInstanceClass"],
                instance.status,
            ]
            for instance in self.instances
        ]
        return tabulate(
            rows,
            headers=["Name", "DBInstanceIdentifier", "Engine", "DBInstanceClass", "State"],
            tablefmt="outline",
        )

    # --- Public methods ---

    def require(self, instance_id: str) -> RDSMySQLInstance:
        """
        Resolve *instance_id*, or fail with the list of valid identifiers.

        :param instance_id: DB instance identifier, or ``None`` when the
            argument was omitted.
        :type instance_id: str
        :return: The named instance.
        :rtype: RDSMySQLInstance
        :raises click.UsageError: If *instance_id* is missing.
        """
        if instance_id:
            return RDSMySQLInstance(instance_id, region=self._region, session=self._session)

        if not self.instances:
            raise click.UsageError(
                "Missing argument 'INSTANCE_ID', and no RDS for MySQL instances were found. "
                "Check --aws-profile and --aws-region."
            )
        raise click.UsageError(f"Missing argument 'INSTANCE_ID'. Pick one of:\n\n{self.table}")
