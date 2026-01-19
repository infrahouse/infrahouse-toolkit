# ih-mysql CLI Implementation Plan

## Overview

Add a new CLI command `ih-mysql` to infrahouse-toolkit for managing Percona/MySQL server operations.
This command will be called by Puppet to perform bootstrap, user creation, and other MySQL management tasks.

## Dependencies

Add to `setup.py` or `pyproject.toml`:
- `infrahouse-core` (for EC2Instance, DynamoDBTable, get_secret, get_client)

## CLI Structure

```
ih-mysql
├── bootstrap    # Master election, user creation (master only), replica configuration, target group registration
└── create-users # Standalone user creation (optional, for manual use)
```

## Tasks

### Task 1: Create CLI Entry Point

**File**: `infrahouse_toolkit/cli/ih_mysql.py`

Create the main CLI using Click:

```python
import click

@click.group()
def ih_mysql():
    """MySQL/Percona Server management commands."""
    pass

# Entry point for setup.py
def main():
    ih_mysql()
```

**File**: `setup.py` - Add entry point:

```python
entry_points={
    'console_scripts': [
        # ... existing entries ...
        'ih-mysql=infrahouse_toolkit.cli.ih_mysql:main',
    ],
}
```

---

### Task 2: Implement `bootstrap` Subcommand

**Purpose**: Coordinate master election via DynamoDB lock, configure replica if master exists.

**Usage**:
```bash
ih-mysql bootstrap \
    --cluster-id percona-prod \
    --dynamodb-table percona-locks \
    --credentials-secret percona/credentials \
    --vpc-cidr 10.0.0.0/16 \
    --read-tg-arn arn:aws:elasticloadbalancing:...:targetgroup/read/... \
    --write-tg-arn arn:aws:elasticloadbalancing:...:targetgroup/write/...
```

**Parameters**:
| Parameter | Required | Description |
|-----------|----------|-------------|
| `--cluster-id` | Yes | Unique identifier for the Percona cluster |
| `--dynamodb-table` | Yes | DynamoDB table name for locking |
| `--credentials-secret` | Yes | AWS Secrets Manager secret name containing MySQL credentials |
| `--vpc-cidr` | Yes | VPC CIDR for MySQL user host restrictions |
| `--read-tg-arn` | No | ARN of the read target group (all nodes register) |
| `--write-tg-arn` | No | ARN of the write target group (master only) |
| `--bootstrap-marker` | No | Path to marker file (default: `/var/lib/mysql/.bootstrapped`) |

**Logic**:

```
1. Check if bootstrap marker exists → exit 0 if exists
2. Get instance ID from EC2 metadata
3. Acquire DynamoDB lock (LOCK_NAME = "{cluster_id}-bootstrap-lock")
4. While holding lock:
   a. Check if master exists (KEY = "{cluster_id}-master")
   b. If no master (becoming MASTER):
      - Create MySQL users (root, repl, backup, monitor) with credentials from Secrets Manager
      - Register self as master in DynamoDB
      - Write "master" to bootstrap marker
      - Register with write target group (if ARN provided)
   c. If master exists (becoming REPLICA):
      - Get master instance ID from DynamoDB
      - Get master private IP via EC2Instance
      - Get replication password from Secrets Manager
      - Run CHANGE REPLICATION SOURCE TO... via mysql CLI
      - Write "replica:{master_ip}" to bootstrap marker
      - (Users will be replicated from master automatically)
5. Lock auto-releases
6. Register with read target group (if ARN provided) - all nodes
7. Exit 0
```

**MySQL Users Created (master only)**:
| User | Host | Grants |
|------|------|--------|
| root | localhost | ALTER USER (set password) |
| repl | {vpc_cidr} | REPLICATION SLAVE |
| backup | localhost | RELOAD, LOCK TABLES, PROCESS, REPLICATION CLIENT, BACKUP_ADMIN |
| monitor | localhost | PROCESS, REPLICATION CLIENT, SELECT |
| monitor | {vpc_cidr} | PROCESS, REPLICATION CLIENT, SELECT |

**Implementation**:

