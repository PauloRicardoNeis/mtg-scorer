"""Saved Wizards coverage pages become verified, source-independent facts (SYNTHETIC data).

The fixtures under ``fixtures/wizards`` are hand-written copies of the two page
templates: the original 2005 table layout and the div.deck layout of 2009 captures.
"""

import json
from collections import Counter

import pytest
from synthetic_wizards import CATALOG, EVENT, FIXTURES, oracle, resolver, save

from mtg_scorer.domain import CoverageScope
from mtg_scorer.ingest import wizards
from mtg_scorer.ingest.wizards import (
    ATTRIBUTION,
    PARSER_VERSION,
    SOURCE,
    NameResolution,
    card_name,
    catalog_resolver,
    deck_pages,
    decode_page,
    join_names,
    match_names,
    name_tokens,
    parse_decks,
    parse_results,
    parse_standings,
    read_saved_pages,
    records,
    result_round,
)


def read(tmp_path, **options):
    return read_saved_pages(save(tmp_path, **options), resolver)


def standing_of(snapshot, deck_number, event="ptsyn05"):
    return {s.source_deck_id: s for s in snapshot.standings}.get(f"{event}#{deck_number}")


# --- Page parsers ------------------------------------------------------------------------


def test_the_table_template_reads_each_zone_and_the_deck_name() -> None:
    decks = parse_decks((FIXTURES / "table" / "page-afdecks.html").read_text(encoding="utf-8"))

    assert [deck["player"] for deck in decks] == ["Ana Alpha", "Ben Bravo", "Carla Charlie"]
    assert [deck["label"] for deck in decks] == ["Psychatog", None, "Boros"]
    ana = decks[0]
    # Split cards, typos and the column totals are read as the printed cards.
    assert ana["main"] == Counter(
        {
            "Island": 22,
            "Psychatog": 4,
            "Fire // Ice": 4,
            "Stitch Together": 4,
            "Lim-Dul's Vault": 2,
            "Counterspell": 24,
        }
    )
    assert ana["side"] == Counter({"Pyrostatik Pillar": 3, "Naturalize": 12})
    # A zero-copy line is no card, and an empty sideboard column stays empty.
    assert decks[2]["main"] == Counter({"Mountain": 24, "Lightning Helix": 36})
    assert decks[2]["side"] == Counter()


def test_the_div_template_reads_each_zone_and_the_deck_name() -> None:
    decks = parse_decks((FIXTURES / "div" / "page-decksaz.html").read_text(encoding="utf-8"))

    assert [deck["player"] for deck in decks] == [
        "Ana Alpha",
        "Ben Bravo",
        "Zed Zulu",
        "Yan Yankee",
        "Wes Whiskey",
    ]
    # Yan's and Wes's captions name the event, not a deck.
    assert [deck["label"] for deck in decks] == ["Zoo", "Faeries", None, None, None]
    # The 2010 pages start the sideboard inside the second main deck column.
    assert decks[4]["main"] == Counter({"Island": 24, "Counterspell": 36})
    assert decks[4]["side"] == Counter({"Naturalize": 15})
    assert decks[0]["main"] == Counter(
        {"Mountain": 20, "Tarmogoyf": 4, "Wear // Tear": 4, "Aether Vial": 32}
    )
    assert decks[0]["side"] == Counter({"Naturalize": 15})


def test_a_deck_name_in_the_player_header_becomes_the_label() -> None:
    page = (
        '<p><b><font size="+1">Shingo Alpha - A Lifetime of Grand Vacations</font></b>'
        '<br></p><td valign="top">60&nbsp;<a>Island</a><br></td>'
        '<p><b><font size="+1">Al-Bravo Ben</font></b><br>Zoo</p>'
        '<td valign="top">60&nbsp;<a>Mountain</a><br></td>'
        '<p><b><font size="+1">Cid Charlie &ndash;Madness &lsquo;Tog</font></b><br></p>'
        '<td valign="top">60&nbsp;<a>Island</a><br></td>'
        # A heading without cards is no deck.
        '<p><b><font size="+1">Top 8 Decklists</font></b><br></p>'
    )

    decks = parse_decks(page)

    assert [(d["player"], d["label"]) for d in decks] == [
        ("Shingo Alpha", "A Lifetime of Grand Vacations"),
        ("Al-Bravo Ben", "Zoo"),
        ("Cid Charlie", "Madness ‘Tog"),
    ]


