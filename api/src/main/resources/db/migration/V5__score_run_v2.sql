-- Score-run file v2 adds, per card, the match record and copies of its decks, its
-- performance against the field, a weekly trend series and its leading archetypes;
-- per run, each archetype's core cards. v1 rows keep NULL for what they never measured.
ALTER TABLE scores.score_run DROP CONSTRAINT score_run_schema_version_check;
ALTER TABLE scores.score_run ADD CONSTRAINT score_run_schema_version_check
 CHECK (schema_version IN ('score-run-file-v1','score-run-file-v2'));

ALTER TABLE scores.score_run_card
 ADD COLUMN mainboard_copies integer CHECK (mainboard_copies IS NULL OR mainboard_copies >= deck_count),
 ADD COLUMN record_decks integer CHECK (record_decks IS NULL OR record_decks BETWEEN 0 AND deck_count),
 ADD COLUMN record_wins integer CHECK (record_wins IS NULL OR record_wins >= 0),
 ADD COLUMN record_losses integer CHECK (record_losses IS NULL OR record_losses >= 0),
 ADD COLUMN record_draws integer CHECK (record_draws IS NULL OR record_draws >= 0),
 ADD COLUMN win_rate double precision CHECK (win_rate IS NULL OR win_rate BETWEEN 0 AND 1),
 ADD COLUMN win_rate_delta double precision CHECK (win_rate_delta IS NULL OR win_rate_delta BETWEEN -1 AND 1),
 ADD COLUMN win_rate_ci95 double precision CHECK (win_rate_ci95 IS NULL OR win_rate_ci95 BETWEEN 0 AND 1),
 ADD COLUMN top_cut_lift double precision CHECK (top_cut_lift IS NULL OR top_cut_lift >= 0),
 ADD COLUMN share_delta double precision CHECK (share_delta IS NULL OR share_delta BETWEEN -1 AND 1),
 ADD COLUMN series_decks integer[] CHECK (series_decks IS NULL OR cardinality(series_decks) = 12),
 ADD COLUMN archetype_count integer CHECK (archetype_count IS NULL OR archetype_count >= 0),
 -- A record is either fully stated or absent; a win rate needs at least one game.
 ADD CHECK ((record_decks IS NULL) = (record_wins IS NULL)
   AND (record_wins IS NULL) = (record_losses IS NULL)
   AND (record_losses IS NULL) = (record_draws IS NULL)),
 ADD CHECK (win_rate IS NULL OR record_wins + record_losses + record_draws > 0);

-- The view was expanded when it was created, so it needs the new columns spelled again.
CREATE OR REPLACE VIEW scores.published_score_run_card AS
 SELECT r.* FROM scores.score_run_card r JOIN scores.score_run s USING(score_run_id) WHERE s.state='published';

CREATE TABLE scores.score_run_card_archetype (
 score_run_id text NOT NULL,
 oracle_id uuid NOT NULL,
 position smallint NOT NULL CHECK (position BETWEEN 1 AND 3),
 label text NOT NULL CHECK (label <> ''),
 deck_count integer NOT NULL CHECK (deck_count > 0),
 PRIMARY KEY (score_run_id, oracle_id, position),
 UNIQUE (score_run_id, oracle_id, label),
 FOREIGN KEY (score_run_id, oracle_id) REFERENCES scores.score_run_card
);
CREATE TABLE scores.score_run_archetype (
 score_run_id text NOT NULL REFERENCES scores.score_run,
 label text NOT NULL CHECK (label <> ''),
 deck_count integer NOT NULL CHECK (deck_count > 0),
 core_cards uuid[] NOT NULL,
 PRIMARY KEY (score_run_id, label)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['score_run_card_archetype','score_run_archetype'] LOOP
  EXECUTE format('CREATE TRIGGER staging_only BEFORE INSERT OR UPDATE OR DELETE ON scores.%I FOR EACH ROW EXECUTE FUNCTION scores.guard_staging()',t);
  EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON scores.%I TO score_publisher',t);
  EXECUTE format('CREATE VIEW scores.published_%I AS SELECT r.* FROM scores.%I r JOIN scores.score_run s USING(score_run_id) WHERE s.state=''published''',t,t);
  EXECUTE format('GRANT SELECT ON scores.published_%I TO score_reader',t);
 END LOOP;
END $$;
-- The publisher refreshes planner statistics after loading a run (PostgreSQL 17 MAINTAIN).
GRANT MAINTAIN ON scores.score_run_card, scores.score_run_method, scores.card_score,
 scores.card_score_input, scores.score_run_card_archetype, scores.score_run_archetype TO score_publisher;
-- Ranks against the previous run look runs up by source, format and publication time.
CREATE INDEX score_run_history ON scores.score_run(source, format_name, published_at DESC);

-- Promotion also checks the archetype rows a v2 header counts; v1 headers count none.
CREATE OR REPLACE FUNCTION scores.promote_score_publication(attempt uuid) RETURNS void
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
 FOR item IN SELECT * FROM (VALUES ('cards','score_run_card'),('methods','score_run_method'),('scores','card_score'),('inputs','card_score_input'),
   ('card_archetypes','score_run_card_archetype'),('archetypes','score_run_archetype')) AS counts(label,relation) LOOP
  EXECUTE format('SELECT count(*) FROM scores.%I WHERE score_run_id=$1',item.relation) INTO actual USING run.score_run_id;
  IF actual <> coalesce((run.row_counts->>item.label)::bigint,0) THEN RAISE EXCEPTION 'row_count_mismatch'; END IF;
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
