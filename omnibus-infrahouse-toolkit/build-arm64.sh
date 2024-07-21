#!/usr/bin/env bash

set -eux

for os in "noble" "jammy" "focal"
do
    export OS_VERSION=$os
    make clean
    make package
    docker run --rm \
        --privileged \
        $(ih-aws --aws-profile AWSAdministratorAccess-493370826424 credentials --docker) \
        -v $PWD:/infrahouse-toolkit \
        -w /infrahouse-toolkit \
        ubuntu:noble bash /infrahouse-toolkit/omnibus-infrahouse-toolkit/upload-arm64.sh $os
done