def test_a_page_without_decks_has_none() -> None:
    assert parse_decks("<html><body><p>Coverage</p></body></html>") == []


def test_results_rows_become_matches_byes_and_unread_rows() -> None:
    matches, byes, unread = parse_results(
        (FIXTURES / "table" / "page-res3.html").read_text(encoding="utf-8")
    )

    assert matches[:2] == [
        ("Alpha, Ana [USA]", "drew", "Charlie, Carla [JPN]"),
        ("Bravo, Ben [FRA]", "won", "Delta, Dan [DEU]"),
    ]
    assert byes == ["Hotel, Hana [ITA]"]
    assert unread == 1


def test_a_bye_written_as_a_won_match_is_a_bye_but_a_byers_is_a_player() -> None:
    page = (
        "<tr><td>1</td><td>Kilo, Kim</td><td>Won 2-0</td><td>vs.</td><td>* BYE *</td></tr>"
        "<tr><td>2</td><td>Lima, Lou</td><td>Won 2-0</td><td>vs.</td><td>Byers, Bo</td></tr>"
    )

    matches, byes, _ = parse_results(page)

    assert byes == ["Kilo, Kim"]
    assert matches == [("Lima, Lou", "won", "Byers, Bo")]


def test_standings_rows_need_a_rank_and_a_country() -> None:
    page = (FIXTURES / "table" / "page-standfin.html").read_text(encoding="utf-8")

    standings = parse_standings(page)

    assert standings[0] == (1, "Alpha, Ana [USA]")
    assert len(standings) == 9


def test_a_match_listed_from_both_seats_counts_once() -> None:
    record = records(
        {
            1: [("Kilo, Kim", "won", "Lima, Lou"), ("Lima, Lou", "lost", "Kilo, Kim")],
            2: [("Lima, Lou", "drew", "Kilo, Kim")],
        }
    )

    assert record["Kilo, Kim"] == Counter({"won": 1, "drew": 1})
    assert record["Lima, Lou"] == Counter({"lost": 1, "drew": 1})


@pytest.mark.parametrize(
    ("slugs", "expected"),
    [
        # Alphabetical ranges are the field, then the top 8; "tedecks" is no range (t > e)
        # but the best Extended records, read after the ranges.
        (
            ["afdecks", "gzdecks", "t8decks", "tedecks", "decktech1"],
            ["afdecks", "gzdecks", "tedecks", "t8decks"],
        ),
        # Side events stay out.
        (["decksae", "decksfk", "extendeddecks"], ["decksae", "decksfk"]),
        (["alldecksad", "alldeckstz", "topdecks"], ["alldecksad", "alldeckstz"]),
        # Without ranges, every decklist page but techs and samples.
        (
            ["blockdecklists", "t8decklists", "decktech2", "samplehand"],
            ["blockdecklists", "t8decklists"],
        ),
        # Booster draft top 8s and translated copies are not constructed decks.
        (
            ["decksae", "top8bcd", "top8bdd", "top8decks", "top8profiles", "t8decks,,fr"],
            ["decksae", "top8bcd", "top8decks"],
        ),
        (["t8decks", "welcome"], ["t8decks"]),
        # 2009–10 events listed the best constructed records apart from the field.
        (
            ["decksae", "tedecks", "top8decks", "f-topblock", "topstddecks", "legacydecks"],
            ["decksae", "f-topblock", "tedecks", "topstddecks", "top8decks"],
        ),
        (["welcome", "res1"], []),
    ],
)
def test_the_field_is_read_from_its_decklist_pages(slugs, expected) -> None:
    assert deck_pages(slugs) == expected


