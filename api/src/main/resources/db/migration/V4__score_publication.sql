-- Score runs are batch results computed by Python; the API only reads published runs.
-- Mirrors catalog publication: rows change only while their run is staging, and
-- guarded functions own every state transition. Each (source, format) has one active run.
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='score_reader') THEN CREATE ROLE score_reader NOLOGIN; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='score_publisher') THEN CREATE ROLE score_publisher NOLOGIN; END IF;
END $$;
CREATE SCHEMA scores;
REVOKE ALL ON SCHEMA scores FROM PUBLIC;
GRANT USAGE ON SCHEMA scores TO score_reader, score_publisher;

CREATE TABLE scores.score_run (
 score_run_id text PRIMARY KEY CHECK (score_run_id ~ '^scores-[0-9a-f]{64}$'),
 schema_version text NOT NULL CHECK (schema_version = 'score-run-file-v1'),
 source text NOT NULL CHECK (source ~ '^[a-z0-9][a-z0-9-]*$'),
 format_name text NOT NULL CHECK (format_name <> ''),
 window_starts_on date NOT NULL,
 window_ends_before date NOT NULL CHECK (window_ends_before > window_starts_on),
 dataset_snapshot_id text NOT NULL CHECK (dataset_snapshot_id <> ''),
 parser_version text NOT NULL CHECK (parser_version <> ''),
 feature_pipeline_version text NOT NULL CHECK (feature_pipeline_version <> ''),
 cohort_rules_hash text NOT NULL CHECK (cohort_rules_hash ~ '^[0-9a-f]{64}$'),
 population_rule text NOT NULL CHECK (population_rule <> ''),
 attribution text NOT NULL CHECK (attribution <> ''),
 -- Cohort, population and raw-file provenance, exactly as the run file states them.
 summary jsonb NOT NULL,
 row_counts jsonb NOT NULL,
 results_sha256 text NOT NULL CHECK (results_sha256 ~ '^[0-9a-f]{64}$'),
 state text NOT NULL CHECK (state IN ('staging','published')),
 published_at timestamptz,
 CHECK ((state = 'published') = (published_at IS NOT NULL))
);
CREATE TABLE scores.score_run_card (
 score_run_id text NOT NULL REFERENCES scores.score_run,
 oracle_id uuid NOT NULL,
 name text NOT NULL CHECK (name <> ''),
 scored boolean NOT NULL,
 deck_count integer NOT NULL CHECK (deck_count > 0),
 event_count integer NOT NULL CHECK (event_count > 0 AND event_count <= deck_count),
 top_cut_count integer,
 top_cut_known_decks integer NOT NULL CHECK (top_cut_known_decks BETWEEN 0 AND deck_count),
 archetype_label text CHECK (archetype_label <> ''),
 archetype_deck_count integer NOT NULL CHECK (archetype_deck_count >= 0),
 labelled_deck_count integer NOT NULL CHECK (labelled_deck_count BETWEEN archetype_deck_count AND deck_count),
 PRIMARY KEY (score_run_id, oracle_id),
 -- Unknown is not zero: a top-cut count exists exactly when some result was known.
 CHECK ((top_cut_count IS NULL) = (top_cut_known_decks = 0)),
 CHECK (top_cut_count IS NULL OR top_cut_count BETWEEN 0 AND top_cut_known_decks),
 CHECK ((archetype_label IS NULL) = (labelled_deck_count = 0)),
 CHECK ((archetype_label IS NULL) = (archetype_deck_count = 0))
);
CREATE TABLE scores.score_run_method (
 score_run_id text NOT NULL REFERENCES scores.score_run,
 method_id text NOT NULL CHECK (method_id ~ '^[a-z0-9][a-z0-9-]*$'),
 method_version text NOT NULL CHECK (method_version <> ''),
 method_config_hash text NOT NULL CHECK (method_config_hash ~ '^[0-9a-f]{64}$'),
 label text NOT NULL CHECK (label <> ''),
 description text NOT NULL CHECK (description <> ''),
 outputs text[] NOT NULL CHECK (cardinality(outputs) > 0),
 PRIMARY KEY (score_run_id, method_id)
);
CREATE TABLE scores.card_score (
 score_run_id text NOT NULL,
 method_id text NOT NULL,
 oracle_id uuid NOT NULL,
 output text NOT NULL CHECK (output <> ''),
 -- NULL means the method could not score the card, never zero.
 value double precision CHECK (value IS NULL OR (value > '-Infinity'::float8 AND value < 'Infinity'::float8)),
 PRIMARY KEY (score_run_id, method_id, oracle_id, output),
 FOREIGN KEY (score_run_id, method_id) REFERENCES scores.score_run_method,
 FOREIGN KEY (score_run_id, oracle_id) REFERENCES scores.score_run_card
);
CREATE TABLE scores.card_score_input (
 score_run_id text NOT NULL,
 method_id text NOT NULL,
 oracle_id uuid NOT NULL,
 input_name text NOT NULL CHECK (input_name <> ''),
 value double precision CHECK (value IS NULL OR (value > '-Infinity'::float8 AND value < 'Infinity'::float8)),
 PRIMARY KEY (score_run_id, method_id, oracle_id, input_name),
 FOREIGN KEY (score_run_id, method_id) REFERENCES scores.score_run_method,
 FOREIGN KEY (score_run_id, oracle_id) REFERENCES scores.score_run_card
);
CREATE TABLE scores.score_publication_attempt (
 attempt_id uuid PRIMARY KEY,
 score_run_id text NOT NULL REFERENCES scores.score_run,
 expected_previous_run_id text REFERENCES scores.score_run,
 started_at timestamptz NOT NULL DEFAULT clock_timestamp(), finished_at timestamptz,
 state text NOT NULL CHECK (state IN ('running','succeeded','failed')), error_code text,
 CHECK ((state = 'running') = (finished_at IS NULL))
);
CREATE TABLE scores.active_score_run (
 source text NOT NULL,
 format_name text NOT NULL,
 score_run_id text NOT NULL REFERENCES scores.score_run,
 PRIMARY KEY (source, format_name)
);
CREATE INDEX card_score_ranking ON scores.card_score(score_run_id, method_id, output, value DESC NULLS LAST, oracle_id);
CREATE INDEX score_run_card_usage ON scores.score_run_card(score_run_id, deck_count DESC, oracle_id);

