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
    - `Usage examples <https://infrahouse-toolkit.readthedocs.io/en/latest/readme.html#infrahouse-toolkit>`_
    - `Installation <https://infrahouse-toolkit.readthedocs.io/en/latest/installation.html>`_
    - `Code documentation <https://infrahouse-toolkit.readthedocs.io/en/latest/modules.html>`_
    - `Contributing <https://infrahouse-toolkit.readthedocs.io/en/latest/contributing.html>`_

.. contents:: List of tools


``ih-aws``: AWS helpers
-----------------------

The command group to work with AWS services.

``ih-aws credentials``: retrieve temporary AWS credentials
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ih-aws credentials`` authenticates a user in `AWS IAM Identity Center <https://aws.amazon.com/iam/identity-center/>`_
and prints acquired AWS credentials. It is useful when you have configured IAM roles in ~/.aws/config
and boto3 gets short-lived access key.
The command prints the credentials in a format that you can copy&paste for different scenarios.

.. code-block:: bash

    $ ih-aws credentials
    AWS_ACCESS_KEY_ID=ASIAXFXZRL24LGX6JZ5A
    AWS_SECRET_ACCESS_KEY=ILA***********************************GR
    AWS_DEFAULT_REGION=us-west-1
    AWS_SESSION_TOKEN=IQoJb3JpZ2luX2VjEMr...F2Dooyg9dJ0hnVsphfLkA==


With a ``-e`` option, the tool adds the ``export`` keyword in case you want a child process to have access to the credentials

.. code-block:: bash

    $ ih-aws credentials -e
    export AWS_ACCESS_KEY_ID=ASIAXFXZRL24LGX6JZ5A
    export AWS_SECRET_ACCESS_KEY=ILA***********************************GR
    export AWS_DEFAULT_REGION=us-west-1
    export AWS_SESSION_TOKEN=IQoJb3JpZ2luX2VjEMr...F2Dooyg9dJ0hnVsphfLkA==

If you want to pass the AWS credentials to a docker, the ``--docker`` option will generate a command line options to
the ``docker`` command.

.. code-block:: bash

    $ docker run $(ih-aws credentials --docker) amazon/aws-cli \
        sts get-caller-identity
    {
        "UserId": "AROAXFXZRL24IKXUK6SPX:aleks",
        "Account": "493370826424",
        "Arn": "arn:aws:sts::493370826424:assumed-role/AWSReservedSSO_AWSAdministratorAccess_a84a03e62f490b50/aleks"
    }

``ih-aws credentials`` reads ``~/.aws/config`` and can accept a profile from it.

For example, if the config file looks like this

.. code-block:: ini

    ### InfraHouse profiles
    [default]
    sso_session = infrahouse
    sso_account_id = 493370826424
    sso_role_name = AWSAdministratorAccess
    region = us-west-1
    output = json

    [profile AWSAdministratorAccess-493370826424]
    sso_session = infrahouse
    sso_account_id = 493370826424
    sso_role_name = AWSAdministratorAccess
    region = us-west-1
    output = json

    [profile infrahouse-admin-cicd]
    sso_session = infrahouse
    sso_account_id = 303467602807
    sso_role_name = AWSAdministratorAccess
    region = us-west-1
    output = json

then you can get credentials for a specific profile.

.. code-block:: bash

    $ docker run $(ih-aws --aws-profile infrahouse-admin-cicd credentials --docker) \
        amazon/aws-cli sts get-caller-identity
    {
        "UserId": "AROAUNKAUEN3ZL5YKTQ5Z:aleks",
        "Account": "303467602807",
        "Arn": "arn:aws:sts::303467602807:assumed-role/AWSReservedSSO_AWSAdministratorAccess_422821c726d81c14/aleks"
    }

``ih-aws ecs``: ECS helpers
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ih-aws ecs wait-services-stable --help
    Usage: ih-aws ecs wait-services-stable [OPTIONS]

      Wait up to --timeout seconds until all specified services in an ECS cluster
      become stable.

      The service is considered stable when there is only one deployment for it
      and number of running tasks is equal to desired number tasks.

    Options:
      --cluster TEXT          ECS cluster name that runs requested services.
                              [required]
      --service TEXT          ECS service name that we wait to become stable.
                              Multiple services can be specified.  [required]
      --wait-timeout INTEGER  Time in seconds to wait until all services become
                              stable.  [default: 1200]
      --help                  Show this message and exit.