def test_results_pages_name_their_round() -> None:
    assert [result_round(slug) for slug in ("res1", "res16", "res3a", "results", "pair3")] == [
        1,
        16,
        3,
        None,
        None,
    ]


def test_card_names_are_corrected_to_the_printed_name() -> None:
    assert card_name("Fire/Ice") == "Fire // Ice"
    assert card_name("Fire // Ice") == "Fire // Ice"
    assert card_name("Æther Vial") == "Aether Vial"
    assert card_name("Caves of Kolios") == "Caves of Koilos"
    assert card_name("Frostlang") == "Frostling"
    assert card_name("Pyrostatik Pillar") == "Pyrostatik Pillar"


def test_pages_are_utf8_unless_they_cannot_be() -> None:
    assert decode_page("Jötun Grunt".encode()) == "Jötun Grunt"
    assert decode_page("Jötun Grunt".encode("cp1252")) == "Jötun Grunt"


# --- Player names ------------------------------------------------------------------------


def test_names_compare_without_order_accents_punctuation_or_suffix() -> None:
    assert name_tokens("Zampere Junior, Celso [BRA]") == ["celso", "zampere"]
    assert name_tokens("Celso Zampere, Jr.") == ["celso", "zampere"]
    assert name_tokens("Müller, André [DEU]") == ["andre", "muller"]


def test_decks_join_the_standings_in_passes_that_keep_unique_matches() -> None:
    players = [
        "Alpha, Ana [USA]",
        "Bravo Long, Benjamin [FRA]",
        "Charlie, Carla [JPN]",
        "Charlie, Chris [JPN]",
        "Delta, D [DEU]",
        "Oodan, Takeshi [JPN]",
        "Stark, William [USA]",
        "Perez Bermudez, Alejan [MEX]",
        "Perez Paez, Oscar [ESP]",
    ]
    decks = [
        "Ana Alpha",
        "Benjamin Bravo Longname",
        "Chris Charlie",
        "Dan Delta",
        "Takeshi Odan",
        "Bill Stark",
        "Alejandro Perez",
        "Oscar Perez",
        "Nobody Known",
    ]

    joined, how = join_names(decks, players)

    assert joined == {
        "Ana Alpha": "Alpha, Ana [USA]",
        "Benjamin Bravo Longname": "Bravo Long, Benjamin [FRA]",
        "Chris Charlie": "Charlie, Chris [JPN]",
        "Dan Delta": "Delta, D [DEU]",
        "Takeshi Odan": "Oodan, Takeshi [JPN]",
        "Bill Stark": "Stark, William [USA]",
        "Alejandro Perez": "Perez Bermudez, Alejan [MEX]",
        "Oscar Perez": "Perez Paez, Oscar [ESP]",
    }
    assert how == Counter({"exact": 2, "truncated": 2, "similar": 4, "unmatched": 1})


def test_a_first_name_may_be_a_nickname_or_any_given_name() -> None:
    joined, how = join_names(
        ["Billy Moreno", "Tom Lapille", "Bryant Malig"],
        [
            "Moreno, William [USA]",
            "LaPille, Thomas [USA]",
            "Malig, J. Bryant [USA]",
            "Moreno, Ana [USA]",
        ],
    )

    assert joined == {
        "Billy Moreno": "Moreno, William [USA]",
        "Tom Lapille": "LaPille, Thomas [USA]",
        "Bryant Malig": "Malig, J. Bryant [USA]",
    }
    # "Tom Lapille" already joins on surname and initial.
    assert how == Counter({"surname_initial": 1, "similar": 2})


def test_a_similar_name_is_not_taken_when_two_players_fit_equally() -> None:
    joined, how = join_names(["Kim Kilo"], ["Kilos, Kim [USA]", "Kilox, Kim [USA]"])

    assert joined == {}
    assert how == Counter({"unmatched": 1})


