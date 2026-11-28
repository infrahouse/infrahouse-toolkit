locals {
  environment       = "development"
  testing_repo_host = trimsuffix(trimprefix(var.testing_repo_url, "https://"), "/")
  # The canary sources line from packaging/README.md ("Canary node"). cloud-init replaces $KEY_FILE with the
  # keyring it writes the key below to.
  testing_repo_source = "deb [signed-by=$KEY_FILE] ${var.testing_repo_url} ${var.testing_repo_codename} main"
  # Puppet installs the toolkit with `ensure => latest` (profile::infrahouse_toolkit in puppet-code), so on its first
  # run it would replace any version but the newest of both repositories, and a candidate published during the test
  # would replace the one under test. A pin above 1000 makes apt's candidate exactly this version: cloud-init installs
  # it, Puppet finds nothing newer, and the replacement instance installs it too.
  toolkit_pin = <<-EOT
    Package: infrahouse-toolkit
    Pin: version ${var.toolkit_version}
    Pin-Priority: 1001
  EOT
}

# The testing repository is signed with the release key, which it also serves.
data "http" "testing_repo_key" {
  url = "${var.testing_repo_url}DEB-GPG-KEY-${local.testing_repo_host}"

  lifecycle {
    postcondition {
      condition     = self.status_code == 200 && strcontains(self.response_body, "BEGIN PGP PUBLIC KEY BLOCK")
      error_message = "Couldn't download the testing repository's key from ${self.url}: HTTP ${self.status_code}."
    }
  }
}

# One instance, the canary role in production. Pinned to the version pytest-infrahouse's jumphost fixture deploys.
module "jumphost" {
  source  = "registry.infrahouse.com/infrahouse/jumphost/aws"
  version = "6.1.1"

  environment              = local.environment
  subnet_ids               = var.subnet_private_ids
  nlb_subnet_ids           = var.subnet_public_ids
  route53_zone_id          = var.test_zone_id
  alarm_emails             = ["devnull@infrahouse.com"]
  asg_min_size             = 1
  asg_max_size             = 1
  puppet_hiera_config_path = "/opt/infrahouse-puppet-data/environments/${local.environment}/hiera.yaml"
  packages = [
    "infrahouse-puppet-data"
  ]
  extra_repos = {
    infrahouse-testing = {
      source = local.testing_repo_source
      key    = data.http.testing_repo_key.response_body
    }
  }
  extra_files = [
    {
      path        = "/etc/apt/preferences.d/infrahouse-toolkit-under-test.pref"
      content     = local.toolkit_pin
      permissions = "0644"
    }
  ]
  extra_policies = {
    cancel_instance_refresh = aws_iam_policy.cancel_instance_refresh.arn
  }
}
