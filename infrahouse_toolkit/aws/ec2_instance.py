"""
Module for EC2Instance class - a class tha represents an EC2 instance.
"""

from logging import getLogger

from cached_property import cached_property_with_ttl
from ec2_metadata import ec2_metadata

from infrahouse_toolkit.aws import get_client

LOG = getLogger()


class EC2Instance:
    """
    EC2Instance represents an EC2 instance.

    :param instance_id: Instance id. If omitted, the local instance is read from metadata.
    :type instance_id: str
    """

    def __init__(self, instance_id: str = None):
        self._instance_id = instance_id

    @property
    def availability_zone(self) -> str:
        """
        :return: Availability zone where this instance is hosted.
        """
        return ec2_metadata.availability_zone

    @property
    def instance_id(self) -> str:
        """
        :return: The instance's instance_id. It's read from metadata
            if the class instance was created w/o specifying it.
        """
        if self._instance_id is None:
            self._instance_id = ec2_metadata.instance_id
        return self._instance_id

    @property
    def state(self) -> str:
        """
        :return: EC2 instance state e.g. ``Running``, ``Terminated``, etc.
        """
        return self._describe_instance["State"]["Name"]

    @property
    def tags(self) -> dict:
        """
        :return: A dictionary with the instance tags. Keys are tag names, and values - the tag values.
        """
        return {tag["Key"]: tag["Value"] for tag in self._describe_instance["Tags"]}

    @property
    def _ec2_client(self):
        return get_client("ec2")

    @cached_property_with_ttl(ttl=10)
    def _describe_instance(self):
        return self._ec2_client.describe_instances(
            InstanceIds=[
                self.instance_id,
            ],
        )[
            "Reservations"
        ][0][
            "Instances"
        ][0]