def test_a_same_surname_with_another_first_name_needs_no_other_candidate() -> None:
    alone, _ = join_names(["Ernesto Padilla"], ["Padilla Chinas, Jorge [MEX]"])
    crowded, _ = join_names(["Ernesto Padilla", "Jorge Padila"], ["Padilla Chinas, Jorge [MEX]"])

    assert alone == {"Ernesto Padilla": "Padilla Chinas, Jorge [MEX]"}
    assert crowded == {"Jorge Padila": "Padilla Chinas, Jorge [MEX]"}


def test_a_player_joins_one_deck_at_most() -> None:
    # Both decks match the player by truncated name; the first keeps it.
    joined, how = join_names(["Ana Alpha Smith", "Ana Alpha Jones"], ["Alpha, Ana [USA]"])

    assert joined == {"Ana Alpha Smith": "Alpha, Ana [USA]"}
    assert how == Counter({"truncated": 1, "unmatched": 1})


# --- Card names ---------------------------------------------------------------------------


def test_names_resolve_canonical_first_then_face_then_without_accents() -> None:
    matches = match_names(
        ["Fire // Ice", "Fire", "Lim-Dul's Vault", "Pyrostatik Pillar", "ISLAND"], CATALOG
    )

    assert matches["Fire // Ice"] == ((oracle(4), "Fire // Ice"),)
    # Two split cards have a "Fire" half: the name is ambiguous.
    assert len(matches["Fire"]) == 2
    assert matches["Lim-Dul's Vault"] == ((oracle(7), "Lim-Dûl's Vault"),)
    assert matches["Pyrostatik Pillar"] == ()
    assert matches["ISLAND"] == ((oracle(1), "Island"),)


class FakeConnection:
    def __init__(self, dsn):
        self.dsn = dsn
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, parameters=None):
        self.queries.append((query, parameters))
        return self

    def fetchone(self):
        return ("catalog-local",)

    def fetchall(self):
        return CATALOG


def test_the_catalog_resolver_reads_the_active_snapshot(monkeypatch) -> None:
    import psycopg

    opened = []
    monkeypatch.setattr(
        psycopg, "connect", lambda dsn: opened.append(FakeConnection(dsn)) or opened[-1]
    )

    resolution = catalog_resolver("dbname=catalog")(["Psychatog", "Fire"])

    assert resolution.catalog_snapshot_id == "catalog-local"
    assert resolution.matches["Psychatog"] == ((oracle(3), "Psychatog"),)
    assert opened[0].dsn == "dbname=catalog"
    query, parameters = opened[0].queries[1]
    assert parameters[0] == "catalog-local"
    assert "token" in parameters[1]


# --- Saved directories ---------------------------------------------------------------


def test_a_saved_event_becomes_one_tournament_with_its_coverage(tmp_path) -> None:
    snapshot = read(tmp_path)

    (event,) = snapshot.tournaments
    assert (event.source_event_id, event.format_name, event.occurred_on.isoformat()) == (
        "ptsyn05",
        "Extended",
        "2005-10-28",
    )
    assert (event.player_count, event.top_cut_size) == (9, 8)
    assert event.provenance.source == SOURCE
    assert event.provenance.parser_version == PARSER_VERSION
    assert event.provenance.raw_snapshot_ref == "saved/page-standfin.html"
    coverage = event.coverage
    assert (coverage.decklists.scope, coverage.decklists.observed_count) == (
        CoverageScope.PARTIAL,
        7,
    )
    assert coverage.standings.scope is CoverageScope.FULL_FIELD
    assert (coverage.matches.scope, coverage.matches.observed_count) == (
        CoverageScope.FULL_FIELD,
        3,
    )
    assert snapshot.top_cut_basis == {"ptsyn05": "standing_order"}
    assert snapshot.dataset_snapshot_id.startswith("wizards-")


