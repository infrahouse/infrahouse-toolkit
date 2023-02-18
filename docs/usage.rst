=====
Usage
=====

The InfraHouse Toolkit comes a a set of tools. All other them have a ``ih-`` prefix.
Use shell completion to get full list of available tools.
Each tool has a ``--help`` message.

.. code-block:: shell

    $ ih-plan --help
    Usage: ih-plan [OPTIONS] COMMAND [ARGS]...

      Terraform plan helpers.

    Options:
      --bucket TEXT           AWS S3 bucket name to upload/download the plan. By
                              default, parse Terraform backend configuration (see
                              --tf-backend-file) in the current directory.
      --tf-backend-file TEXT  File with Terraform backend configuration.
                              [default: terraform.tf]
      --version               Show the version and exit.
      --help                  Show this message and exit.

    Commands:
      download  Download a file from an S3 bucket.
      remove    Remove a file from an S3 bucket.
      upload    Upload a plan file to an S3 bucket.
