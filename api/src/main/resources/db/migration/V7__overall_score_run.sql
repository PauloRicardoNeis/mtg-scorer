-- An overall run combines one active run per format into one grade per card. It is
-- published like a format's run under its own format name, "Overall", so it reuses the
-- score tables and their guarded publication; only its file version is new. Its cards
-- leave NULL what cannot be pooled across formats, and its summary lists the runs it
-- combined under "components".
ALTER TABLE scores.score_run DROP CONSTRAINT score_run_schema_version_check;
ALTER TABLE scores.score_run ADD CONSTRAINT score_run_schema_version_check
 CHECK (schema_version IN ('score-run-file-v1','score-run-file-v2','overall-run-file-v1'));
