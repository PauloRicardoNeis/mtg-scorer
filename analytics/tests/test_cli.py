"""The command line drives local batch operations; network and database calls are replaced."""

import io
import json
import sys
from pathlib import Path

import pytest

import mtg_scorer.ingest.scryfall as scryfall
import mtg_scorer.publish.postgres as postgres
import mtg_scorer.publish.score_postgres as score_postgres
from mtg_scorer import cli
from mtg_scorer.publish.artifact import verify_artifact

SEED = Path(__file__).resolve().parents[1] / "seeds/scryfall-layouts-v1"
FIXTURE = Path(__file__).parent / "fixtures" / "scryfall" / "default-cards.json"
DSN = "dbname=catalog_cli_test"


def run(monkeypatch, *arguments):
    monkeypatch.setattr(sys, "argv", ["mtg-scorer", *map(str, arguments)])
    cli.main()


def test_a_command_is_required(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exited:
        run(monkeypatch)

    assert exited.value.code == 2
    assert "required" in capsys.readouterr().err


def test_help_lists_every_batch_command(monkeypatch, capsys):
    with pytest.raises(SystemExit) as exited:
        run(monkeypatch, "--help")

    assert exited.value.code == 0
    usage = capsys.readouterr().out
    for command in (
        "ingest-scryfall",
        "export-catalog",
        "publish-catalog",
        "rollback-catalog",
        "score-topdeck",
        "publish-scores",
        "rollback-scores",
    ):
        assert command in usage


def test_ingest_scryfall_reports_the_retained_snapshot_and_parquet(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(
        scryfall,
        "_fetch_json",
        lambda _: {
            "updated_at": "2026-09-08T00:00:00Z",
            "download_uri": "https://example.invalid/bulk",
        },
    )
    monkeypatch.setattr(scryfall, "urlopen", lambda *a, **k: io.BytesIO(FIXTURE.read_bytes()))

    run(monkeypatch, "ingest-scryfall", "--data-dir", tmp_path)

    report = dict(line.split(": ", 1) for line in capsys.readouterr().out.splitlines())
    assert report["snapshot"].startswith("scryfall-default-cards-20260908T000000Z-")
    assert (report["oracle cards"], report["printings"]) == ("2", "3")
    assert (tmp_path / "raw" / "scryfall" / "20260908T000000Z" / "manifest.json").exists()
    for key in ("oracle parquet", "printing parquet"):
        parquet = Path(report[key])
        assert parquet.exists()
        assert tmp_path / "silver" / "scryfall" / report["snapshot"] in parquet.parents


def test_export_catalog_prints_a_verifiable_and_reusable_artifact(monkeypatch, capsys, tmp_path):
    created_at = "2026-09-08T01:00:00Z"
    run(
        monkeypatch,
        "export-catalog",
        "--source-dir",
        SEED,
        "--output-root",
        tmp_path,
        "--created-at",
        created_at,
    )
    directory = Path(capsys.readouterr().out.strip())

    payload, _ = verify_artifact(directory, SEED)
    assert directory.parent == tmp_path
    assert payload["created_at"] == created_at

    run(monkeypatch, "export-catalog", "--source-dir", SEED, "--output-root", tmp_path)
    assert Path(capsys.readouterr().out.strip()) == directory


def test_publish_catalog_uses_the_environment_dsn_and_prints_json(monkeypatch, capsys, tmp_path):
    calls = []

    def publish(artifact, source_dir, dsn):
        calls.append((artifact, source_dir, dsn))
        return {"catalog_snapshot_id": "catalog-1", "state": "published"}

    monkeypatch.setattr(postgres, "publish_catalog", publish)
    monkeypatch.setenv("CATALOG_PUBLISH_DSN", DSN)

    run(monkeypatch, "publish-catalog", "--source-dir", SEED, "--artifact", tmp_path)

    assert calls == [(tmp_path, SEED, DSN)]
    assert json.loads(capsys.readouterr().out) == {
        "catalog_snapshot_id": "catalog-1",
        "state": "published",
    }


def test_publish_catalog_without_a_dsn_fails_before_publishing(monkeypatch, tmp_path):
    monkeypatch.delenv("CATALOG_PUBLISH_DSN", raising=False)
    monkeypatch.setattr(postgres, "publish_catalog", lambda *a: pytest.fail("published"))

    with pytest.raises(KeyError, match="CATALOG_PUBLISH_DSN"):
        run(monkeypatch, "publish-catalog", "--source-dir", SEED, "--artifact", tmp_path)


def test_rollback_catalog_passes_the_expected_active_snapshot(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(postgres, "rollback_catalog", lambda *args: calls.append(args))
    monkeypatch.setenv("CATALOG_PUBLISH_DSN", DSN)

    run(monkeypatch, "rollback-catalog", "--target", "catalog-old", "--expected", "catalog-new")

    assert calls == [(DSN, "catalog-old", "catalog-new")]
    assert "rolled back" in capsys.readouterr().out


def test_publish_scores_uses_the_score_dsn_and_prints_json(monkeypatch, capsys, tmp_path):
    calls = []

    def publish(run_file, dsn):
        calls.append((run_file, dsn))
        return {"score_run_id": "scores-1", "state": "published"}

    monkeypatch.setattr(score_postgres, "publish_score_run", publish)
    monkeypatch.setenv("SCORE_PUBLISH_DSN", DSN)

    run(monkeypatch, "publish-scores", "--run-file", tmp_path / "run.json")

    assert calls == [(tmp_path / "run.json", DSN)]
    assert json.loads(capsys.readouterr().out) == {"score_run_id": "scores-1", "state": "published"}


def test_publish_scores_without_a_dsn_fails_before_publishing(monkeypatch, tmp_path):
    monkeypatch.delenv("SCORE_PUBLISH_DSN", raising=False)
    monkeypatch.setattr(score_postgres, "publish_score_run", lambda *a: pytest.fail("published"))

    with pytest.raises(KeyError, match="SCORE_PUBLISH_DSN"):
        run(monkeypatch, "publish-scores", "--run-file", tmp_path / "run.json")


def test_rollback_scores_passes_the_expected_active_run(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(score_postgres, "rollback_score_run", lambda *args: calls.append(args))
    monkeypatch.setenv("SCORE_PUBLISH_DSN", DSN)

    run(monkeypatch, "rollback-scores", "--target", "scores-old", "--expected", "scores-new")

    assert calls == [(DSN, "scores-old", "scores-new")]
    assert "rolled back" in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param(("rollback-scores", "--target", "scores-old"), id="unguarded-score-rollback"),
        pytest.param(("publish-scores",), id="publish-scores-without-file"),
        pytest.param(("rollback-catalog", "--target", "catalog-old"), id="unguarded-rollback"),
        pytest.param(("publish-catalog", "--artifact", "artifact"), id="publish-without-source"),
        pytest.param(("export-catalog", "--source-dir", "seed"), id="export-without-output"),
    ],
)
def test_required_options_are_enforced_before_any_operation(monkeypatch, capsys, arguments):
    monkeypatch.setattr(postgres, "rollback_catalog", lambda *a: pytest.fail("rolled back"))
    monkeypatch.setattr(postgres, "publish_catalog", lambda *a: pytest.fail("published"))

    with pytest.raises(SystemExit) as exited:
        run(monkeypatch, *arguments)

    assert exited.value.code == 2
    assert "required" in capsys.readouterr().err