def test_the_top_8_page_adds_only_the_decks_the_field_pages_lack(tmp_path) -> None:
    snapshot = read(tmp_path)

    assert [deck.source_deck_id for deck in snapshot.decks] == [
        f"ptsyn05#{number}" for number in range(1, 8)
    ]
    # Ana's field deck is kept; Hana's deck comes from the top 8 page alone.
    assert [deck.archetype_label for deck in snapshot.decks] == [
        "Psychatog",
        None,
        "Boros",
        "Affinity",
        "Psychatog",
        "Boros",
        "Burning Zoo",
    ]
    assert len(snapshot.decks[0].cards) > 1


def test_cards_resolve_to_the_catalog_and_unresolved_lines_are_kept_apart(tmp_path) -> None:
    snapshot = read(tmp_path)

    ana = snapshot.decks[0]
    cards = {card.name: (card.mainboard_count, card.sideboard_count) for card in ana.cards}
    assert cards["Fire // Ice"] == (4, 0)
    assert cards["Stitch Together"] == (4, 0)
    assert cards["Lim-Dûl's Vault"] == (2, 0)
    assert "Pyrostatik Pillar" not in cards
    # Ana's unresolved line is in the sideboard, Ben's in the main deck.
    assert not ana.sideboard_observed
    assert snapshot.incomplete_mainboards == frozenset({"ptsyn05#2"})
    assert snapshot.quarantined_card_lines == 2
    assert snapshot.unresolved_names == ("Pyrostatik Pillar",)
    assert snapshot.decks[3].sideboard_observed
    # Carla listed no sideboard, which is not the same as an empty one.
    assert not snapshot.decks[2].sideboard_observed


def test_joined_decks_get_their_rank_record_byes_and_top_cut(tmp_path) -> None:
    snapshot = read(tmp_path)

    ana, takeshi, gus = (standing_of(snapshot, n) for n in (1, 4, 5))
    assert (ana.final_rank, ana.wins, ana.losses, ana.draws, ana.byes) == (1, 2, 0, 1, 0)
    assert ana.made_top_cut is True
    assert (takeshi.final_rank, takeshi.wins, takeshi.losses, takeshi.byes) == (4, 0, 2, 1)
    assert (gus.final_rank, gus.wins, gus.losses, gus.draws) == (7, 1, 2, 0)
    # Zed Zulu is not in the standings, so the deck has no standing.
    assert standing_of(snapshot, 6) is None
    assert snapshot.join_methods == {"exact": 5, "similar": 1, "unmatched": 1}
    hana = standing_of(snapshot, 7)
    assert (hana.final_rank, hana.made_top_cut, hana.wins, hana.losses, hana.byes) == (
        8,
        True,
        0,
        2,
        1,
    )


def test_a_results_spelling_is_read_as_the_standings_player_unless_rounds_clash() -> None:
    def results(*rows):
        return ([(a, "won", b) for a, b in rows], [], 0)

    spelling = wizards._standings_spellings(
        {
            1: results(("Golf, Gus [USA]", "Kilo, Kim [USA]")),
            2: results(("Golf, Gus [ESP]", "Kilo, Kim [DEU]")),
            3: results(("Kilo, Kim [USA]", "Lima, Lou [USA]")),
        },
        ["Golf, Gus [ESP]", "Kilo, Kim [DEU]"],
    )

    # Gus played round 1 under the default country and round 2 under his own; Kim's
    # default spelling played rounds 1 and 3, never alongside round 2.
    assert spelling("Golf, Gus [USA]") == "Golf, Gus [ESP]"
    assert spelling("Kilo, Kim [USA]") == "Kilo, Kim [DEU]"
    # Lou is no standings player.
    assert spelling("Lima, Lou [USA]") == "Lima, Lou [USA]"


def test_two_names_that_played_the_same_round_are_two_players() -> None:
    spelling = wizards._standings_spellings(
        {1: ([("Golf, Gus [USA]", "won", "Golf, Gus [ESP]")], [], 0)},
        ["Golf, Gus [ESP]"],
    )

    assert spelling("Golf, Gus [USA]") == "Golf, Gus [USA]"


