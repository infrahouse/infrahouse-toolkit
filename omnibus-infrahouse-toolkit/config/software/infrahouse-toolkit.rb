#
# Copyright 2023 InfraHouse Inc.
#
# All Rights Reserved.
#


# These options are required for all software definitions
name 'infrahouse-toolkit'

license 'Apache-2.0'
license_file 'LICENSE'
skip_transitive_dependency_licensing true

dependency 'python'

source path: '/infrahouse-toolkit'

relative_path 'infrahouse-toolkit'

scripts_dir = '/usr/local/bin'

build do
  # Setup a default environment from Omnibus - you should use this Omnibus
  # helper everywhere. It will become the default in the future.
  env = with_standard_compiler_flags(with_embedded_path)

  command "#{install_dir}/embedded/bin/pip3 --cert #{install_dir}/embedded/ssl/cert.pem install -I .", env: env
  link "#{install_dir}/embedded/bin/ih-aws", "#{scripts_dir}/ih-aws"
  link "#{install_dir}/embedded/bin/ih-certbot", "#{scripts_dir}/ih-certbot"
  link "#{install_dir}/embedded/bin/ih-ec2", "#{scripts_dir}/ih-ec2"
  link "#{install_dir}/embedded/bin/ih-elastic", "#{scripts_dir}/ih-elastic"
  link "#{install_dir}/embedded/bin/ih-github", "#{scripts_dir}/ih-github"
  link "#{install_dir}/embedded/bin/ih-openvpn", "#{scripts_dir}/ih-openvpn"
  link "#{install_dir}/embedded/bin/ih-plan", "#{scripts_dir}/ih-plan"
  link "#{install_dir}/embedded/bin/ih-puppet", "#{scripts_dir}/ih-puppet"
  link "#{install_dir}/embedded/bin/ih-registry", "#{scripts_dir}/ih-registry"
  link "#{install_dir}/embedded/bin/ih-s3", "#{scripts_dir}/ih-s3"
  link "#{install_dir}/embedded/bin/ih-s3-reprepro", "#{scripts_dir}/ih-s3-reprepro"
  link "#{install_dir}/embedded/bin/ih-secrets", "#{scripts_dir}/ih-secrets"
  link "#{install_dir}/embedded/bin/ih-skeema", "#{scripts_dir}/ih-skeema"
  command "#{install_dir}/embedded/bin/python3 omnibus-infrahouse-toolkit/update_bash_completion.py"
  copy "/tmp/infrahouse-completion", "/etc/bash_completion.d/infrahouse-completion"
end
