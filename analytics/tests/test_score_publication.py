"""Real PostgreSQL proof for score runs; TEST_DATABASE_DSN must name a disposable database.

Every run below is SYNTHETIC. Each test makes its own run identities, and only asserts
on its own runs, so the suite can share one database with other publication tests.
"""

import json
import os
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Jsonb
from synthetic_topdeck import (
    BOLT,
    COUNTERSPELL,
    ISLAND,
    deck,
    event,
    open_event,
    row,
    save,
    weekly_event,
)

from mtg_scorer import MaxRatioMethod
from mtg_scorer.ingest.topdeck import read_saved_responses
from mtg_scorer.publish.overall_run import score_overall
from mtg_scorer.publish.score_postgres import (
    publish_score_run,
    rollback_score_run,
    score_run_header,
)
from mtg_scorer.publish.score_run import build_score_run, write_score_run
from mtg_scorer.tournament_features import CohortRules

DSN = os.environ.get("TEST_DATABASE_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="real PostgreSQL TEST_DATABASE_DSN required")


def role_dsn(role):
    return psycopg.conninfo.make_conninfo(DSN, options=f"-c role={role}")


@pytest.fixture
def make_run(tmp_path):
    """Write a fresh SYNTHETIC run file; a unique cohort version gives a unique identity."""

    def make(fmt="Modern", methods=None):
        events = [open_event(), weekly_event()]
        if fmt != "Modern":
            listed = deck({"Bolt": (BOLT, 4), "Counterspell": (COUNTERSPELL, 4)})
            events = [event("synthetic-other-format", [row(1, deck_obj=listed)], fmt=fmt)]
        directory = save(tmp_path / uuid4().hex, {"search.json": events})
        rules = CohortRules(
            version=f"synthetic-publication-{uuid4()}",
            format_name=fmt,
            starts_on="2026-03-01",
            ends_before="2026-09-01",
        )
        arguments = {} if methods is None else {"methods": methods}
        document = build_score_run(read_saved_responses(directory), rules, **arguments)
        return write_score_run(document, tmp_path / "runs")

    return make


def publish(run_file, **kwargs):
    return publish_score_run(run_file, role_dsn("score_publisher"), **kwargs)


def active(connection, fmt="Modern"):
    found = connection.execute(
        "SELECT score_run_id FROM scores.active_score_run "
        "WHERE source='topdeck' AND format_name=%s",
        (fmt,),
    ).fetchone()
    return found[0] if found else None


def attempts(connection, run_id):
    return connection.execute(
        "SELECT state, error_code FROM scores.score_publication_attempt "
        "WHERE score_run_id=%s ORDER BY started_at",
        (run_id,),
    ).fetchall()


def test_publication_is_readable_replayable_and_read_only_for_the_api(make_run) -> None:
    run_file = make_run()
    result = publish(run_file)
    run_id = result["score_run_id"]

    assert result["state"] == "published"
    assert publish(run_file)["state"] == "already_published"
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        assert active(reader) == run_id
        ranked = reader.execute(
            "SELECT c.name, s.value FROM scores.published_card_score s "
            "JOIN scores.published_score_run_card c USING (score_run_id, oracle_id) "
            "WHERE s.score_run_id=%s AND s.method_id='max-ratio' AND s.output='max_ratio' "
            "ORDER BY s.value DESC, c.name",
            (run_id,),
        ).fetchall()
        assert ranked == [("Bolt", 100.0), ("Counterspell", 100.0)]
        inputs = reader.execute(
            "SELECT input_name, value FROM scores.published_card_score_input "
            "WHERE score_run_id=%s AND method_id='max-ratio' AND oracle_id=%s ORDER BY input_name",
            (run_id, BOLT),
        ).fetchall()
        assert inputs == [("count", 3.0), ("max_count", 3.0)]
        for statement in (
            "SELECT * FROM scores.score_run_card",
            "DELETE FROM scores.active_score_run",
            "SELECT scores.rollback_score_run(NULL,NULL)",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                reader.execute(statement)


def test_archetypes_are_published_with_their_record_and_performance(make_run) -> None:
    run_id = publish(make_run())["score_run_id"]
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        control = reader.execute(
            "SELECT commanders, event_count, top_cut_count, top_cut_known_decks, record_wins,"
            " record_losses, win_rate, top_cut_lift, cardinality(series_decks)"
            " FROM scores.published_score_run_archetype WHERE score_run_id=%s AND label='Control'",
            (run_id,),
        ).fetchone()

    assert control == ([], 2, 1, 2, 3, 4, 0.4286, 0.75, 12)


def test_decks_are_published_with_their_event_and_each_card_lists_its_own(make_run) -> None:
    run_id = publish(make_run())["score_run_id"]
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        decks = reader.execute(
            "SELECT position, source_deck_id, event_name, event_url, occurred_on::text, players,"
            " archetype_label, final_rank, made_top_cut, record_wins, record_losses, record_draws"
            " FROM scores.published_score_run_deck WHERE score_run_id=%s ORDER BY position",
            (run_id,),
        ).fetchall()
        bolt = reader.execute(
            "SELECT deck_positions, deck_copies FROM scores.published_score_run_card"
            " WHERE score_run_id=%s AND oracle_id=%s",
            (run_id, BOLT),
        ).fetchone()

    assert [deck[1] for deck in decks] == [
        "synthetic-weekly#1",
        "synthetic-weekly#2",
        "synthetic-open#1",
        "synthetic-open#2",
        "synthetic-open#3",
    ]
    assert decks[2] == (
        2,
        "synthetic-open#1",
        "Synthetic synthetic-open",
        "https://topdeck.gg/bracket/synthetic-open",
        "2026-03-10",
        4,
        "Burn",
        None,
        True,
        3,
        0,
        0,
    )
    assert bolt == ([0, 2, 3], [4, 4, 2])


def test_each_deck_is_published_with_its_whole_list(make_run) -> None:
    run_id = publish(make_run())["score_run_id"]
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        lists = reader.execute(
            "SELECT position, mainboard, mainboard_copies, commanders, sideboard,"
            " sideboard_names, sideboard_copies FROM scores.published_score_run_deck"
            " WHERE score_run_id=%s ORDER BY position",
            (run_id,),
        ).fetchall()

    # The open's Burn deck: four Bolts and ten Islands, an empty sideboard and no commander.
    _, main, copies, commanders, sideboard, names, side_copies = lists[2]
    assert dict(zip(map(str, main), copies, strict=True)) == {BOLT: 4, ISLAND: 10}
    assert (commanders, sideboard, names, side_copies) == ([], [], [], [])
    # The open's last deck reported no sideboard at all, which stays unknown.
    assert lists[4][4:] == (None, None, None)
    assert sum(len(row[1]) for row in lists) == 8


def test_unscored_cards_and_unknown_top_cuts_are_stored_as_unknown(make_run) -> None:
    run_id = publish(make_run())["score_run_id"]
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        island = reader.execute(
            "SELECT scored, top_cut_count, top_cut_known_decks "
            "FROM scores.published_score_run_card WHERE score_run_id=%s AND name='Island'",
            (run_id,),
        ).fetchone()
        scored_for_island = reader.execute(
            "SELECT count(*) FROM scores.published_card_score s "
            "JOIN scores.published_score_run_card c USING (score_run_id, oracle_id) "
            "WHERE s.score_run_id=%s AND c.name='Island'",
            (run_id,),
        ).fetchone()[0]

    assert island == (False, 1, 1)
    assert scored_for_island == 0


def test_published_rows_cannot_be_changed(make_run) -> None:
    run_id = publish(make_run())["score_run_id"]
    with (
        psycopg.connect(role_dsn("score_publisher"), autocommit=True) as writer,
        pytest.raises(psycopg.Error, match="score_run_immutable"),
    ):
        writer.execute("DELETE FROM scores.card_score WHERE score_run_id=%s", (run_id,))


def test_same_identity_with_different_results_is_a_conflict(make_run) -> None:
    run_file = make_run()
    run_id = publish(run_file)["score_run_id"]
    header = score_run_header(json.loads(run_file.read_bytes()))
    header["results_sha256"] = "0" * 64
    with (
        psycopg.connect(role_dsn("score_publisher"), autocommit=True) as writer,
        pytest.raises(psycopg.Error, match="score_run_content_conflict"),
    ):
        writer.execute(
            "SELECT scores.begin_score_publication(%s,%s,%s)",
            (Jsonb(header), uuid4(), run_id),
        )


def test_a_failed_load_stays_invisible_and_a_retry_publishes(make_run) -> None:
    run_file = make_run()

    def explode(run_id):
        raise RuntimeError("synthetic failure before promotion")

    with psycopg.connect(DSN, autocommit=True) as admin:
        before = active(admin)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        publish(run_file, before_promote=explode)
    run_id = json.loads(run_file.read_bytes())["score_run_id"]
    with psycopg.connect(DSN, autocommit=True) as admin:
        assert attempts(admin, run_id) == [("failed", "publication_failed")]
        assert active(admin) == before
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        assert not reader.execute(
            "SELECT 1 FROM scores.published_score_run WHERE score_run_id=%s", (run_id,)
        ).fetchone()

    assert publish(run_file)["state"] == "published"
    with psycopg.connect(DSN, autocommit=True) as admin:
        assert [state for state, _ in attempts(admin, run_id)] == ["failed", "succeeded"]


@pytest.mark.parametrize(
    ("statement", "error"),
    [
        pytest.param(
            "DELETE FROM scores.card_score WHERE score_run_id=%s AND method_id='max-ratio'",
            "row_count_mismatch",
            id="missing-scores",
        ),
        pytest.param(
            "UPDATE scores.score_run_card SET scored=false WHERE score_run_id=%s AND name='Bolt'",
            "invalid_scores",
            id="score-for-unscored-card",
        ),
        pytest.param(
            "UPDATE scores.score_run_card SET deck_positions=NULL,deck_copies=NULL"
            " WHERE score_run_id=%s AND name='Bolt'",
            "invalid_decks",
            id="card-without-its-decks",
        ),
        pytest.param(
            "UPDATE scores.score_run_card SET deck_positions=ARRAY[0,2,9]"
            " WHERE score_run_id=%s AND name='Bolt'",
            "invalid_decks",
            id="deck-past-the-run",
        ),
        pytest.param(
            "DELETE FROM scores.score_run_deck WHERE score_run_id=%s AND position=4",
            "row_count_mismatch",
            id="missing-deck",
        ),
        pytest.param(
            "UPDATE scores.score_run_deck SET mainboard=NULL,mainboard_copies=NULL,commanders=NULL,"
            "sideboard=NULL,sideboard_names=NULL,sideboard_copies=NULL"
            " WHERE score_run_id=%s AND position=0",
            "invalid_decks",
            id="deck-without-its-list",
        ),
        pytest.param(
            "UPDATE scores.score_run_deck SET mainboard=mainboard[1:1],"
            "mainboard_copies=mainboard_copies[1:1] WHERE score_run_id=%s AND position=2",
            "invalid_decks",
            id="deck-list-missing-cards",
        ),
    ],
)
def test_promotion_rejects_rows_that_do_not_match_the_run(make_run, statement, error) -> None:
    run_file = make_run()
    run_id = json.loads(run_file.read_bytes())["score_run_id"]
    # The hook runs inside the publisher's loading transaction, where staged rows live.
    with (
        psycopg.connect(role_dsn("score_publisher"), autocommit=True) as writer,
        pytest.raises(psycopg.Error, match=error),
    ):
        publish_score_run(
            run_file,
            DSN,
            connection=writer,
            before_promote=lambda staged: writer.execute(statement, (staged,)),
        )
    with psycopg.connect(DSN, autocommit=True) as admin:
        assert attempts(admin, run_id) == [("failed", "publication_failed")]
        assert admin.execute(
            "SELECT state FROM scores.score_run WHERE score_run_id=%s", (run_id,)
        ).fetchone() == ("staging",)


def test_each_format_has_its_own_active_run(make_run) -> None:
    modern = publish(make_run())["score_run_id"]
    pioneer = publish(make_run(fmt="Pioneer"))["score_run_id"]
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        assert active(reader, "Modern") == modern
        assert active(reader, "Pioneer") == pioneer


def test_an_overall_run_is_published_beside_the_formats_it_combines(make_run) -> None:
    modern = make_run()
    pioneer = make_run(fmt="Pioneer")
    result = publish(score_overall([modern, pioneer], modern.parent.parent / "overall"))
    run_id = result["score_run_id"]

    assert result["state"] == "published"
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        assert active(reader, "Overall") == run_id
        components = reader.execute(
            "SELECT summary->'components' FROM scores.published_score_run WHERE score_run_id=%s",
            (run_id,),
        ).fetchone()[0]
        bolt = reader.execute(
            "SELECT deck_count, win_rate, series_decks, archetype_label "
            "FROM scores.published_score_run_card WHERE score_run_id=%s AND oracle_id=%s",
            (run_id, BOLT),
        ).fetchone()
        grades = reader.execute(
            "SELECT count(*) FROM scores.published_card_score "
            "WHERE score_run_id=%s AND method_id='overall-grade' AND output='score'",
            (run_id,),
        ).fetchone()[0]

    assert [c["format_name"] for c in components] == ["Modern", "Pioneer"]
    # Bolt is in three Modern decks and the one Pioneer deck; nothing format-bound pools.
    assert bolt == (4, None, None, None)
    assert grades == 2


def test_rollback_is_guarded_by_the_expected_active_run(make_run) -> None:
    first = publish(make_run(fmt="Legacy"))["score_run_id"]
    second = publish(make_run(fmt="Legacy", methods=(MaxRatioMethod(),)))["score_run_id"]
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        assert active(reader, "Legacy") == second

    with pytest.raises(psycopg.Error, match="stale_promotion"):
        rollback_score_run(role_dsn("score_publisher"), first, "scores-" + "0" * 64)
    with pytest.raises(psycopg.Error, match="score_run_not_published"):
        rollback_score_run(role_dsn("score_publisher"), "scores-" + "1" * 64, second)
    rollback_score_run(role_dsn("score_publisher"), first, second)
    with psycopg.connect(role_dsn("score_reader"), autocommit=True) as reader:
        assert active(reader, "Legacy") == first