``ih-certbot``: a bundled certbot
---------------------------------

``ih-certbot`` is a wrapper around. InfraHouse Toolkit packages it to avoid installing ``certbot``
in the system Python environment. To see what ``certbot`` provides, get its help.

.. code-block:: bash

    $ ih-certbot -- --help

    - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

      certbot [SUBCOMMAND] [options] [-d DOMAIN] [-d DOMAIN] ...

    Certbot can obtain and install HTTPS/TLS/SSL certificates.  By default,
    it will attempt to use a webserver both for obtaining and installing the
    certificate. The most common SUBCOMMANDS and flags are:

    obtain, install, and renew certificates:
        (default) run   Obtain & install a certificate in your current webserver
        certonly        Obtain or renew a certificate, but do not install it
        renew           Renew all previously obtained certificates that are near
    ....
    More detailed help:

      -h, --help [TOPIC]    print this message, or detailed help on a topic;
                            the available TOPICS are:

       all, automation, commands, paths, security, testing, or any of the
       subcommands or plugins (certonly, renew, install, register, nginx,
       apache, standalone, webroot, etc.)
      -h all                print a detailed help page including all topics
      --version             print the version number
    - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


``ih-ec2``: common EC2 operations
---------------------------------

The ``ih-ec2`` command works with AWS EC2.

.. code-block:: bash

    $ ih-ec2
    Usage: ih-ec2 [OPTIONS] COMMAND [ARGS]...

      AWS EC2 helpers.

    Options:
      --debug                         Enable debug logging.
      --aws-profile [default|AWSAdministratorAccess-493370826424|infrahouse-admin-cicd|...]
                                      AWS profile name for authentication.
      --aws-region [af-south-1|ap-east-1|ap-northeast-1|ap-northeast-2|ap-northeast-3|ap-south-1|ap-southeast-1|ap-southeast-2|ap-southeast-3|ca-central-1|eu-central-1|eu-north-1|eu-south-1|eu-west-1|eu-west-2|eu-west-3|me-south-1|sa-east-1|us-east-1|us-east-2|us-west-1|us-west-2]
                                      AWS region to use.
      --version                       Show the version and exit.
      --help                          Show this message and exit.

    Commands:
      instance-types    Describe AWS EC2 instance types.
      launch            Start an EC2 instance.
      launch-templates  Describe AWS launch-templates.
      list              List created EC2 instances.
      subnets           Describe AWS subnets.
      terminate         Terminate an EC2 instance.

Note, the help message reads your ``~/.aws/config`` and prints available AWS profiles.

``ih-ec2 list``: list EC2 instances
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``ih-ec2 list`` command prints a list of ECS instances in a region.

Without additional options, it shows an instance's Name, PrivateIpAddress, InstanceId, InstanceType, and State.

.. code-block:: bash

    $ ih-ec2 list
    +--------------------+--------------------+---------------------+----------------+---------+
    | Name               | PrivateIpAddress   | InstanceId          | InstanceType   | State   |
    +====================+====================+=====================+================+=========+
    | auth               | 10.0.1.233         | i-053a08fa0f4d583c1 | t3.small       | running |
    | jumphost           | 10.0.1.130         | i-0f7b00928e84b9173 | t3a.micro      | running |
    | mail               | 10.0.3.66          | i-0e1c3c842edc1a43a | t3a.micro      | running |
    | openvpn            | 10.0.1.213         | i-069ff960335c93087 | m6in.large     | running |
    | openvpn-portal     | 10.0.3.177         | i-0a77715da944ed583 | t3.small       | running |
    | terraform-registry | 10.0.3.117         | i-011f470b96279cb89 | t3.micro       | running |
    | webserver          | 10.0.6.203         | i-00eb66708c5108595 | t3.micro       | running |
    | webserver          | 10.0.7.88          | i-0ff80ad49cf5a46ea | t3.micro       | running |
    +--------------------+--------------------+---------------------+----------------+---------+

Should you want to see the instance's public DNS name or IP address, use ``--public-dns-name``
and ``--public-ip-address`` options respectively.

