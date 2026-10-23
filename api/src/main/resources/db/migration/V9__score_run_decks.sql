-- From feature pipeline card-usage-v7 on, a run lists its cohort's decks, newest event
-- first, and every card its decks by their position in that list with the mainboard
-- copies each plays, so a card's page can show the decks behind its counts. A deck
-- carries its event's name, page, date and size, its archetype and the result its
-- standing reported. Older runs have no decks and keep NULL deck lists.
ALTER TABLE scores.score_run_card
 ADD COLUMN deck_positions integer[] CHECK (deck_positions IS NULL OR 0 <= ALL(deck_positions)),
 ADD COLUMN deck_copies smallint[] CHECK (deck_copies IS NULL OR 1 <= ALL(deck_copies)),
 -- Both lists or neither, with one entry for each of the card's decks.
 ADD CHECK ((deck_positions IS NULL) = (deck_copies IS NULL)),
 ADD CHECK (deck_positions IS NULL
   OR (cardinality(deck_positions) = deck_count AND cardinality(deck_copies) = deck_count));

-- The view was expanded when it was created, so it needs the new columns spelled again.
CREATE OR REPLACE VIEW scores.published_score_run_card AS
 SELECT r.* FROM scores.score_run_card r JOIN scores.score_run s USING(score_run_id) WHERE s.state='published';

CREATE TABLE scores.score_run_deck (
 score_run_id text NOT NULL REFERENCES scores.score_run,
 position integer NOT NULL CHECK (position >= 0),
 source_deck_id text NOT NULL CHECK (source_deck_id <> ''),
 source_event_id text NOT NULL CHECK (source_event_id <> ''),
 event_name text CHECK (event_name <> ''),
 event_url text CHECK (event_url ~ '^https://\S+$'),
 occurred_on date NOT NULL,
 players integer CHECK (players > 0),
 archetype_label text CHECK (archetype_label <> ''),
 final_rank integer CHECK (final_rank > 0),
 made_top_cut boolean,
 record_wins integer CHECK (record_wins >= 0),
 record_losses integer CHECK (record_losses >= 0),
 record_draws integer CHECK (record_draws >= 0),
 PRIMARY KEY (score_run_id, position),
 UNIQUE (score_run_id, source_deck_id),
 -- A record is either fully stated or absent.
 CHECK ((record_wins IS NULL) = (record_losses IS NULL)
   AND (record_losses IS NULL) = (record_draws IS NULL))
);
CREATE TRIGGER staging_only BEFORE INSERT OR UPDATE OR DELETE ON scores.score_run_deck
 FOR EACH ROW EXECUTE FUNCTION scores.guard_staging();
GRANT SELECT,INSERT,UPDATE,DELETE ON scores.score_run_deck TO score_publisher;
CREATE VIEW scores.published_score_run_deck AS
 SELECT r.* FROM scores.score_run_deck r JOIN scores.score_run s USING(score_run_id) WHERE s.state='published';
GRANT SELECT ON scores.published_score_run_deck TO score_reader;
GRANT MAINTAIN ON scores.score_run_deck TO score_publisher;

-- Promotion also counts the decks a header states, and checks that a run lists decks for
-- every card or for none, each card's last deck being one of the run's.
CREATE OR REPLACE FUNCTION scores.promote_score_publication(attempt uuid) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,scores AS $$
DECLARE job score_publication_attempt; run score_run; actual bigint; item record; expected_scores bigint;
 decks bigint;
BEGIN
 PERFORM pg_advisory_xact_lock(724603);
 SELECT * INTO STRICT job FROM score_publication_attempt WHERE attempt_id=attempt AND state='running' FOR UPDATE;
 SELECT * INTO STRICT run FROM score_run WHERE score_run_id=job.score_run_id AND state='staging' FOR UPDATE;
 IF (SELECT score_run_id FROM active_score_run WHERE source=run.source AND format_name=run.format_name)
    IS DISTINCT FROM job.expected_previous_run_id THEN
  RAISE EXCEPTION 'stale_promotion';
 END IF;
 FOR item IN SELECT * FROM (VALUES ('cards','score_run_card'),('methods','score_run_method'),('scores','card_score'),('inputs','card_score_input'),
   ('card_archetypes','score_run_card_archetype'),('archetypes','score_run_archetype'),('decks','score_run_deck')) AS counts(label,relation) LOOP
  EXECUTE format('SELECT count(*) FROM scores.%I WHERE score_run_id=$1',item.relation) INTO actual USING run.score_run_id;
  IF actual <> coalesce((run.row_counts->>item.label)::bigint,0) THEN RAISE EXCEPTION 'row_count_mismatch'; END IF;
 END LOOP;
 IF NOT EXISTS(SELECT FROM score_run_card WHERE score_run_id=run.score_run_id AND scored)
 OR NOT EXISTS(SELECT FROM score_run_method WHERE score_run_id=run.score_run_id) THEN
  RAISE EXCEPTION 'empty_score_run';
 END IF;
 decks := coalesce((run.row_counts->>'decks')::bigint,0);
 IF EXISTS(SELECT FROM score_run_card c WHERE c.score_run_id=run.score_run_id
   AND ((c.deck_positions IS NULL) <> (decks = 0)
     OR c.deck_positions[cardinality(c.deck_positions)] >= decks)) THEN
  RAISE EXCEPTION 'invalid_decks';
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
