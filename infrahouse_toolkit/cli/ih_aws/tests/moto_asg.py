"""An autoscaling group in moto, for ``ih-aws autoscaling`` tests."""

from typing import Dict, List

import boto3

REGION = "us-east-1"


class MotoASG:
    """
    An autoscaling group with running instances. Create it while moto is active.

    :param image_id: AMI for the instances.
    :type image_id: str
    :param name: Group name. The launch template gets the same name.
    :type name: str
    :param size: Number of instances.
    :type size: int
    """

    def __init__(self, image_id: str, name: str = "web", size: int = 2):
        self._name = name
        self._autoscaling = boto3.client("autoscaling", region_name=REGION)
        boto3.client("ec2", region_name=REGION).create_launch_template(
            LaunchTemplateName=name, LaunchTemplateData={"ImageId": image_id, "InstanceType": "t3.micro"}
        )
        self._autoscaling.create_auto_scaling_group(
            AutoScalingGroupName=name,
            LaunchTemplate={"LaunchTemplateName": name},
            MinSize=size,
            MaxSize=size,
            DesiredCapacity=size,
            AvailabilityZones=[f"{REGION}a"],
        )

    @property
    def instance_ids(self) -> List[str]:
        """
        :return: Ids of the group's instances.
        """
        return list(self.scale_in_protection)

    @property
    def name(self) -> str:
        """
        :return: Group name.
        """
        return self._name

    @property
    def scale_in_protection(self) -> Dict[str, bool]:
        """
        :return: Whether each instance is protected from scale-in, by instance id, as moto records it.
        """
        groups = self._autoscaling.describe_auto_scaling_groups(AutoScalingGroupNames=[self._name])
        return {
            instance["InstanceId"]: instance["ProtectedFromScaleIn"]
            for instance in groups["AutoScalingGroups"][0]["Instances"]
        }

    def protect_all(self, protected: bool) -> None:
        """
        Set the scale-in protection of every instance in the group.

        :param protected: True to protect the instances, False to release them.
        :type protected: bool
        """
        self._autoscaling.set_instance_protection(
            AutoScalingGroupName=self._name, InstanceIds=self.instance_ids, ProtectedFromScaleIn=protected
        )