The ``--tags`` option will add formatted instance tags.

.. code-block:: bash

    $ ih-ec2 list --tags
    +--------------------+--------------------+---------------------+----------------+--------------------------------------------------------------------------------+---------+
    | Name               | PrivateIpAddress   | InstanceId          | InstanceType   | Tags                                                                           | State   |
    +====================+====================+=====================+================+================================================================================+=========+
    | auth               | 10.0.1.233         | i-053a08fa0f4d583c1 | t3.small       | {                                                                              | running |
    |                    |                    |                     |                |     "AmazonECSManaged": "true",                                                |         |
    |                    |                    |                     |                |     "account": "493370826424",                                                 |         |
    |                    |                    |                     |                |     "aws:autoscaling:groupName": "auth2024030222363784960000000d",             |         |
    |                    |                    |                     |                |     "aws:ec2launchtemplate:id": "lt-0d93139ab32de43aa",                        |         |
    |                    |                    |                     |                |     "aws:ec2launchtemplate:version": "2",                                      |         |
    |                    |                    |                     |                |     "environment": "development",                                              |         |
    |                    |                    |                     |                |     "managed-by": "terraform",                                                 |         |
    |                    |                    |                     |                |     "service": "auth"                                                          |         |
    |                    |                    |                     |                | }                                                                              |         |
    +--------------------+--------------------+---------------------+----------------+--------------------------------------------------------------------------------+---------+
    | jumphost           | 10.0.1.130         | i-0f7b00928e84b9173 | t3a.micro      | {                                                                              | running |
    |                    |                    |                     |                |     "aws:autoscaling:groupName": "jumphost-20240223005113359100000009-02R7BZ", |         |
    |                    |                    |                     |                |     "aws:ec2launchtemplate:id": "lt-001743d1d2257c40b",                        |         |
    |                    |                    |                     |                |     "aws:ec2launchtemplate:version": "10",                                     |         |
    |                    |                    |                     |                |     "created_by_module": "infrahouse/jumphost/aws"                             |         |
    |                    |                    |                     |                | }                                                                              |         |
    +--------------------+--------------------+---------------------+----------------+--------------------------------------------------------------------------------+---------+

It is possible to filter output based on a tag value, multiple values or its existence.

To print instances that have a ``service`` tag with any value.

.. code-block:: bash

    $ ih-ec2 list --tags --service
    +--------------------+--------------------+---------------------+----------------+-------------------------------------------------------------------------------+---------+
    | Name               | PrivateIpAddress   | InstanceId          | InstanceType   | Tags                                                                          | State   |
    +====================+====================+=====================+================+===============================================================================+=========+
    | auth               | 10.0.1.233         | i-053a08fa0f4d583c1 | t3.small       | {                                                                             | running |
    |                    |                    |                     |                |     "AmazonECSManaged": "true",                                               |         |
    |                    |                    |                     |                |     "account": "493370826424",                                                |         |
    |                    |                    |                     |                |     "aws:autoscaling:groupName": "auth2024030222363784960000000d",            |         |
    |                    |                    |                     |                |     "aws:ec2launchtemplate:id": "lt-0d93139ab32de43aa",                       |         |
    |                    |                    |                     |                |     "aws:ec2launchtemplate:version": "2",                                     |         |
    |                    |                    |                     |                |     "environment": "development",                                             |         |
    |                    |                    |                     |                |     "managed-by": "terraform",                                                |         |
    |                    |                    |                     |                |     "service": "auth"                                                         |         |
    |                    |                    |                     |                | }                                                                             |         |
    +--------------------+--------------------+---------------------+----------------+-------------------------------------------------------------------------------+---------+
    ...
    +--------------------+--------------------+---------------------+----------------+-------------------------------------------------------------------------------+---------+
    | webserver          | 10.0.7.88          | i-0ff80ad49cf5a46ea | t3.micro       | {                                                                             | running |
    |                    |                    |                     |                |     "account": "493370826424",                                                |         |
    |                    |                    |                     |                |     "aws:autoscaling:groupName": "web20231125205239428700000003",             |         |
    |                    |                    |                     |                |     "aws:ec2launchtemplate:id": "lt-042ea5dd55b0fff3b",                       |         |
    |                    |                    |                     |                |     "aws:ec2launchtemplate:version": "6",                                     |         |
    |                    |                    |                     |                |     "environment": "production",                                              |         |
    |                    |                    |                     |                |     "managed-by": "terraform",                                                |         |
    |                    |                    |                     |                |     "service": "website"                                                      |         |
    |                    |                    |                     |                | }                                                                             |         |
    +--------------------+--------------------+---------------------+----------------+-------------------------------------------------------------------------------+---------+

