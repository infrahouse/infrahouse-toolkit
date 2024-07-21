#!/usr/bin/env bash

set -eux
codename=$1

# Install dependencies

apt-get update
apt-get -y install gpg lsb-release curl


# Add a GPG public key to verify InfraHouse packages

mkdir -p /etc/apt/cloud-init.gpg.d/
curl  -fsSL "https://release-$(lsb_release -cs).infrahouse.com/DEB-GPG-KEY-release-$(lsb_release -cs).infrahouse.com" \
    | gpg --dearmor -o /etc/apt/cloud-init.gpg.d/infrahouse.gpg


# Add the InfraHouse repository source

echo "deb [signed-by=/etc/apt/cloud-init.gpg.d/infrahouse.gpg] https://release-$(lsb_release -cs).infrahouse.com/ $(lsb_release -cs) main" \
    > /etc/apt/sources.list.d/infrahouse.list

apt-get update

apt-get -y install infrahouse-toolkit

ih-s3-reprepro \
    --debug \
    --bucket infrahouse-release-"$codename" \
    --gpg-key-secret-id packager-key-"$codename" \
    --gpg-passphrase-secret-id packager-passphrase-"$codename" \
    includedeb \
    "$codename" \
    omnibus-infrahouse-toolkit/pkg/infrahouse-toolkit_*.deb
