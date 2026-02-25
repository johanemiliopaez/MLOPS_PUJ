#!/bin/sh
set -eu

mysql -uroot -p"${MYSQL_ROOT_PASSWORD}" "${MYSQL_DATABASE}" <<'SQL'
CREATE TABLE IF NOT EXISTS penguins_raw (
  species VARCHAR(50),
  island VARCHAR(50),
  bill_length_mm VARCHAR(50),
  bill_depth_mm VARCHAR(50),
  flipper_length_mm VARCHAR(50),
  body_mass_g VARCHAR(50),
  sex VARCHAR(50),
  year VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS penguins LIKE penguins_raw;
SQL