To print instances of a "website" service.

.. code-block:: bash

    $ ih-ec2 list --tags --service=website
    +-----------+--------------------+---------------------+----------------+-------------------------------------------------------------------+---------+
    | Name      | PrivateIpAddress   | InstanceId          | InstanceType   | Tags                                                              | State   |
    +===========+====================+=====================+================+===================================================================+=========+
    | webserver | 10.0.6.203         | i-00eb66708c5108595 | t3.micro       | {                                                                 | running |
    |           |                    |                     |                |     "account": "493370826424",                                    |         |
    |           |                    |                     |                |     "aws:autoscaling:groupName": "web20231125205239428700000003", |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:id": "lt-042ea5dd55b0fff3b",           |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:version": "6",                         |         |
    |           |                    |                     |                |     "environment": "production",                                  |         |
    |           |                    |                     |                |     "managed-by": "terraform",                                    |         |
    |           |                    |                     |                |     "service": "website"                                          |         |
    |           |                    |                     |                | }                                                                 |         |
    +-----------+--------------------+---------------------+----------------+-------------------------------------------------------------------+---------+
    | webserver | 10.0.7.88          | i-0ff80ad49cf5a46ea | t3.micro       | {                                                                 | running |
    |           |                    |                     |                |     "account": "493370826424",                                    |         |
    |           |                    |                     |                |     "aws:autoscaling:groupName": "web20231125205239428700000003", |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:id": "lt-042ea5dd55b0fff3b",           |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:version": "6",                         |         |
    |           |                    |                     |                |     "environment": "production",                                  |         |
    |           |                    |                     |                |     "managed-by": "terraform",                                    |         |
    |           |                    |                     |                |     "service": "website"                                          |         |
    |           |                    |                     |                | }                                                                 |         |
    +-----------+--------------------+---------------------+----------------+-------------------------------------------------------------------+---------+

To print instances of more than one service, list them with a comma.

.. code-block:: bash

    $ ih-ec2 list --tags --service=website,auth
    +-----------+--------------------+---------------------+----------------+--------------------------------------------------------------------+---------+
    | Name      | PrivateIpAddress   | InstanceId          | InstanceType   | Tags                                                               | State   |
    +===========+====================+=====================+================+====================================================================+=========+
    | auth      | 10.0.1.233         | i-053a08fa0f4d583c1 | t3.small       | {                                                                  | running |
    |           |                    |                     |                |     "AmazonECSManaged": "true",                                    |         |
    |           |                    |                     |                |     "account": "493370826424",                                     |         |
    |           |                    |                     |                |     "aws:autoscaling:groupName": "auth2024030222363784960000000d", |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:id": "lt-0d93139ab32de43aa",            |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:version": "2",                          |         |
    |           |                    |                     |                |     "environment": "development",                                  |         |
    |           |                    |                     |                |     "managed-by": "terraform",                                     |         |
    |           |                    |                     |                |     "service": "auth"                                              |         |
    |           |                    |                     |                | }                                                                  |         |
    +-----------+--------------------+---------------------+----------------+--------------------------------------------------------------------+---------+
    | webserver | 10.0.6.203         | i-00eb66708c5108595 | t3.micro       | {                                                                  | running |
    |           |                    |                     |                |     "account": "493370826424",                                     |         |
    |           |                    |                     |                |     "aws:autoscaling:groupName": "web20231125205239428700000003",  |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:id": "lt-042ea5dd55b0fff3b",            |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:version": "6",                          |         |
    |           |                    |                     |                |     "environment": "production",                                   |         |
    |           |                    |                     |                |     "managed-by": "terraform",                                     |         |
    |           |                    |                     |                |     "service": "website"                                           |         |
    |           |                    |                     |                | }                                                                  |         |
    +-----------+--------------------+---------------------+----------------+--------------------------------------------------------------------+---------+
    | webserver | 10.0.7.88          | i-0ff80ad49cf5a46ea | t3.micro       | {                                                                  | running |
    |           |                    |                     |                |     "account": "493370826424",                                     |         |
    |           |                    |                     |                |     "aws:autoscaling:groupName": "web20231125205239428700000003",  |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:id": "lt-042ea5dd55b0fff3b",            |         |
    |           |                    |                     |                |     "aws:ec2launchtemplate:version": "6",                          |         |
    |           |                    |                     |                |     "environment": "production",                                   |         |
    |           |                    |                     |                |     "managed-by": "terraform",                                     |         |
    |           |                    |                     |                |     "service": "website"                                           |         |
    |           |                    |                     |                | }                                                                  |         |
    +-----------+--------------------+---------------------+----------------+--------------------------------------------------------------------+---------+

