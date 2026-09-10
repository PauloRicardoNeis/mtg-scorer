-- The migration user owns objects; runtime roles cannot replace transition functions.
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='catalog_reader') THEN CREATE ROLE catalog_reader NOLOGIN; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='catalog_publisher') THEN CREATE ROLE catalog_publisher NOLOGIN; END IF;
END $$;
CREATE SCHEMA catalog;
REVOKE ALL ON SCHEMA catalog FROM PUBLIC;
GRANT USAGE ON SCHEMA catalog TO catalog_reader, catalog_publisher;

CREATE TABLE catalog.catalog_snapshot (
 catalog_snapshot_id text PRIMARY KEY CHECK (catalog_snapshot_id ~ '^catalog-[0-9a-f]{64}$'),
 source text NOT NULL CHECK (source = 'scryfall'),
 parser_version text NOT NULL,
 schema_version text NOT NULL CHECK (schema_version = 'catalog-publication-v1'),
 created_at timestamptz NOT NULL,
 selection jsonb NOT NULL,
 manifest jsonb NOT NULL,
 export_sha256 text NOT NULL CHECK (export_sha256 ~ '^[0-9a-f]{64}$'),
 state text NOT NULL CHECK (state IN ('staging','ready','published')),
 published_at timestamptz,
 CHECK ((state = 'published') = (published_at IS NOT NULL))
);
CREATE TABLE catalog.catalog_card (
 catalog_snapshot_id text NOT NULL REFERENCES catalog.catalog_snapshot,
 oracle_id uuid NOT NULL, source_scryfall_id uuid NOT NULL,
 name text NOT NULL CHECK (name <> ''), name_key text COLLATE "C" NOT NULL CHECK (name_key <> ''),
 layout text NOT NULL, mana_cost text, mana_value double precision,
 oracle_text text, type_line text, colors text[], color_identity text[],
 PRIMARY KEY(catalog_snapshot_id, oracle_id),
 CHECK (mana_value IS NULL OR (mana_value >= 0 AND mana_value < 'Infinity'::float8)),
 CHECK (colors <@ ARRAY['W','U','B','R','G']),
 CHECK (color_identity <@ ARRAY['W','U','B','R','G'])
);
CREATE TABLE catalog.catalog_face (
 catalog_snapshot_id text NOT NULL, oracle_id uuid NOT NULL,
 face_index integer NOT NULL CHECK(face_index >= 0), name text NOT NULL,
 mana_cost text, oracle_text text, type_line text, colors text[],
 PRIMARY KEY(catalog_snapshot_id, oracle_id, face_index),
 FOREIGN KEY(catalog_snapshot_id, oracle_id) REFERENCES catalog.catalog_card,
 CHECK (colors <@ ARRAY['W','U','B','R','G'])
);
CREATE TABLE catalog.catalog_printing (
 catalog_snapshot_id text NOT NULL, scryfall_id uuid NOT NULL, oracle_id uuid NOT NULL,
 set_code text NOT NULL CHECK(set_code ~ '^[a-z0-9]{2,8}$'), set_name text NOT NULL,
 collector_number text NOT NULL,
 rarity text NOT NULL CHECK(rarity IN ('common','uncommon','rare','mythic','special','bonus')),
 released_on date, language text NOT NULL, games text[] NOT NULL,
 source_uri text NOT NULL CHECK(source_uri LIKE 'https://%'),
 retrieved_at timestamptz NOT NULL, raw_snapshot_ref text NOT NULL,
 raw_sha256 text NOT NULL CHECK(raw_sha256 ~ '^[0-9a-f]{64}$'),
 PRIMARY KEY(catalog_snapshot_id, scryfall_id),
 UNIQUE(catalog_snapshot_id, scryfall_id, oracle_id),
 FOREIGN KEY(catalog_snapshot_id, oracle_id) REFERENCES catalog.catalog_card,
 CHECK (games <@ ARRAY['paper','arena','mtgo'])
);
ALTER TABLE catalog.catalog_card ADD CONSTRAINT representative_same_card
 FOREIGN KEY(catalog_snapshot_id, source_scryfall_id, oracle_id)
 REFERENCES catalog.catalog_printing(catalog_snapshot_id, scryfall_id, oracle_id)
 DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE catalog.catalog_printing_image (
 catalog_snapshot_id text NOT NULL, scryfall_id uuid NOT NULL,
 image_slot integer NOT NULL CHECK(image_slot >= -1), source_uri text NOT NULL,
 artist text, PRIMARY KEY(catalog_snapshot_id, scryfall_id, image_slot),
 FOREIGN KEY(catalog_snapshot_id,scryfall_id) REFERENCES catalog.catalog_printing,
 CHECK(source_uri LIKE 'https://%')
);
CREATE TABLE catalog.catalog_alias (
 catalog_snapshot_id text NOT NULL, oracle_id uuid NOT NULL,
 alias_key text NOT NULL CHECK(alias_key <> ''), kind text NOT NULL CHECK(kind IN ('canonical','face')),
 PRIMARY KEY(catalog_snapshot_id,oracle_id,alias_key,kind),
 FOREIGN KEY(catalog_snapshot_id,oracle_id) REFERENCES catalog.catalog_card
);
CREATE TABLE catalog.catalog_publication_attempt (
 attempt_id uuid PRIMARY KEY, catalog_snapshot_id text NOT NULL REFERENCES catalog.catalog_snapshot,
 expected_previous_snapshot_id text REFERENCES catalog.catalog_snapshot,
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(), finished_at timestamptz,
 state text NOT NULL CHECK(state IN ('running','succeeded','failed')), error_code text,
 CHECK ((state = 'running') = (finished_at IS NULL))
);
CREATE TABLE catalog.active_catalog (
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 catalog_snapshot_id text NOT NULL REFERENCES catalog.catalog_snapshot
);
CREATE INDEX card_name_page ON catalog.catalog_card(catalog_snapshot_id,name_key,oracle_id);
CREATE INDEX printing_card_page ON catalog.catalog_printing(catalog_snapshot_id,oracle_id,scryfall_id);
CREATE INDEX printing_pool ON catalog.catalog_printing(catalog_snapshot_id,set_code,rarity,oracle_id);
CREATE INDEX alias_search ON catalog.catalog_alias(catalog_snapshot_id,alias_key,oracle_id);

