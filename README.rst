==================
InfraHouse Toolkit
==================


.. image:: https://img.shields.io/pypi/v/infrahouse_toolkit.svg
        :target: https://pypi.python.org/pypi/infrahouse_toolkit

.. image:: https://readthedocs.org/projects/infrahouse-toolkit/badge/?version=latest
        :target: https://infrahouse-toolkit.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status

.. image:: https://app.codacy.com/project/badge/Grade/26f8863a19434e3fb578bfa254328e9d
    :target: https://app.codacy.com/gh/infrahouse/infrahouse-toolkit/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade

A collection of tools for building infrastructure.


* Free software: Apache Software License 2.0
* Documentation: https://infrahouse-toolkit.readthedocs.io.


Features
--------

``ih-plan``
~~~~~~~~~~~
``ih-plan`` is a helper tool to upload/download a Terraform plan.

::

    $ ih-plan --help
    Usage: ih-plan [OPTIONS] COMMAND [ARGS]...

      Terraform plan helpers.

    Options:
      --bucket TEXT               AWS S3 bucket name to upload/download the plan.
                                  By default, parse Terraform backend
                                  configuration (see --tf-backend-file) in the
                                  current directory.
      --aws-assume-role-arn TEXT  ARN of a role the AWS client should assume.
      --tf-backend-file TEXT      File with Terraform backend configuration.
                                  [default: terraform.tf]
      --version                   Show the version and exit.
      --help                      Show this message and exit.

    Commands:
      download         Download a file from an S3 bucket.
      min-permissions  Parse Terraform trace file and produce an action list...
      publish          Publish Terraform plan to GitHub pull request.
      remove           Remove a file from an S3 bucket.
      upload           Upload a plan file to an S3 bucket.

Commands ``upload``, ``download``, ``remove`` manipulate with plan files on S3.

Command ``publish`` prepares a nicely formatted Terraform plan to a pull request so a reviewer
can make an informed decision approving a change.

Command ``min-permissions`` parses a Terraform trace and figures out the minimal set of permissions
needed to execute the plan. Say, you want to reduce permissions of a role running terraform.
That's the use-case.

``ih-s3-reprepro``
~~~~~~~~~~~~~~~~~~
Manage Debian repository in an S3 bucket.

Basically, it's a cloud version of the good old ``reprepro``.

``ih-s3-reprepro`` uses ``reprepro`` underneath plus it adds wrappers around S3 and GPG.
The Debian repository is stored in an S3 bucket. ``ih-s3-reprepro`` mounts the S3 bucket it locally,
pulls a GPG private key from AWS's secretsmanager and configures the GPG home environment.

::

    $ ih-s3-reprepro --help
    Usage: ih-s3-reprepro [OPTIONS] COMMAND [ARGS]...

      Tool to manage deb packages to a Debian repository hosted in an S3 bucket.

    Options:
      --bucket TEXT                   AWS S3 bucket with a Debian repo  [required]
      --role-arn TEXT                 Assume this role for all AWS operations
      --gpg-key-secret-id TEXT        AWS secrets manager secret name that stores
                                      a GPG private key.
      --gpg-passphrase-secret-id TEXT
                                      AWS secrets manager secret name that stores
                                      a passphrase to the GPG key.
      --help                          Show this message and exit.

    Commands:
      check               Check for all needed files to be registered properly.
      checkpool           Check if all files in the pool are still in proper...
      deleteunreferenced  Remove all known files (and forget them) in the...
      dumpunreferenced    Print a list of all filed believed to be in the...
      includedeb          Include the given binary package.
      list                List all packages by the given name occurring in...
      remove              Delete all packages in the specified distribution,...


Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