``ih-elastic``: manage Elasticsearch cluster
--------------------------------------------

The ``ih-elastic`` command works with an Elasticsearch cluster.

.. code-block:: bash

    $ ih-elastic
    Usage: ih-elastic [OPTIONS] COMMAND [ARGS]...

      Elasticsearch helper.

    Options:
      --debug                         Enable debug logging.
      --quiet                         Suppress informational messages and output
                                      only warnings and errors.
      --username TEXT                 Username in Elasticsearch cluster.
                                      [default: elastic]
      --password TEXT                 Password for the Elasticsearch user. By
                                      default try to read it from puppet facts/AWS
                                      secretsmanager.
      --password-secret TEXT          AWS secretsmanager secret id with the
                                      password.
      --es-protocol TEXT              Elasticsearch protocol  [default: http]
      --es-host TEXT                  Elasticsearch host  [default: 127.0.1.1]
      --es-port INTEGER               Elasticsearch port  [default: 9200]
      --format [text|json|cbor|yaml|smile]
                                      Output format
      --help                          Show this message and exit.

    Commands:
      cat             Compact and aligned text (CAT) APIs.
      cluster         Cluster level operations.
      cluster-health  Connect to Elasticsearch host and print the cluster...
      passwd          Change password for Elasticsearch user.
      snapshots       Work with snapshots.

``ih-elastic cluster-health``: Show cluster health
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ih-elastic cluster-health`` shows the cluster health. The command is supposed to be run on an Elasticsearch node.

.. code-block:: bash

    $ ih-elastic cluster-health
    2024-07-13 23:04:30,987: INFO: botocore.credentials:credentials.load():1075: Found credentials from IAM Role: elastic-master-dhBLZE
    2024-07-13 23:04:31,573: INFO: elastic_transport.transport:_transport.perform_request():349: GET http://10.1.2.145:9200/_cluster/health [status:200 duration:0.002s]
    2024-07-13 23:04:31,573: INFO: root:__init__.cmd_cluster_health():25: {
        "cluster_name": "elastic",
        "status": "green",
        "timed_out": false,
        "number_of_nodes": 6,
        "number_of_data_nodes": 3,
        "active_primary_shards": 167,
        "active_shards": 433,
        "relocating_shards": 0,
        "initializing_shards": 0,
        "unassigned_shards": 0,
        "delayed_unassigned_shards": 0,
        "number_of_pending_tasks": 0,
        "number_of_in_flight_fetch": 0,
        "task_max_waiting_in_queue_millis": 0,
        "active_shards_percent_as_number": 100.0
    }

``ih-elastic cluster allocation-explain``: Explain allocation problems
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ih-elastic cluster allocation-explain --help
    Usage: ih-elastic cluster allocation-explain [OPTIONS]

      Provides explanations for shard allocations in the cluster.

    Options:
      --index TEXT           Specifies the name of the index that you would like
                             an explanation for. Run ih-elastic cat shards to get
                             a list.
      --shard INTEGER        Specifies the ID of the shard that you would like an
                             explanation for. Run ih-elastic cat shards to get a
                             list.
      --primary / --replica  If --primary, returns explanation for the primary
                             shard for the given shard ID.
      --help                 Show this message and exit.


``ih-elastic cat shards``: List shards
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    $ ih-elastic cat shards --help
    Usage: ih-elastic cat shards [OPTIONS]

      Provides a detailed view of shard allocation on nodes.

    Options:
      --help  Show this message and exit.

