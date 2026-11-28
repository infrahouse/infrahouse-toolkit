"""
The integration test (IH-192): a fresh instance boots and runs Puppet with the infrahouse-toolkit candidate, in AWS.

``make test-integration`` runs it. It deploys terraform-aws-jumphost with the testing apt repository, so the instance
installs a candidate, and checks the boot, the package, Puppet, Puppet's failure path and a replacement. See
"Integration test" in ``packaging/README.md``.
"""
