"""
Module for ASGInstance class - a class to describe and work with
an instance that is a part of an Autoscaling group.
"""

from cached_property import cached_property_with_ttl

from infrahouse_toolkit.aws import get_client
from infrahouse_toolkit.aws.ec2_instance import EC2Instance


class ASGInstance(EC2Instance):
    """
    ASGInstance is an EC2 instance that is a part of an autoscaling group.
    Because it's an EC2 instance, ASGInstance inherits EC2Instance.
    """

    @property
    def lifecycle_state(self) -> str:
        """
        :return: Lifecycle state of the instance.
            See https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-lifecycle.html
            for possible values.
        """
        return self._describe_auto_scaling_instance["LifecycleState"]

    @property
    def asg_name(self) -> str:
        """
        :return: Name of an autoscaling group that this instance is a part of.
        """
        return self.tags["aws:autoscaling:groupName"]

    def mark_unhealthy(self):
        """Tell the autoscaling group that this instance is not healthy
        and should be replaced."""
        self._autoscaling_client.set_instance_health(
            InstanceId=self.instance_id,
            HealthStatus="Unhealthy",
        )

    @property
    def _autoscaling_client(self):
        return get_client("autoscaling")

    @cached_property_with_ttl(ttl=10)
    def _describe_auto_scaling_instance(self):
        return self._autoscaling_client.describe_auto_scaling_instances(
            InstanceIds=[
                self.instance_id,
            ],
        )[
            "AutoScalingInstances"
        ][0]
