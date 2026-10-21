-- From feature pipeline card-usage-v5 on, a run describes each archetype the way it
-- describes a card: its decks' events, top cuts, match record, performance against the
-- field and trend, plus the commanders that name a commander archetype. That ranks the
-- commanders of EDH and its relatives. Rows of older runs keep NULL for all of it.
ALTER TABLE scores.score_run_archetype
 ADD COLUMN commanders uuid[],
 ADD COLUMN event_count integer CHECK (event_count IS NULL OR event_count BETWEEN 1 AND deck_count),
 ADD COLUMN top_cut_count integer CHECK (top_cut_count IS NULL OR top_cut_count >= 0),
 ADD COLUMN top_cut_known_decks integer CHECK (top_cut_known_decks IS NULL OR top_cut_known_decks BETWEEN 0 AND deck_count),
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
 -- A described archetype states all of it; a top-cut count needs a known result and a
 -- win rate a game, as for cards.
 ADD CHECK ((record_decks IS NULL) = (record_wins IS NULL)
   AND (record_wins IS NULL) = (record_losses IS NULL)
   AND (record_losses IS NULL) = (record_draws IS NULL)
   AND (record_draws IS NULL) = (event_count IS NULL)
   AND (event_count IS NULL) = (top_cut_known_decks IS NULL)
   AND (top_cut_known_decks IS NULL) = (commanders IS NULL)
   AND (commanders IS NULL) = (series_decks IS NULL)),
 ADD CHECK (top_cut_count IS NULL OR top_cut_known_decks > 0),
 ADD CHECK (win_rate IS NULL OR record_wins + record_losses + record_draws > 0);

-- The view was expanded when it was created, so it needs the new columns spelled again.
CREATE OR REPLACE VIEW scores.published_score_run_archetype AS
 SELECT r.* FROM scores.score_run_archetype r JOIN scores.score_run s USING(score_run_id) WHERE s.state='published';
