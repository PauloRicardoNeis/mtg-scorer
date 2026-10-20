-- Card prices are daily market estimates from a retained Scryfall bulk file. They
-- change every day, so they live beside the immutable catalog rather than inside it:
-- each load is a new snapshot named by its source bytes and selection rule, and one
-- pointer marks the snapshot the API reads. The publisher can insert but never
-- rewrite, and loads a snapshot, its rows and the pointer in one transaction.
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='price_reader') THEN CREATE ROLE price_reader NOLOGIN; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='price_publisher') THEN CREATE ROLE price_publisher NOLOGIN; END IF;
END $$;
CREATE SCHEMA prices;
REVOKE ALL ON SCHEMA prices FROM PUBLIC;
GRANT USAGE ON SCHEMA prices TO price_reader, price_publisher;

CREATE TABLE prices.price_snapshot (
 price_snapshot_id text PRIMARY KEY CHECK (price_snapshot_id ~ '^prices-[0-9a-f]{64}$'),
 source text NOT NULL CHECK (source = 'scryfall'),
 source_snapshot_id text NOT NULL CHECK (source_snapshot_id <> ''),
 source_sha256 text NOT NULL CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
 -- When Scryfall last refreshed the bulk file: the prices' "as of".
 source_updated_at timestamptz NOT NULL,
 rule text NOT NULL CHECK (rule <> ''),
 card_count integer NOT NULL CHECK (card_count >= 0),
 published_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE prices.card_price (
 price_snapshot_id text NOT NULL REFERENCES prices.price_snapshot,
 oracle_id uuid NOT NULL,
 usd numeric(12,2) NOT NULL CHECK (usd > 0),
 -- The printing the price belongs to, so a surprising number can be traced.
 usd_scryfall_id uuid NOT NULL,
 PRIMARY KEY (price_snapshot_id, oracle_id)
);
CREATE TABLE prices.active_price_snapshot (
 singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
 price_snapshot_id text NOT NULL REFERENCES prices.price_snapshot
);
GRANT SELECT ON prices.price_snapshot, prices.card_price, prices.active_price_snapshot TO price_reader;
GRANT SELECT, INSERT ON prices.price_snapshot, prices.card_price TO price_publisher;
GRANT SELECT, INSERT, UPDATE ON prices.active_price_snapshot TO price_publisher;
GRANT MAINTAIN ON prices.card_price TO price_publisher;