CREATE FUNCTION scores.guard_staging() RETURNS trigger LANGUAGE plpgsql
 SECURITY DEFINER SET search_path = pg_catalog,scores AS $$
DECLARE rid text;
BEGIN
 PERFORM pg_advisory_xact_lock(724603);
 rid := CASE WHEN TG_OP='DELETE' THEN OLD.score_run_id ELSE NEW.score_run_id END;
 IF TG_OP='UPDATE' AND OLD.score_run_id <> NEW.score_run_id THEN
   RAISE EXCEPTION 'score_run_key_immutable';
 END IF;
 IF NOT EXISTS(SELECT FROM score_run WHERE score_run_id=rid AND state='staging') THEN
   RAISE EXCEPTION 'score_run_immutable';
 END IF;
 IF TG_OP='DELETE' THEN RETURN OLD; END IF;
 RETURN NEW;
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['score_run_card','score_run_method','card_score','card_score_input'] LOOP
  EXECUTE format('CREATE TRIGGER staging_only BEFORE INSERT OR UPDATE OR DELETE ON scores.%I FOR EACH ROW EXECUTE FUNCTION scores.guard_staging()',t);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON scores.%I TO score_publisher',t);
  EXECUTE format('CREATE VIEW scores.published_%I AS SELECT r.* FROM scores.%I r JOIN scores.score_run s USING(score_run_id) WHERE s.state=''published''',t,t);
  EXECUTE format('GRANT SELECT ON scores.published_%I TO score_reader',t);
 END LOOP;
END $$;
CREATE VIEW scores.published_score_run AS SELECT * FROM scores.score_run WHERE state='published';
GRANT SELECT ON scores.published_score_run, scores.active_score_run TO score_reader;
GRANT SELECT ON scores.score_run, scores.score_publication_attempt, scores.active_score_run TO score_publisher;

CREATE FUNCTION scores.begin_score_publication(header jsonb, attempt uuid, expected text)
 RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scores AS $$
DECLARE rid text := header->>'score_run_id'; existing score_run;
BEGIN
 PERFORM pg_advisory_xact_lock(724603);
 UPDATE score_publication_attempt SET state='failed',finished_at=clock_timestamp(),error_code='abandoned_attempt' WHERE state='running';
 SELECT * INTO existing FROM score_run WHERE score_run_id=rid;
 IF FOUND THEN
  IF existing.results_sha256 <> header->>'results_sha256' OR existing.row_counts <> header->'row_counts' THEN
   RAISE EXCEPTION 'score_run_content_conflict';
  END IF;
  IF existing.state='published' THEN RETURN false; END IF;
 ELSE
  INSERT INTO score_run VALUES(rid,header->>'schema_version',header->>'source',header->>'format_name',
   (header->>'window_starts_on')::date,(header->>'window_ends_before')::date,header->>'dataset_snapshot_id',
   header->>'parser_version',header->>'feature_pipeline_version',header->>'cohort_rules_hash',
   header->>'population_rule',header->>'attribution',header->'summary',header->'row_counts',
   header->>'results_sha256','staging',NULL);
 END IF;
 INSERT INTO score_publication_attempt(attempt_id,score_run_id,expected_previous_run_id,state)
 VALUES(attempt,rid,expected,'running');
 RETURN true;
