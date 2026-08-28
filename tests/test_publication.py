from datetime import UTC, datetime

import pytest

from mtg_scorer import build_catalog, build_demonstration_catalog

PUBLISHED_AT = datetime(2026, 8, 28, 18, 30, tzinfo=UTC)


def test_demonstration_catalog_exposes_one_versioned_product_contract() -> None:
    catalog = build_demonstration_catalog(published_at=PUBLISHED_AT)

    assert catalog["contractVersion"] == "card-catalog-v1"
    assert catalog["catalogKind"] == "DEMONSTRATION"
    assert catalog["snapshot"]["datasetSnapshotId"] == "demo-synthetic-v1"
    assert catalog["snapshot"]["publishedAt"] == "2026-08-28T18:30:00Z"
    assert len(catalog["snapshot"]["scoreConfigHash"]) == 64
    assert len(catalog["cards"]) == 3

    buildaround = next(card for card in catalog["cards"] if card["name"] == "Example Engine")
    assert buildaround["scores"]["buildaroundSignal"] > buildaround["scores"]["staple"]
    assert buildaround["reasons"]


def test_catalog_rejects_an_empty_publication() -> None:
    with pytest.raises(ValueError, match="at least one"):
        build_catalog((), catalog_kind="DEMONSTRATION", published_at=PUBLISHED_AT)


def test_catalog_rejects_a_naive_publication_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_catalog((), catalog_kind="DEMONSTRATION", published_at=datetime(2026, 8, 28))
