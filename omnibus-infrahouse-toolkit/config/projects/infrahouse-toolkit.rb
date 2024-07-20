#
# Copyright 2023 InfraHouse Inc.
#
# All Rights Reserved.
#

name "infrahouse-toolkit"
maintainer "InfraHouse Inc."
homepage "https://infrahouse.com"

# Defaults to C:/infrahouse-toolkit on Windows
# and /opt/infrahouse-toolkit on all other platforms
install_dir "#{default_root}/#{name}"

build_version '2.27.0'
build_iteration 1

override :openssl, version: '1.1.1t'

# Creates required build directories
dependency "preparation"

# infrahouse-toolkit dependencies/components
dependency 'infrahouse-toolkit'
runtime_dependency 'reprepro'
runtime_dependency 'gpg'
runtime_dependency 's3fs'
runtime_dependency 'puppet-agent'

scripts_dir = '/usr/local/bin'
extra_package_file "#{scripts_dir}/ih-aws"
extra_package_file "#{scripts_dir}/ih-certbot"
extra_package_file "#{scripts_dir}/ih-ec2"
extra_package_file "#{scripts_dir}/ih-elastic"
extra_package_file "#{scripts_dir}/ih-github"
extra_package_file "#{scripts_dir}/ih-plan"
extra_package_file "#{scripts_dir}/ih-registry"
extra_package_file "#{scripts_dir}/ih-puppet"
extra_package_file "#{scripts_dir}/ih-s3-reprepro"
extra_package_file "#{scripts_dir}/ih-secrets"
extra_package_file "#{scripts_dir}/ih-skeema"
extra_package_file "/etc/bash_completion.d/infrahouse-completion"

exclude "**/.git"
exclude "**/bundler/git"