END $$;

CREATE FUNCTION scores.fail_score_publication(attempt uuid, failure_code text) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scores AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(724603);
 IF failure_code NOT IN ('publication_failed','abandoned_attempt') THEN RAISE EXCEPTION 'invalid_failure_code'; END IF;
 UPDATE score_publication_attempt SET state='failed',finished_at=clock_timestamp(),error_code=failure_code
 WHERE attempt_id=attempt AND state='running';
END $$;

CREATE FUNCTION scores.promote_score_publication(attempt uuid) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scores AS $$
DECLARE job score_publication_attempt; run score_run; actual bigint; item record; expected_scores bigint;
BEGIN
 PERFORM pg_advisory_xact_lock(724603);
 SELECT * INTO STRICT job FROM score_publication_attempt WHERE attempt_id=attempt AND state='running' FOR UPDATE;
 SELECT * INTO STRICT run FROM score_run WHERE score_run_id=job.score_run_id AND state='staging' FOR UPDATE;
 IF (SELECT score_run_id FROM active_score_run WHERE source=run.source AND format_name=run.format_name)
    IS DISTINCT FROM job.expected_previous_run_id THEN
  RAISE EXCEPTION 'stale_promotion';
 END IF;
 FOR item IN SELECT * FROM (VALUES ('cards','score_run_card'),('methods','score_run_method'),('scores','card_score'),('inputs','card_score_input')) AS counts(label,relation) LOOP
  EXECUTE format('SELECT count(*) FROM scores.%I WHERE score_run_id=$1',item.relation) INTO actual USING run.score_run_id;
  IF actual <> (run.row_counts->>item.label)::bigint THEN RAISE EXCEPTION 'row_count_mismatch'; END IF;
 END LOOP;
 IF NOT EXISTS(SELECT FROM score_run_card WHERE score_run_id=run.score_run_id AND scored)
 OR NOT EXISTS(SELECT FROM score_run_method WHERE score_run_id=run.score_run_id) THEN
  RAISE EXCEPTION 'empty_score_run';
 END IF;
 -- Scores belong only to scored cards and to their method's declared outputs...
 IF EXISTS(SELECT FROM card_score s
   JOIN score_run_method m USING(score_run_id,method_id)
   JOIN score_run_card c USING(score_run_id,oracle_id)
   WHERE s.score_run_id=run.score_run_id AND (NOT c.scored OR NOT s.output = ANY(m.outputs)))
 OR EXISTS(SELECT FROM card_score_input i JOIN score_run_card c USING(score_run_id,oracle_id)
   WHERE i.score_run_id=run.score_run_id AND NOT c.scored) THEN
  RAISE EXCEPTION 'invalid_scores';
 END IF;
 -- ...and, given unique keys, the right count means every method scored every scored card.
 SELECT (SELECT sum(cardinality(outputs)) FROM score_run_method WHERE score_run_id=run.score_run_id)
      * (SELECT count(*) FROM score_run_card WHERE score_run_id=run.score_run_id AND scored)
   INTO expected_scores;
 IF (SELECT count(*) FROM card_score WHERE score_run_id=run.score_run_id) <> expected_scores THEN
  RAISE EXCEPTION 'incomplete_scores';
 END IF;
 UPDATE score_run SET state='published',published_at=clock_timestamp() WHERE score_run_id=run.score_run_id;
 INSERT INTO active_score_run VALUES(run.source,run.format_name,run.score_run_id)
  ON CONFLICT(source,format_name) DO UPDATE SET score_run_id=EXCLUDED.score_run_id;
 UPDATE score_publication_attempt SET state='succeeded',finished_at=clock_timestamp() WHERE attempt_id=attempt;
END $$;

CREATE FUNCTION scores.rollback_score_run(target text, expected text) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scores AS $$
DECLARE run score_run;
BEGIN
 PERFORM pg_advisory_xact_lock(724603);
 SELECT * INTO run FROM score_run WHERE score_run_id=target AND state='published';
 IF NOT FOUND THEN RAISE EXCEPTION 'score_run_not_published'; END IF;
 IF (SELECT score_run_id FROM active_score_run WHERE source=run.source AND format_name=run.format_name)
    IS DISTINCT FROM expected THEN
  RAISE EXCEPTION 'stale_promotion';
 END IF;
 UPDATE active_score_run SET score_run_id=target WHERE source=run.source AND format_name=run.format_name;
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA scores FROM PUBLIC;
GRANT EXECUTE ON FUNCTION scores.begin_score_publication(jsonb,uuid,text),scores.fail_score_publication(uuid,text),scores.promote_score_publication(uuid),scores.rollback_score_run(text,text) TO score_publisher;