``ih-elastic cat snapshots``: Shows backup copies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ih-elastic cat snapshots`` shows available backup copies. It also has to be run on an Elasticsearch node.

.. code-block:: bash

    $ ih-elastic cat snapshots | head
    2024-07-13 23:06:38,874: INFO: botocore.credentials:credentials.load():1075: Found credentials from IAM Role: elastic-master-dhBLZE
    2024-07-13 23:06:39,952: INFO: elastic_transport.transport:_transport.perform_request():349: GET http://10.1.2.145:9200/_cat/snapshots/_all?v=true [status:200 duration:0.979s]
    2024-07-13 23:06:39,952: INFO: root:__init__.cmd_snapshots():23:
    id                                 repository  status start_epoch start_time end_epoch  end_time duration indices successful_shards failed_shards total_shards
    elastic-2024-02-20_19-19-54.544449 backups    SUCCESS 1708456794  19:19:54   1708456796 19:19:56     1.8s      33                33             0           33
    elastic-2024-02-20_19-43-51.722634 backups    SUCCESS 1708458231  19:43:51   1708458233 19:43:53     1.6s      33                33             0           33
    elastic-2024-02-20_19-52-25.053742 backups    SUCCESS 1708458745  19:52:25   1708458745 19:52:25    801ms      33                33             0           33
    elastic-2024-02-20_20-01-23.072070 backups    SUCCESS 1708459282  20:01:22   1708459283 20:01:23    801ms      34                34             0           34
    elastic-2024-02-21_11-44-02.921604 backups    SUCCESS 1708515842  11:44:02   1708515844 11:44:04     1.4s      36                36             0           36
    elastic-2024-02-21_12-37-02.628985 backups    SUCCESS 1708519022  12:37:02   1708519023 12:37:03    800ms      36                36             0           36


``ih-elastic snapshots``: Create or restore snapshots
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``ih-elastic snapshots`` can take or restore a snapshot.

.. code-block:: bash

    $ ih-elastic snapshots
    2024-07-13 23:07:58,835: INFO: botocore.credentials:credentials.load():1075: Found credentials from IAM Role: elastic-master-dhBLZE
    Usage: ih-elastic snapshots [OPTIONS] COMMAND [ARGS]...

      Work with snapshots.

    Options:
      --help  Show this message and exit.

    Commands:
      create             Creates a snapshot in a repository.
      create-repository  Creates a repository.
      delete-repository  Deletes a repository.
      restore            Restores a snapshot in a repository.
      status             Returns information about the status of a snapshot.

``ih-github``: manage action runners
------------------------------------

As the name suggests, the ``ih-github`` command works with GitHub.

.. code-block:: bash

    $ ih-github --help
    Usage: ih-github [OPTIONS] COMMAND [ARGS]...

      Various GitHub helper commands. See ih-github --help for details.

    Options:
      --debug  Enable debug logging.
      --help   Show this message and exit.

    Commands:
      run     Run a command and publish its output to as a comment in GitHub...
      runner  Manage self-hosted runners.


The ``ih-github run`` command can run a command and publish its output as a command in a pull request.

.. code-block:: bash

    $ ih-github run --help
    Usage: ih-github run [OPTIONS] REPO PULL_REQUEST_NUMBER

      Run a command and publish its output to as a comment in GitHub pull request.

      For instance

    Options:
      --github-token TEXT    Personal access token for GitHub.
      --run-timeout INTEGER  How many seconds the command it allowed to run
                             [default: 3600]
      --help                 Show this message and exit.

I use it often in CI workflows.

.. code-block:: yaml

    jobs:
      check:
        runs-on: ["self-hosted", "Linux", "environment:sandbox", "skeema"]
        environment: "continuous-integration"
        steps:
          - uses: "actions/checkout@v4"

          - name: "Linters"
            run: |
              yamllint .github
              ih-github run ${{ github.repository }} ${{ github.event.pull_request.number }} \
              skeema lint --workspace docker


The ``ih-github runner`` command allows to manipulate with self-hosted action runners in GitHub.