```python
@ih_mysql.command()
@click.option('--cluster-id', required=True, help='Cluster identifier')
@click.option('--dynamodb-table', required=True, help='DynamoDB table for locking')
@click.option('--credentials-secret', required=True, help='Secrets Manager secret name')
@click.option('--region', default=None, help='AWS region')
@click.option('--bootstrap-marker', default='/var/lib/mysql/.bootstrapped', help='Marker file path')
def bootstrap(cluster_id, dynamodb_table, credentials_secret, region, bootstrap_marker):
    """Bootstrap Percona server as master or replica."""
    # Implementation here
```

---

### Task 3: Implement `create-users` Subcommand

**Purpose**: Create MySQL users for replication, backup, and monitoring.

**Usage**:
```bash
ih-mysql create-users \
    --credentials-secret percona/credentials \
    --vpc-cidr 10.0.0.0/16 \
    --region us-east-1
```

**Parameters**:
| Parameter | Required | Description |
|-----------|----------|-------------|
| `--credentials-secret` | Yes | AWS Secrets Manager secret name |
| `--vpc-cidr` | Yes | VPC CIDR for user host restrictions |
| `--region` | No | AWS region |

**Secret Format** (JSON):
```json
{
  "root": "root-password",
  "replication": "repl-password",
  "backup": "backup-password",
  "monitor": "monitor-password"
}
```

**Users to Create**:
| User | Host | Grants |
|------|------|--------|
| root | localhost | ALTER USER (set password) |
| repl | {vpc_cidr} | REPLICATION SLAVE |
| backup | localhost | RELOAD, LOCK TABLES, PROCESS, REPLICATION CLIENT, BACKUP_ADMIN |
| monitor | localhost | PROCESS, REPLICATION CLIENT, SELECT |
| monitor | {vpc_cidr} | PROCESS, REPLICATION CLIENT, SELECT |

**Implementation**:

```python
@ih_mysql.command()
@click.option('--credentials-secret', required=True, help='Secrets Manager secret name')
@click.option('--vpc-cidr', required=True, help='VPC CIDR for user hosts')
@click.option('--region', default=None, help='AWS region')
def create_users(credentials_secret, vpc_cidr, region):
    """Create MySQL users for replication, backup, and monitoring."""
    # Implementation here
```

---

## File Structure

```
infrahouse_toolkit/
├── cli/
│   ├── __init__.py
│   ├── ih_mysql.py          # NEW: Main CLI
│   └── ih_mysql/            # NEW: Subcommand implementations
│       ├── __init__.py
│       ├── bootstrap.py
│       └── create_users.py
```

---

## Testing

1. Deploy updated infrahouse-toolkit to test EC2 instance
2. Test bootstrap as first instance (becomes master):
   ```bash
   ih-mysql bootstrap --cluster-id test --dynamodb-table test-locks --credentials-secret test/creds --region us-east-1
   cat /var/lib/mysql/.bootstrapped  # Should show "master"
   ```
3. Test bootstrap as second instance (becomes replica):
   ```bash
   # On second instance
   ih-mysql bootstrap --cluster-id test --dynamodb-table test-locks --credentials-secret test/creds --region us-east-1
   cat /var/lib/mysql/.bootstrapped  # Should show "replica:{ip}"
   ```

---

## Puppet Integration

After implementation, Puppet becomes a single exec call - bootstrap handles everything:

```puppet
# profile::percona::bootstrap
class profile::percona::bootstrap () {

  $cluster_id = $facts['percona']['cluster_id']
  $dynamodb_table = $facts['percona']['dynamodb_table']
  $credentials_secret = $facts['percona']['credentials_secret']
  $vpc_cidr = $facts['percona']['vpc_cidr']
  $read_tg_arn = $facts['percona']['read_tg_arn']
  $write_tg_arn = $facts['percona']['write_tg_arn']

  $bootstrap_cmd = @("CMD"/L)
    ih-mysql bootstrap \
    --cluster-id ${cluster_id} \
    --dynamodb-table ${dynamodb_table} \
    --credentials-secret ${credentials_secret} \
    --vpc-cidr ${vpc_cidr} \
    --read-tg-arn ${read_tg_arn} \
    --write-tg-arn ${write_tg_arn}
    |-CMD

  exec { 'percona-bootstrap':
    path    => '/usr/local/bin:/usr/bin:/bin',
    command => $bootstrap_cmd,
    creates => '/var/lib/mysql/.bootstrapped',
    require => [
      Package['infrahouse-toolkit'],
      Service['mysql'],
    ],
  }
}
```

**Note**: No separate `create-users` step needed - bootstrap creates users on master, replicas get them via replication.