def test_only_the_rounds_played_in_the_format_count(tmp_path) -> None:
    snapshot = read(tmp_path, event={**EVENT, "constructed_rounds": [1, 3]})

    ana = standing_of(snapshot, 1)
    assert (ana.wins, ana.losses, ana.draws) == (1, 0, 1)
    assert snapshot.tournaments[0].coverage.matches.observed_count == 2


def test_a_missing_round_leaves_every_record_unknown(tmp_path) -> None:
    snapshot = read(tmp_path, event={**EVENT, "constructed_rounds": [1, 2, 3, 4]})

    ana = standing_of(snapshot, 1)
    assert (ana.wins, ana.losses, ana.draws, ana.byes) == (None, None, None, None)
    assert ana.final_rank == 1
    matches = snapshot.tournaments[0].coverage.matches
    assert (matches.scope, matches.observed_count, matches.expected_count) == (
        CoverageScope.PARTIAL,
        3,
        4,
    )


def test_without_final_standings_the_results_name_the_players(tmp_path) -> None:
    snapshot = read(tmp_path, pages=("afdecks", "gzdecks", "res1", "res2", "res3"))

    (event,) = snapshot.tournaments
    # With no standings to name him, Gus's round 1 spelling counts as one more player.
    assert event.player_count == 10
    assert event.top_cut_size is None
    assert event.coverage.standings.scope is CoverageScope.NONE
    assert event.provenance.raw_snapshot_ref == "saved/page-afdecks.html"
    assert snapshot.top_cut_basis == {"ptsyn05": "unknown_top_cut"}
    ana = standing_of(snapshot, 1)
    assert (ana.final_rank, ana.made_top_cut, ana.wins) == (None, None, 2)


def test_without_results_or_standings_nothing_is_known_about_the_field(tmp_path) -> None:
    snapshot = read(tmp_path, pages=("afdecks",))

    (event,) = snapshot.tournaments
    assert event.player_count is None
    assert event.coverage.decklists.scope is CoverageScope.UNKNOWN
    assert event.coverage.matches.scope is CoverageScope.NONE
    assert snapshot.standings == ()


def test_an_older_probe_names_the_event_in_its_summary(tmp_path) -> None:
    directory = save(tmp_path, event=None, retrieved_at=False)
    (directory / "summary.json").write_text(json.dumps({"event": EVENT}), encoding="utf-8")

    snapshot = read_saved_pages(directory, resolver)

    assert snapshot.tournaments[0].source_event_id == "ptsyn05"
    assert snapshot.raw_files[0].retrieved_at_basis == "file_mtime"


def test_the_snapshot_identity_follows_files_event_and_catalog(tmp_path) -> None:
    for name in ("a", "b", "c"):
        (tmp_path / name).mkdir()
    first = read(tmp_path / "a")
    again = read(tmp_path / "b")
    other_event = read(tmp_path / "c", event={**EVENT, "format": "Standard"})
    other_catalog = read_saved_pages(
        tmp_path / "a" / "saved",
        lambda names: NameResolution("catalog-other", match_names(names, CATALOG)),
    )

    assert first.dataset_snapshot_id == again.dataset_snapshot_id
    assert other_event.dataset_snapshot_id != first.dataset_snapshot_id
    assert other_catalog.dataset_snapshot_id != first.dataset_snapshot_id


def test_a_changed_page_is_rejected(tmp_path) -> None:
    directory = save(tmp_path)
    (directory / "page-res1.html").write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="page-res1.html does not match"):
        read_saved_pages(directory, resolver)


def test_a_directory_without_pages_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="no saved coverage pages"):
        read(tmp_path, pages=())


def test_the_attribution_names_the_publisher_and_the_archive() -> None:
    assert "Wizards of the Coast" in ATTRIBUTION
    assert "web.archive.org" in ATTRIBUTION
    assert wizards.TOP_CUT == 8
