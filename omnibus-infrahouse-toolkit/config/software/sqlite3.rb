#
# Copyright 2023 InfraHouse Inc.
#
# All Rights Reserved.
#


# These options are required for all software definitions
name 'sqlite3'

license 'Apache-2.0'
license_file 'LICENSE'
skip_transitive_dependency_licensing true
dependency "libreadline7"

default_version "3.33.0"
version("3.33.0") { source sha256: "106a2c48c7f75a298a7557bcc0d5f4f454e5b43811cc738b7ca294d6956bbb15" }

source url: "https://src.fedoraproject.org/repo/pkgs/sqlite/sqlite-autoconf-3330000.tar.gz/sha512/c0d79d4012a01f12128ab5044b887576a130663245b85befcc0ab82ad3a315dd1e7f54b6301f842410c9c21b73237432c44a1d7c2fe0e0709435fec1f1a20a11/sqlite-autoconf-3330000.tar.gz"

relative_path "sqlite-autoconf-3330000"

build do
  # Setup a default environment from Omnibus - you should use this Omnibus
  # helper everywhere. It will become the default in the future.
  env = with_standard_compiler_flags(with_embedded_path)

  configure env: env
  make "-j #{workers}", env: env
  make "-j #{workers} install", env: env
end
