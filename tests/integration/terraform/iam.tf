data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Check 4 runs `ih-puppet --cancel-instance-refresh-on-error`, whose child `ih-aws autoscaling
# cancel-instance-refresh` reads the instance's group and cancels its refresh. The jumphost's role can't: production
# jumphosts don't pass that flag. The test grants it the way terraform-aws-elasticsearch grants it to its nodes.
data "aws_iam_policy_document" "cancel_instance_refresh" {
  statement {
    # Describe actions take no resource-level permissions.
    actions   = ["autoscaling:DescribeAutoScalingInstances"]
    resources = ["*"]
  }
  statement {
    actions = ["autoscaling:CancelInstanceRefresh"]
    resources = [
      join(
        ":",
        [
          "arn:aws:autoscaling",
          data.aws_region.current.region,
          data.aws_caller_identity.current.account_id,
          "autoScalingGroup:*:autoScalingGroupName/${module.jumphost.jumphost_asg_name}",
        ]
      )
    ]
  }
}

resource "aws_iam_policy" "cancel_instance_refresh" {
  name_prefix = "toolkit-candidate-cancel-refresh-"
  description = "Lets the toolkit candidate's jumphost cancel its own group's instance refresh (IH-192 check 4)."
  policy      = data.aws_iam_policy_document.cancel_instance_refresh.json
}
