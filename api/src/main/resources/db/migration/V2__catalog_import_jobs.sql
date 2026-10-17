-- HTTP enqueues only; a separately operated Python process owns ingestion.
DO $$ BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='catalog_import_admin') THEN
  CREATE ROLE catalog_import_admin NOLOGIN;
 END IF;
END $$;
GRANT USAGE ON SCHEMA catalog TO catalog_import_admin;
CREATE TABLE catalog.catalog_import_job (
 job_id uuid PRIMARY KEY,
 state text NOT NULL CHECK(state IN ('queued','running','succeeded','failed')),
 stage text NOT NULL,
 requested_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 started_at timestamptz, updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 finished_at timestamptz,
 source_snapshot_id text, catalog_snapshot_id text,
 parser_version text, schema_version text,
 row_counts jsonb NOT NULL DEFAULT '{}', excluded_record_counts jsonb NOT NULL DEFAULT '{}',
 result text, error_code text,
 CHECK ((state IN ('succeeded','failed')) = (finished_at IS NOT NULL))
);
CREATE UNIQUE INDEX one_active_catalog_import ON catalog.catalog_import_job ((true))
 WHERE state IN ('queued','running');
GRANT SELECT,UPDATE ON catalog.catalog_import_job TO catalog_publisher;

-- A worker holds session lock 724603 throughout a job. A lost process/connection
-- releases it. Readers and new requests can then repair its durable running record.
CREATE FUNCTION catalog.recover_catalog_import() RETURNS void LANGUAGE plpgsql
 SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
BEGIN
 IF pg_try_advisory_xact_lock(724603) THEN
  UPDATE catalog_import_job SET state='failed', finished_at=clock_timestamp(),
   updated_at=clock_timestamp(), error_code='worker_interrupted'
  WHERE state='running';
 END IF;
END $$;
CREATE FUNCTION catalog.request_catalog_import(id uuid) RETURNS uuid LANGUAGE plpgsql
 SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
DECLARE existing uuid;
BEGIN
 PERFORM pg_advisory_xact_lock(724604);
 PERFORM recover_catalog_import();
 SELECT job_id INTO existing FROM catalog_import_job WHERE state IN ('queued','running');
 IF FOUND THEN RETURN existing; END IF;
 INSERT INTO catalog_import_job(job_id,state,stage) VALUES(id,'queued','queued');
 RETURN id;
END $$;
CREATE FUNCTION catalog.catalog_import_status(id uuid) RETURNS jsonb LANGUAGE plpgsql
 SECURITY DEFINER SET search_path=pg_catalog,catalog AS $$
DECLARE result jsonb;
BEGIN
 PERFORM recover_catalog_import();
 SELECT to_jsonb(j) || jsonb_build_object('status_url','/api/v1/admin/catalog-imports/' || job_id)
 INTO result FROM catalog_import_job j WHERE job_id=id;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION catalog.recover_catalog_import(),
 catalog.request_catalog_import(uuid),catalog.catalog_import_status(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION catalog.request_catalog_import(uuid),
 catalog.catalog_import_status(uuid) TO catalog_import_admin;
GRANT EXECUTE ON FUNCTION catalog.recover_catalog_import() TO catalog_publisher;
