-- From feature pipeline card-usage-v8 on, a run's decks carry their whole list: the main
-- deck, which the run's cards already list their decks for, turned around so one row
-- reads a deck; its commanders; and its sideboard as the source reported it, with names,
-- since a sideboard card may be in no main deck. A sideboard the source did not fully
-- report is NULL, not empty. Decks of older runs keep NULL lists.
ALTER TABLE scores.score_run_deck
 ADD COLUMN mainboard uuid[],
 ADD COLUMN mainboard_copies smallint[] CHECK (mainboard_copies IS NULL OR 1 <= ALL(mainboard_copies)),
 ADD COLUMN commanders uuid[],
 ADD COLUMN sideboard uuid[],
 ADD COLUMN sideboard_names text[] CHECK (sideboard_names IS NULL OR '' <> ALL(sideboard_names)),
 ADD COLUMN sideboard_copies smallint[] CHECK (sideboard_copies IS NULL OR 1 <= ALL(sideboard_copies)),
 -- A listed deck states its main deck and commanders together, one copy count per card,
 -- and its commanders are main deck cards.
 ADD CHECK ((mainboard IS NULL) = (mainboard_copies IS NULL) AND (mainboard IS NULL) = (commanders IS NULL)),
 ADD CHECK (mainboard IS NULL
   OR (cardinality(mainboard) > 0 AND cardinality(mainboard_copies) = cardinality(mainboard)
     AND commanders <@ mainboard)),
 ADD CHECK ((sideboard IS NULL) = (sideboard_names IS NULL) AND (sideboard IS NULL) = (sideboard_copies IS NULL)),
 ADD CHECK (sideboard IS NULL
   OR (mainboard IS NOT NULL AND cardinality(sideboard_names) = cardinality(sideboard)
     AND cardinality(sideboard_copies) = cardinality(sideboard)));

-- The view was expanded when it was created, so it needs the new columns spelled again.
CREATE OR REPLACE VIEW scores.published_score_run_deck AS
 SELECT r.* FROM scores.score_run_deck r JOIN scores.score_run s USING(score_run_id) WHERE s.state='published';

-- Promotion also checks that a run's deck lists are all there and name as many decks
-- as its cards do.
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
 -- From card-usage-v8 on every deck carries its list, which names each card's decks once.
 IF EXISTS(SELECT FROM score_run_deck WHERE score_run_id=run.score_run_id AND mainboard IS NOT NULL)
 AND (EXISTS(SELECT FROM score_run_deck WHERE score_run_id=run.score_run_id AND mainboard IS NULL)
   OR (SELECT sum(cardinality(mainboard)) FROM score_run_deck WHERE score_run_id=run.score_run_id)
      <> (SELECT sum(deck_count) FROM score_run_card WHERE score_run_id=run.score_run_id)) THEN
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