CREATE FUNCTION catalog.guard_staging() RETURNS trigger LANGUAGE plpgsql
 SECURITY DEFINER SET search_path = pg_catalog,catalog AS $$
DECLARE sid text;
BEGIN
 PERFORM pg_advisory_xact_lock(724602);
 sid := CASE WHEN TG_OP='DELETE' THEN OLD.catalog_snapshot_id ELSE NEW.catalog_snapshot_id END;
 IF TG_OP='UPDATE' AND OLD.catalog_snapshot_id <> NEW.catalog_snapshot_id THEN
   RAISE EXCEPTION 'snapshot_key_immutable';
 END IF;
 IF NOT EXISTS(SELECT FROM catalog_snapshot WHERE catalog_snapshot_id=sid AND state='staging') THEN
   RAISE EXCEPTION 'snapshot_immutable';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['catalog_card','catalog_face','catalog_printing','catalog_printing_image','catalog_alias'] LOOP
  EXECUTE format('CREATE TRIGGER staging_only BEFORE INSERT OR UPDATE OR DELETE ON catalog.%I FOR EACH ROW EXECUTE FUNCTION catalog.guard_staging()',t);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON catalog.%I TO catalog_publisher',t);
  EXECUTE format('CREATE VIEW catalog.published_%I AS SELECT r.* FROM catalog.%I r JOIN catalog.catalog_snapshot s USING(catalog_snapshot_id) WHERE s.state=''published''',t,t);
  EXECUTE format('GRANT SELECT ON catalog.published_%I TO catalog_reader',t);
 END LOOP;
END $$;
CREATE VIEW catalog.published_snapshot AS SELECT * FROM catalog.catalog_snapshot WHERE state='published';
GRANT SELECT ON catalog.published_snapshot,catalog.active_catalog TO catalog_reader;
GRANT SELECT ON catalog.catalog_snapshot,catalog.catalog_publication_attempt,catalog.active_catalog TO catalog_publisher;

CREATE FUNCTION catalog.begin_publication(header jsonb, publication_manifest jsonb, attempt uuid, expected text)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
DECLARE sid text := header->>'catalog_snapshot_id'; existing catalog_snapshot;
BEGIN
 PERFORM pg_advisory_xact_lock(724602);
 UPDATE catalog_publication_attempt SET state='failed',finished_at=clock_timestamp(),error_code='abandoned_attempt' WHERE state='running';
 SELECT * INTO existing FROM catalog_snapshot WHERE catalog_snapshot_id=sid;
 IF FOUND THEN
  IF existing.export_sha256 <> publication_manifest->>'export_sha256' OR existing.manifest <> publication_manifest THEN
   RAISE EXCEPTION 'snapshot_content_conflict';
  END IF;
  IF existing.state='published' THEN RETURN false; END IF;
 ELSE
  INSERT INTO catalog_snapshot VALUES(sid,header->>'source',header->>'parser_version',header->>'schema_version',
   (header->>'created_at')::timestamptz,header->'selection',publication_manifest,publication_manifest->>'export_sha256','staging',NULL);
 END IF;
 INSERT INTO catalog_publication_attempt(attempt_id,catalog_snapshot_id,expected_previous_snapshot_id,state)
 VALUES(attempt,sid,expected,'running');
 RETURN true;
END $$;

CREATE FUNCTION catalog.fail_publication(attempt uuid, failure_code text) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(724602);
 IF failure_code NOT IN ('publication_failed','abandoned_attempt') THEN RAISE EXCEPTION 'invalid_failure_code'; END IF;
 UPDATE catalog_publication_attempt SET state='failed',finished_at=clock_timestamp(),error_code=failure_code
 WHERE attempt_id=attempt AND state='running';
END $$;

