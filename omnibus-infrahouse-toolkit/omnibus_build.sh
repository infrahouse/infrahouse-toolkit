#!/usr/bin/env bash

set -eux

PROJECT="infrahouse-toolkit"

cd /$PROJECT/omnibus-$PROJECT

bundle install --binstubs
omnibus build $PROJECT