.. code-block:: bash

    $ ih-github runner --help
    Usage: ih-github runner [OPTIONS] COMMAND [ARGS]...

      Manage self-hosted runners.

    Options:
      --github-token TEXT         Personal access token for GitHub.
      --github-token-secret TEXT  Read GitHub token from AWS secret.
      --org TEXT                  GitHub organization
      --help                      Show this message and exit.

    Commands:
      deregister     deregister a self-hosted runner.
      download       Download an actions-runner release tar-ball.
      is-registered  Check if a runner with the given name is already...
      list           List self-hosted runners
      register       register a self-hosted runner.

For example, I can see what runners are offline.

.. code-block:: bash

    $ ih-github runner --org infrahouse --github-token **** list | jq .runners[] | jq '"Name: \(.name), Status: \(.status)"'
    "Name: ip-10-1-1-132, Status: online"
    "Name: ip-10-1-1-61, Status: online"
    "Name: ip-10-1-2-8, Status: online"
    "Name: ip-10-1-3-224, Status: online"
    "Name: ip-10-1-1-119, Status: offline"
    "Name: ip-10-1-1-161, Status: offline"
    "Name: ip-10-1-1-168, Status: offline"
    "Name: ip-10-1-1-24, Status: offline"
    "Name: ip-10-1-1-51, Status: offline"
    "Name: ip-10-1-1-72, Status: offline"
    "Name: ip-10-1-1-82, Status: offline"
    "Name: ip-10-1-2-221, Status: offline"
    "Name: ip-10-1-2-40, Status: offline"
    "Name: ip-10-1-2-6, Status: offline"
    "Name: ip-10-1-2-7, Status: offline"
    "Name: ip-10-1-3-61, Status: offline"
    "Name: ip-10-1-3-65, Status: offline"


``ih-plan``: summarize and publish Terraform plan to pull request
-----------------------------------------------------------------

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

The full comment includes several sections:

    * Title specifies in what Terraform state the changes will be made.
    * "Affected resources counts" is a summary table with counts of how many resources will be added, modified, or destroyed.
    * "Affected resources by action" is a table that lists resources that are going to be added, modified, or destroyed.
    * Finally, a collapsible "STDOUT" block. It includes the output of ``terraform plan``, however it skips progress messages for brevity and convenience.

.. image:: docs/_static/ih-plan-full-comment.png
    :align: center
    :alt: Example of a comment published by ``ih-plan``.

.. image:: docs/_static/ih-plan-stdout-block.png
    :align: center
    :alt: A part of ``terraform plan`` standard output.


``ih-puppet``: run master-less puppet
-------------------------------------

``ih-puppet apply`` runs a Puppet client. For instance, all InfraHouse provisioned hosts have a cron job

.. code-block::

    26,56 * * * * ih-puppet  --quiet \
    --environment sandbox \
    --environmentpath {root_directory}/environments \
    --root-directory /opt/puppet-code \
    --hiera-config /opt/infrahouse-puppet-data/environments/sandbox/hiera.yaml \
    --module-path {root_directory}/modules:/opt/infrahouse-puppet-data/modules \
    apply \
    /opt/puppet-code/environments/sandbox/manifests/site.pp

It's just a wrapper that installs Puppet module dependencies and runs the client.

``ih-registry``: publish Terraform modules
------------------------------------------

The ``ih-registry upload`` command can publish a Terraform module to a Tapir_-managed private registry.

.. code-block:: bash

    $ ih-registry
    Usage: ih-registry [OPTIONS] COMMAND [ARGS]...

      InfraHouse Terraform Registry helpers.

    Options:
      --debug    Enable debug logging.
      --version  Show the version and exit.
      --help     Show this message and exit.

    Commands:
      upload  Upload Terraform module to the InfraHouse Terraform Registry

``ih-s3-reprepro``: manage Debian repository in S3
--------------------------------------------------

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

``ih-secrets``: access AWS Secrets Manager
------------------------------------------

The ``ih-secrets`` command works with
`AWS Secrets Manager <https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html>`_.

You can list secrets.

