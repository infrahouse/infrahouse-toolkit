#
# Copyright 2023 InfraHouse Inc.
#
# All Rights Reserved.
#


# These options are required for all software definitions
name "libreadline7"
default_version "7.0"

version("7.0") { source sha256: "750d437185286f40a369e1e4f4764eda932b9459b5ec9a731628393dd3d32334" }

source url: "http://archive.ubuntu.com/ubuntu/pool/main/r/readline/readline_#{version}.orig.tar.gz"

license "GNU"
license_file "README"
skip_transitive_dependency_licensing true

relative_path "readline-#{version}"

build do

  env = with_standard_compiler_flags
  configure env: env

  make "-j #{workers}", env: env
  make "-j #{workers} install", env: env
end
