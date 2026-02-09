# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First Steps

**Your first tool call in this repository MUST be reading .claude/CODING_STANDARD.md.
Do not read any other files, search, or take any actions until you have read it.**
This contains InfraHouse's comprehensive coding standards for Terraform, Python, and general formatting rules.

## Project Overview

**infrahouse-toolkit** is a Python CLI toolkit for AWS infrastructure provisioning, operational tasks, and CI/CD
workflows. It provides 14 CLI tools built with Click, packaged as both a PyPI package and Debian packages.

## Common Commands

```bash
# Setup
make bootstrap                  # Install all deps + editable install + git hooks

# Linting (does NOT modify files, only checks)
make lint                       # Run all linters (yamllint, black, isort, mdformat, reqsort, pylint)

# Formatting (modifies files)
make black                      # Reformat code with black
make isort                      # Reformat imports

# Testing
pytest --cov --cov-report=term-missing -xvvs infrahouse_toolkit           # Full test suite
pytest -xvvs infrahouse_toolkit/cli/ih_ec2/cmd_list/                      # Single test directory
pytest -xvvs infrahouse_toolkit/cli/ih_ec2/cmd_list/ -k "test_my_func"    # Single test

# Build
make dist                       # Build wheel + sdist
make package                    # Build Debian package via Docker/omnibus
```

## Architecture

### CLI Structure

All CLI tools use Click and follow the same hierarchical pattern:

```
infrahouse_toolkit/cli/ih_<tool>/
├── __init__.py              # Click group with global options (--debug, --aws-profile, --aws-region)
├── cmd_<subcommand>/
│   └── __init__.py          # Click command implementation
└── cmd_<subcommand2>/
    └── __init__.py
```

**Pattern**: The parent group initializes `ctx.obj` with shared resources (AWS clients, config), and subcommands
access them via `@click.pass_context`. Subcommands are registered with `group.add_command(cmd)` in the group's
`__init__.py`. Nested groups (e.g., `ih-aws autoscaling complete`) are supported.

Entry points are registered in `setup.py` `console_scripts`.

### CLI Tools

| Command | Purpose |
|---------|---------|
| `ih-aws` | AWS helpers (credentials, autoscaling, ECS) |
| `ih-certbot` | Bundled certbot wrapper |
| `ih-ec2` | EC2 instance management |
| `ih-elastic` | Elasticsearch cluster operations |
| `ih-github` | GitHub integration (runners, CI/CD) |
| `ih-mysql` | MySQL/Percona cluster bootstrap |
| `ih-openvpn` | OpenVPN certificate management |
| `ih-plan` | Terraform plan helpers |
| `ih-puppet` | Puppet client wrapper |
| `ih-registry` | Terraform registry publishing |
| `ih-s3` | S3 utilities |
| `ih-s3-reprepro` | Debian repo management in S3 |
| `ih-secrets` | AWS Secrets Manager access |
| `ih-skeema` | Skeema database schema tool |

### Shared Modules

- `infrahouse_toolkit/cli/lib.py` — Terraform backend parsing, S3 clients, Secrets Manager helpers
- `infrahouse_toolkit/cli/utils.py` — Subprocess execution, S3 mounting, retry logic, dependency checking
- `infrahouse_toolkit/cli/exceptions.py` — Custom `IHCLIError` exception hierarchy
- `infrahouse_toolkit/aws/` — AWS utility classes and their tests

### Key Dependencies

- **Click** — CLI framework
- **boto3/botocore** — AWS SDK
- **infrahouse-core** — InfraHouse shared library (logging via `setup_logging()`, AWS helpers)
- **PyGithub** — GitHub API
- **elasticsearch** — Elasticsearch client

## Configuration

- **Black**: line-length = 120 (configured in `pyproject.toml`)
- **isort**: profile = "black" (configured in `pyproject.toml`)
- **pylint**: configured via `.pylintrc`
- **Version**: managed by `bump2version` across `setup.py`, `infrahouse_toolkit/__init__.py`, and omnibus config

## Adding a New CLI Tool

1. Create `infrahouse_toolkit/cli/ih_<name>/__init__.py` with a `@click.group()` function
2. Create subcommand directories `cmd_<action>/__init__.py` with `@click.command()` functions
3. Register subcommands via `group.add_command(cmd)` in the group's `__init__.py`
4. Add entry point to `console_scripts` in `setup.py`
5. Add any new dependencies to `requirements.txt` (pinned with `~=` to major version)