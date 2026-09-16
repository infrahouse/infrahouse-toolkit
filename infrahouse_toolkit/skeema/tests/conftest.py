"""Fixtures with skeema diff output."""

import pytest

from infrahouse_toolkit.skeema.diff import SkeemaDiff

WORKING_DIR = "/work/schema"

# skeema 1.11.1 diff against MySQL 8.0, with
# alter-wrapper="/usr/bin/pt-online-schema-change ... D={SCHEMA},t={TABLE},..." and alter-wrapper-min-size=1M.
# orders is above the minimum size, so skeema prints a wrapper command for it instead of an ALTER.
# Stored routines come in a DELIMITER block.
CONFIGURED_OUTPUT = """\
-- instance: 127.0.0.1:33069
USE `other`;
ALTER TABLE `t` ADD COLUMN `x` int DEFAULT NULL;
USE `shop`;
DROP TABLE `gone`;
\\! /usr/bin/pt-online-schema-change --execute --alter 'ADD COLUMN `note` varchar(255) DEFAULT NULL' \
D=shop,t=orders,h=127.0.0.1,P=33069,F=$IH_SKEEMA_DEFAULTS_FILE
ALTER TABLE `small` ADD COLUMN `w` int DEFAULT NULL;
CREATE TABLE `fresh` (
  `id` int NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
DELIMITER //
CREATE DEFINER=`root`@`%` PROCEDURE `proc_touch`(IN p_id int)
BEGIN
  UPDATE small SET v = v + 1 WHERE id = p_id;
  SELECT 1;
END//
DELIMITER ;
"""

# The same diff with --alter-wrapper= --ddl-wrapper=. skeema prints the statements of a schema
# in a different order from one run to the next.
PLAIN_OUTPUT = """\
-- instance: 127.0.0.1:33069
USE `other`;
ALTER TABLE `t` ADD COLUMN `x` int DEFAULT NULL;
USE `shop`;
ALTER TABLE `orders` ADD COLUMN `note` varchar(255) DEFAULT NULL;
ALTER TABLE `small` ADD COLUMN `w` int DEFAULT NULL;
DROP TABLE `gone`;
CREATE TABLE `fresh` (
  `id` int NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
DELIMITER //
CREATE DEFINER=`root`@`%` PROCEDURE `proc_touch`(IN p_id int)
BEGIN
  UPDATE small SET v = v + 1 WHERE id = p_id;
  SELECT 1;
END//
DELIMITER ;
"""

DIFF_ERRORS = """\
2026-09-16 11:52:45 [INFO]  Generating diff of 127.0.0.1:33069 other vs /work/schema/other/*.sql
2026-09-16 11:52:45 [INFO]  127.0.0.1:33069 other: diff complete
2026-09-16 11:52:45 [INFO]  Generating diff of 127.0.0.1:33069 shop vs /work/schema/shop/*.sql
2026-09-16 11:52:45 [WARN]  /work/schema/shop/orders.sql:2: Column id of table `orders` is an auto_increment column \
using data type int, which is not configured to be permitted.
2026-09-16 11:52:45 [INFO]  127.0.0.1:33069 shop: diff complete
"""

# Without --allow-unsafe skeema skips a schema with a DROP TABLE entirely: nothing for it on stdout,
# the refused statement in the log, and exit code 2.
REFUSED_OUTPUT = """\
-- instance: 127.0.0.1:33069
USE `other`;
ALTER TABLE `t` ADD COLUMN `x` int DEFAULT NULL;
"""

REFUSED_ERRORS = """\
2026-09-16 11:52:35 [INFO]  Generating diff of 127.0.0.1:33069 other vs /work/schema/other/*.sql
2026-09-16 11:52:35 [INFO]  127.0.0.1:33069 other: diff complete
2026-09-16 11:52:35 [INFO]  Generating diff of 127.0.0.1:33069 shop vs /work/schema/shop/*.sql
2026-09-16 11:52:35 [ERROR] Desired drop of table `_orders_old` would cause all of its data to be lost. \
Generated SQL statement:
2026-09-16 11:52:35 [ERROR] # DROP TABLE `_orders_old`
2026-09-16 11:52:35 [WARN]  Skipping 127.0.0.1:33069 shop due to 1 unsafe statements. Use --allow-unsafe or \
--safe-below-size to permit this operation. Refer to the Safety Options section of --help.
2026-09-16 11:52:35 [ERROR] Skipped 1 operations due to problems
"""


@pytest.fixture
def configured_diff():
    """A diff where skeema wraps the ALTER of orders."""
    return SkeemaDiff(CONFIGURED_OUTPUT, DIFF_ERRORS, 1, WORKING_DIR)


@pytest.fixture
def plain_diff():
    """The same diff with wrappers blanked."""
    return SkeemaDiff(PLAIN_OUTPUT, DIFF_ERRORS, 1, WORKING_DIR)


@pytest.fixture
def refused_diff():
    """A diff where skeema refused an unsafe statement."""
    return SkeemaDiff(REFUSED_OUTPUT, REFUSED_ERRORS, 2, WORKING_DIR)
