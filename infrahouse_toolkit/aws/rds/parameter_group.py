"""
RDS DB parameter group.

Provides :class:`RDSParameterGroup` — a thin, read-mostly view over an RDS DB
parameter group with the ability to apply and roll back a set of dynamic
parameters.

Parameter groups are the only way to change server variables on RDS: the master
user normally lacks ``SYSTEM_VARIABLES_ADMIN``, so ``SET GLOBAL`` is unavailable,
and even where it works RDS re-applies parameter group values behind you.
"""

from logging import getLogger
from typing import Dict, List, Optional

from botocore.exceptions import ClientError
from infrahouse_core.aws.base import AWSResource

from infrahouse_toolkit.aws.rds.exceptions import RDSParameterError

LOG = getLogger(__name__)


class RDSParameterGroup(AWSResource):
    """
    An RDS DB parameter group.

    :param name: DB parameter group name.
    :type name: str
    :param region: AWS region.
    :type region: str
    :param role_arn: IAM role ARN for cross-account access.
    :type role_arn: str
    :param session: Pre-configured boto3 session.
    :type session: Session
    """

    def __init__(self, name: str, region: str = None, role_arn: str = None, session=None) -> None:
        super().__init__(name, "rds", region=region, role_arn=role_arn, session=session)
        self._description: Optional[dict] = None
        self._parameters: Optional[Dict[str, dict]] = None

    # --- Public properties ---

    @property
    def attached_instance_ids(self) -> List[str]:
        """
        Identifiers of every DB instance using this parameter group.

        Modifying a parameter group affects *all* of them.  Attaching a
        different parameter group instead is not a way around that — it
        requires a reboot even when the parameters themselves are dynamic.

        :return: DB instance identifiers.
        :rtype: List[str]
        """
        identifiers = []
        for page in self._client.get_paginator("describe_db_instances").paginate():
            for instance in page["DBInstances"]:
                names = [group["DBParameterGroupName"] for group in instance.get("DBParameterGroups", [])]
                if self._resource_id in names:
                    identifiers.append(instance["DBInstanceIdentifier"])
        return identifiers

    @property
    def description(self) -> dict:
        """
        :return: Raw ``describe_db_parameter_groups`` entry for this group.
        :rtype: dict
        :raises RDSParameterError: If the group does not exist.
        """
        if self._description is None:
            response = self._client.describe_db_parameter_groups(DBParameterGroupName=self._resource_id)
            groups = response["DBParameterGroups"]
            if not groups:
                raise RDSParameterError(f"DB parameter group {self._resource_id} not found")
            self._description = groups[0]
        return self._description

    @property
    def exists(self) -> bool:
        """
        :return: ``True`` if the parameter group exists.
        :rtype: bool
        :raises ClientError: On any RDS API failure other than "not found".
        """
        try:
            self._client.describe_db_parameter_groups(DBParameterGroupName=self._resource_id)
            return True
        except ClientError as err:
            if err.response["Error"]["Code"] == "DBParameterGroupNotFound":
                return False
            raise

    @property
    def family(self) -> str:
        """
        :return: Parameter group family, e.g. ``mysql8.0``.
        :rtype: str
        """
        return self.description["DBParameterGroupFamily"]

    @property
    def is_default(self) -> bool:
        """
        Whether this is an RDS-provided default parameter group.

        Default groups cannot be modified at all, so a capture that needs to
        change parameters must target an instance on a custom group.

        :return: ``True`` for a default group.
        :rtype: bool
        """
        return self._resource_id.startswith("default.")

    @property
    def name(self) -> str:
        """
        :return: DB parameter group name.
        :rtype: str
        """
        return self._resource_id

    @property
    def parameters(self) -> Dict[str, dict]:
        """
        Every parameter in the group, keyed by parameter name.

        Includes engine defaults and RDS system values, not just the
        user-modified ones, so callers can tell "unset, engine default"
        apart from "explicitly set to the same value".

        :return: Parameter name to its ``describe_db_parameters`` entry.
        :rtype: Dict[str, dict]
        """
        if self._parameters is None:
            parameters = {}
            paginator = self._client.get_paginator("describe_db_parameters")
            for page in paginator.paginate(DBParameterGroupName=self._resource_id):
                for parameter in page["Parameters"]:
                    parameters[parameter["ParameterName"]] = parameter
            self._parameters = parameters
        return self._parameters

    # --- Public methods ---

    def apply(self, values: Dict[str, str]) -> None:
        """
        Set parameters to the given values, effective immediately.

        Every parameter is validated first: it must exist in this group's
        family, be modifiable, and be dynamic.  A static parameter would only
        take effect on reboot, which is never what a capture wants — so it is
        rejected rather than silently queued.

        :param values: Parameter name to desired value.
        :type values: Dict[str, str]
        :raises RDSParameterError: If the group is a default group, or any
            parameter is unknown, read-only, or static.
        """
        if self.is_default:
            raise RDSParameterError(
                f"{self._resource_id} is a default parameter group and cannot be modified. "
                f"Attach a custom parameter group to the instance first (this needs a reboot)."
            )

        self.validate_modifiable(list(values))

        payload = [
            {"ParameterName": name, "ParameterValue": str(value), "ApplyMethod": "immediate"}
            for name, value in values.items()
        ]
        LOG.info("Applying to parameter group %s: %s", self._resource_id, values)
        self._client.modify_db_parameter_group(DBParameterGroupName=self._resource_id, Parameters=payload)
        self.refresh()

    def delete(self) -> None:
        """
        Delete the parameter group.

        Idempotent — does nothing if it does not exist.  Note RDS refuses to
        delete a group that is still attached to an instance.

        :raises ClientError: On any RDS API failure other than "not found".
        """
        try:
            self._client.delete_db_parameter_group(DBParameterGroupName=self._resource_id)
            LOG.info("Deleted DB parameter group %s", self._resource_id)
        except ClientError as err:
            if err.response["Error"]["Code"] == "DBParameterGroupNotFound":
                LOG.info("DB parameter group %s does not exist.", self._resource_id)
            else:
                raise

    def refresh(self) -> None:
        """Drop cached parameter group state so the next read hits the API."""
        self._description = None
        self._parameters = None

    def restore(self, snapshot: List[dict]) -> None:
        """
        Roll the group back to a snapshot taken by :meth:`snapshot`.

        Parameters that were explicitly set by a user before the change are set
        back to their previous value.  Parameters that were *not* user-set are
        reset instead of being written with the default value — writing the
        default would leave the group permanently marked as user-modified and
        pinned against future RDS default changes.

        :param snapshot: Output of :meth:`snapshot`.
        :type snapshot: List[dict]
        """
        to_set = {entry["name"]: entry["value"] for entry in snapshot if entry["source"] == "user"}
        to_reset = [entry["name"] for entry in snapshot if entry["source"] != "user"]

        if to_set:
            payload = [
                {"ParameterName": name, "ParameterValue": str(value), "ApplyMethod": "immediate"}
                for name, value in to_set.items()
            ]
            LOG.info("Restoring user values in %s: %s", self._resource_id, to_set)
            self._client.modify_db_parameter_group(DBParameterGroupName=self._resource_id, Parameters=payload)

        if to_reset:
            payload = [{"ParameterName": name, "ApplyMethod": "immediate"} for name in to_reset]
            LOG.info("Resetting to engine defaults in %s: %s", self._resource_id, ", ".join(to_reset))
            self._client.reset_db_parameter_group(DBParameterGroupName=self._resource_id, Parameters=payload)

        self.refresh()

    def snapshot(self, names: List[str]) -> List[dict]:
        """
        Record the current value and origin of the named parameters.

        The origin matters as much as the value: ``source`` is ``user`` when
        somebody set the parameter explicitly, and ``engine-default`` or
        ``system`` when the value is merely inherited.  :meth:`restore` uses
        that distinction to decide between setting and resetting.

        :param names: Parameter names to record.
        :type names: List[str]
        :return: One entry per parameter with ``name``, ``value`` and ``source``.
        :rtype: List[dict]
        :raises RDSParameterError: If a parameter does not exist in this family.
        """
        recorded = []
        for name in names:
            parameter = self.parameters.get(name)
            if parameter is None:
                raise RDSParameterError(f"Parameter {name} does not exist in family {self.family}")
            recorded.append(
                {
                    "name": name,
                    "value": parameter.get("ParameterValue"),
                    "source": parameter.get("Source"),
                }
            )
        return recorded

    def validate_modifiable(self, names: List[str]) -> None:
        """
        Ensure the named parameters can all be changed immediately.

        Checking against the group's own family is what makes this work
        unchanged across engine versions: MySQL 8.0 and 8.4 do not expose the
        same set of parameters, and an unknown name fails here with a clear
        message instead of being silently dropped.

        :param names: Parameter names to check.
        :type names: List[str]
        :raises RDSParameterError: If any parameter is unknown, read-only, or static.
        """
        for name in names:
            parameter = self.parameters.get(name)
            if parameter is None:
                raise RDSParameterError(
                    f"Parameter {name} does not exist in family {self.family}. "
                    f"Engine versions differ in which parameters they expose."
                )
            if not parameter.get("IsModifiable"):
                raise RDSParameterError(f"Parameter {name} is not modifiable on RDS (IsModifiable=false)")
            if parameter.get("ApplyType") != "dynamic":
                raise RDSParameterError(
                    f"Parameter {name} is {parameter.get('ApplyType')}, not dynamic — "
                    f"changing it would require a reboot"
                )

    def value_of(self, name: str) -> Optional[str]:
        """
        :param name: Parameter name.
        :type name: str
        :return: The effective value, or ``None`` when the parameter is unset
            and the engine picks the default at runtime.
        :rtype: Optional[str]
        """
        parameter = self.parameters.get(name)
        return parameter.get("ParameterValue") if parameter else None
