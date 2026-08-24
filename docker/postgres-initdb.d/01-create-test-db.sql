-- Runs once, automatically, the first time the postgres data volume is
-- initialized (see docker-compose.yml's db.volumes). Creates the separate
-- database the test suite uses when run against real Postgres, per
-- CLAUDE.md's testing conventions:
--   DATABASE_URL=postgresql+psycopg2://signalhub:signalhub@localhost:5433/signalhub_test pytest
CREATE DATABASE signalhub_test OWNER signalhub;
