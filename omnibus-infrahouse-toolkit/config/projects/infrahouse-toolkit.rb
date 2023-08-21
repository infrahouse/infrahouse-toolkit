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

build_version '2.3.0'
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
extra_package_file "#{scripts_dir}/ih-plan"
extra_package_file "#{scripts_dir}/ih-s3-reprepro"
extra_package_file "#{scripts_dir}/ih-puppet"

exclude "**/.git"
exclude "**/bundler/git"