CREATE FUNCTION catalog.promote_publication(attempt uuid) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
DECLARE job catalog_publication_attempt; snapshot catalog_snapshot; actual bigint; item record;
BEGIN
 PERFORM pg_advisory_xact_lock(724602);
 SELECT * INTO STRICT job FROM catalog_publication_attempt WHERE attempt_id=attempt AND state='running' FOR UPDATE;
 SELECT * INTO STRICT snapshot FROM catalog_snapshot WHERE catalog_snapshot_id=job.catalog_snapshot_id AND state='staging' FOR UPDATE;
 IF (SELECT catalog_snapshot_id FROM active_catalog) IS DISTINCT FROM job.expected_previous_snapshot_id THEN
  RAISE EXCEPTION 'stale_promotion';
 END IF;
 FOR item IN SELECT * FROM (VALUES ('cards','catalog_card'),('faces','catalog_face'),('printings','catalog_printing'),('aliases','catalog_alias')) AS counts(label,relation) LOOP
  EXECUTE format('SELECT count(*) FROM catalog.%I WHERE catalog_snapshot_id=$1',item.relation) INTO actual USING job.catalog_snapshot_id;
  IF actual <> (snapshot.manifest->'row_counts'->>item.label)::bigint THEN RAISE EXCEPTION 'row_count_mismatch'; END IF;
 END LOOP;
 IF (snapshot.manifest->'row_counts'->>'cards')::bigint < 1 OR (snapshot.manifest->'row_counts'->>'printings')::bigint < 1 THEN
  RAISE EXCEPTION 'empty_catalog';
 END IF;
 IF EXISTS(SELECT FROM catalog_face WHERE catalog_snapshot_id=job.catalog_snapshot_id GROUP BY oracle_id HAVING min(face_index)<>0 OR max(face_index)<>count(*)-1) THEN
  RAISE EXCEPTION 'noncontiguous_faces';
 END IF;
 IF EXISTS(SELECT FROM catalog_card c WHERE c.catalog_snapshot_id=job.catalog_snapshot_id AND c.layout IN ('transform','modal_dfc','split','adventure','flip','double_faced_token','reversible_card') AND (SELECT count(*) FROM catalog_face f WHERE f.catalog_snapshot_id=c.catalog_snapshot_id AND f.oracle_id=c.oracle_id)<2) THEN
  RAISE EXCEPTION 'missing_faces';
 END IF;
 IF EXISTS(SELECT FROM catalog_card c WHERE c.catalog_snapshot_id=job.catalog_snapshot_id AND NOT EXISTS(SELECT FROM catalog_alias a WHERE a.catalog_snapshot_id=c.catalog_snapshot_id AND a.oracle_id=c.oracle_id AND a.alias_key=c.name_key AND a.kind='canonical')) THEN
  RAISE EXCEPTION 'missing_alias';
 END IF;
 IF EXISTS(SELECT FROM catalog_printing_image i JOIN catalog_printing p USING(catalog_snapshot_id,scryfall_id) WHERE i.catalog_snapshot_id=job.catalog_snapshot_id AND i.image_slot>=0 AND NOT EXISTS(SELECT FROM catalog_face f WHERE f.catalog_snapshot_id=p.catalog_snapshot_id AND f.oracle_id=p.oracle_id AND f.face_index=i.image_slot)) THEN
  RAISE EXCEPTION 'orphan_image_face';
 END IF;
 IF EXISTS(SELECT FROM catalog_printing WHERE catalog_snapshot_id=job.catalog_snapshot_id GROUP BY set_code HAVING count(DISTINCT set_name)>1)
 OR (SELECT count(DISTINCT set_code) FROM catalog_printing WHERE catalog_snapshot_id=job.catalog_snapshot_id)>4096 THEN
  RAISE EXCEPTION 'invalid_set_vocabulary';
 END IF;
 SET CONSTRAINTS ALL IMMEDIATE;
 UPDATE catalog_snapshot SET state='ready' WHERE catalog_snapshot_id=job.catalog_snapshot_id;
 UPDATE catalog_snapshot SET state='published',published_at=clock_timestamp() WHERE catalog_snapshot_id=job.catalog_snapshot_id;
 INSERT INTO active_catalog VALUES(true,job.catalog_snapshot_id) ON CONFLICT(singleton) DO UPDATE SET catalog_snapshot_id=EXCLUDED.catalog_snapshot_id;
 UPDATE catalog_publication_attempt SET state='succeeded',finished_at=clock_timestamp() WHERE attempt_id=attempt;
END $$;

CREATE FUNCTION catalog.rollback_catalog(target text, expected text) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(724602);
 IF (SELECT catalog_snapshot_id FROM active_catalog) IS DISTINCT FROM expected THEN RAISE EXCEPTION 'stale_promotion'; END IF;
 IF NOT EXISTS(SELECT FROM catalog_snapshot WHERE catalog_snapshot_id=target AND state='published') THEN RAISE EXCEPTION 'snapshot_not_published'; END IF;
 UPDATE active_catalog SET catalog_snapshot_id=target;
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA catalog FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.begin_publication(jsonb,jsonb,uuid,text),catalog.fail_publication(uuid,text),catalog.promote_publication(uuid),catalog.rollback_catalog(text,text) TO catalog_publisher;
