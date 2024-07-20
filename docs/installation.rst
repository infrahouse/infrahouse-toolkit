.. highlight:: shell

============
Installation
============

The InfraHouse Toolkit runs on MacOS or Linux operating systems. It can be installed as a Python package from
the public PyPI, with Homebrew on MacOS, or as a .deb package on Ubuntu.

Python Package (Linux, MacOS)
-----------------------------

To install InfraHouse Toolkit, run this command in your terminal:

.. code-block:: console

    pip install infrahouse-toolkit

This is the preferred method to install InfraHouse Toolkit, as it will always install the most recent stable release.

If you don't have `pip`_ installed, this `Python installation guide`_ can guide
you through the process.


Homebrew package (MacOS)
------------------------

.. code-block:: console

    brew install infrahouse/infrahouse-toolkit/infrahouse-toolkit


Debian package (Ubuntu noble, jammy, focal)
-------------------------------------------

Download the repository public key and convert it into apt compatible format.

.. code-block:: console

    # Install dependencies
    apt-get update
    apt-get install \
        gpg \
        lsb-release \
        curl
    # Add a GPG public key to verify InfraHouse packages
    mkdir -p /etc/apt/cloud-init.gpg.d/
    curl  -fsSL https://release-$(lsb_release -cs).infrahouse.com/DEB-GPG-KEY-release-$(lsb_release -cs).infrahouse.com \
        | gpg --dearmor -o /etc/apt/cloud-init.gpg.d/infrahouse.gpg


Add the InfraHouse repository source.

.. code-block:: console

    echo "deb [signed-by=/etc/apt/cloud-init.gpg.d/infrahouse.gpg] https://release-$(lsb_release -cs).infrahouse.com/ $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/infrahouse.list

    apt-get update


Install ``infrahouse-toolkit`` package.

.. code-block:: console

    apt-get install infrahouse-toolkit


.. _pip: https://pip.pypa.io
.. _Python installation guide: http://docs.python-guide.org/en/latest/starting/installation/


From sources
------------

The sources for InfraHouse Toolkit can be downloaded from the `Github repo`_.

You can either clone the public repository:

.. code-block:: console

    git clone git://github.com/infrahouse/infrahouse-toolkit

Or download the `tarball`_:

.. code-block:: console

    curl -OJL https://github.com/infrahouse/infrahouse-toolkit/tarball/main

Once you have a copy of the source, you can install it with:

.. code-block:: console

    python setup.py install


.. _Github repo: https://github.com/infrahouse/infrahouse-toolkit
.. _tarball: https://github.com/infrahouse/infrahouse-toolkit/tarball/main
