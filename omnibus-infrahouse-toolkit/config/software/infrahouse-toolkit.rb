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
  link "#{install_dir}/embedded/bin/ih-plan", "#{scripts_dir}/ih-plan"
  link "#{install_dir}/embedded/bin/ih-s3-reprepro", "#{scripts_dir}/ih-s3-reprepro"
  link "#{install_dir}/embedded/bin/ih-puppet", "#{scripts_dir}/ih-puppet"
end