.. code-block:: bash

    $ ih-secrets list
    +------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------+
    | Name                                                 | Description                                                                                                               |
    +======================================================+===========================================================================================================================+
    | GITHUB_TOKEN                                         | GitHub token with manage_runners:org permissions. Needed to register self-hosted runners.                                 |
    | flask_secret_key20240705183915732100000013           | Flask secret key                                                                                                          |
    | google_client20240705183915856300000015              | A JSON with Google OAuth Client ID                                                                                        |
    | keycloak_admin_credentials20240302224352142500000001 | A json with username/password keys with keycloak credentials                                                              |
    | keycloak_service20240303174856808900000002           | A JSON with username/password keys - MySQL account used by keycloak service                                               |
    | openvpn_ca_passphrase20240705183916567800000017      | OpenVPN CA Key Passphrase                                                                                                 |
    | packager-key-focal                                   | Signing GPG key for focal                                                                                                 |
    | packager-key-jammy                                   | Signing GPG key for jammy                                                                                                 |
    | packager-passphrase-focal                            | Passphrase for a signing GPG key for focal                                                                                |
    | packager-passphrase-jammy                            | Passphrase for a signing GPG key for jammy                                                                                |
    | rds!db-8b53b28e-6606-43d3-941d-62d6986747f9          | Secret associated with primary RDS DB instance: arn:aws:rds:us-west-1:493370826424:db:keycloak-20240303174857883700000006 |
    | registry_client_secret20240302203708051000000001     | Oauth2 credentials with Google                                                                                            |
    | smtp_credentials20240707192347968700000001           | SMTP credentials for Postfix smarthost                                                                                    |
    +------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------------+


You can get a secret value.

.. code-block:: bash

    $ ih-secrets get keycloak_service20240303174856808900000002 | jq
    {
      "password": "******",
      "username": "keycloak_service"
    }


And, if your credentials allow updating the secret, you can set it's value.

.. code-block:: bash

    $ ih-secrets set --help
    Usage: ih-secrets set [OPTIONS] SECRET [PATH]...

      Set value to a secret.

      Optionally the value may be given via a local file specified by a path
      argument.

      ih-secrets set mysecret /path/to/file_with_value

      if the path is omitted, a user will be prompt for the value.

    Options:
      --help  Show this message and exit.


``ih-skeema``: run Skeema in CI/CD
----------------------------------

The ``ih-skeema`` command is a wrapper around a popular Skeema tool. The wrapper provides intergration with
AWS Secrets Manager to provide database credentials.

.. code-block:: bash

    $ ih-skeema --help
    Usage: ih-skeema [OPTIONS] COMMAND [ARGS]...

      Various Skeema (https://www.skeema.io/) helper commands. See ih-skeema
      --help for details.

    Options:
      --debug                    Enable debug logging.
      --skeema-path TEXT         Path to the skeema executable.  [default: skeema]
      --username TEXT            Username to connect to database host  [default:
                                 root]
      --password TEXT            Password for database user. By default, read from
                                 environment variable $MYSQL_PWD.
      --credentials-secret TEXT  If specified, read username and password from AWS
                                 secrets manager. The secret value must be a JSON
                                 with keys 'username' and 'password'.
      --help                     Show this message and exit.

    Commands:
      run  Run a skeema command.


``ih-skeema`` is designed to be used in CI/CD workflows. For example, here it runs skeema diff and publishes result
to a pull request.

.. code-block:: yaml

    jobs:
      check:
        runs-on: ["self-hosted", "Linux", "environment:sandbox", "skeema"]
        environment: "continuous-integration"
        steps:
          - uses: "actions/checkout@v4"

          - name: "Configure AWS Credentials"
            uses: "aws-actions/configure-aws-credentials@v2"
            with:
              role-to-assume: "${{ env.ROLE_GITHUB }}"
              role-session-name: "github-actions"
              aws-region: "${{ env.AWS_DEFAULT_REGION }}"

          - name: "Linters"
            run: |
              yamllint .github
              ih-github run ${{ github.repository }} ${{ github.event.pull_request.number }} \
              skeema lint --workspace docker

          - name: "Differences"
            run: |
              ih-github run ${{ github.repository }} ${{ github.event.pull_request.number }} \
              ih-skeema --credentials-secret ${{ env.CREDENTIALS_SECRET }} run diff sandbox || \
                ( RESULT=$? ; if [ $RESULT -gt 1 ]; then echo "Error occured"; exit $RESULT ; fi )


Credits
~~~~~~~

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
.. _Tapir: https://github.com/PacoVK/tapir
