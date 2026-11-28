output "asg_name" {
  description = "Name of the jumphost's Auto Scaling group."
  value       = module.jumphost.jumphost_asg_name
}

output "toolkit_version" {
  description = "The infrahouse-toolkit version the instance is pinned to."
  value       = var.toolkit_version
}
