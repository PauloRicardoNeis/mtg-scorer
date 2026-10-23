"""Relationship and manifest rules that the closed row schemas cannot express."""

import copy
import json
from hashlib import sha256
from pathlib import Path

import pytest

from mtg_scorer.publish.artifact import canonical_bytes, export_catalog
from mtg_scorer.publish.validation import (
    validate_catalog,
    validate_manifest,
    validate_relationships,
)

SEED = Path(__file__).resolve().parents[1] / "seeds/scryfall-layouts-v1"
UNKNOWN_UUID = "00000000-0000-4000-8000-00000000000f"


@pytest.fixture(scope="module")
def exported(tmp_path_factory):
    directory = export_catalog(SEED, tmp_path_factory.mktemp("seed"))
    return (
        (directory / "catalog.json").read_bytes(),
        json.loads((directory / "manifest.json").read_bytes()),
    )


@pytest.fixture
def payload(exported):
    return json.loads(exported[0])


def card(payload, name):
    return next(row for row in payload["cards"] if row["name"] == name)


def printing_of(payload, name):
    oracle_id = card(payload, name)["oracle_id"]
    return next(row for row in payload["printings"] if row["oracle_id"] == oracle_id)


def drop(payload, table, **match):
    payload[table] = [
        row for row in payload[table] if any(row[key] != value for key, value in match.items())
    ]


def duplicate_first(table):
    return lambda payload: payload[table].append(copy.deepcopy(payload[table][0]))


def orphan_first(table):
    return lambda payload: payload[table][0].update(oracle_id=UNKNOWN_UUID)


def representative_from(other):
    def change(payload):
        borrowed = card(payload, other)["source_scryfall_id"]
        card(payload, "Lightning Bolt")["source_scryfall_id"] = borrowed

    return change


def face_index_gap(payload):
    fire_ice = card(payload, "Fire // Ice")["oracle_id"]
    faces = [face for face in payload["faces"] if face["oracle_id"] == fire_ice]
    assert [face["face_index"] for face in faces] == [0, 1]
    faces[1]["face_index"] = 2


def transform_without_faces(payload):
    drop(
        payload,
        "faces",
        oracle_id=card(payload, "Delver of Secrets // Insectile Aberration")["oracle_id"],
    )


def face_alias_missing(payload):
    drop(payload, "aliases", alias_key="ice", kind="face")


def canonical_alias_missing(payload):
    drop(payload, "aliases", alias_key="lightning bolt", kind="canonical")


def unnormalized_alias(payload):
    payload["aliases"].append(
        {
            "oracle_id": card(payload, "Lightning Bolt")["oracle_id"],
            "alias_key": "Bolt",
            "kind": "face",
        }
    )


def duplicate_image_slot(payload):
    images = printing_of(payload, "Delver of Secrets // Insectile Aberration")["images"]
    images.append(copy.deepcopy(images[0]))


def image_for_missing_face(payload):
    printing_of(payload, "Lightning Bolt")["images"].append(
        {
            "face_index": 0,
            "source_uri": "https://cards.scryfall.io/normal/front/x.jpg",
            "artist": None,
        }
    )


def renamed_set(payload):
    same_set = [row for row in payload["printings"] if row["set_code"] == "inr"]
    assert len(same_set) == 2
    same_set[1]["set_name"] = "Innistrad Remastered (renamed)"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        pytest.param(duplicate_first("cards"), "duplicate cards key", id="duplicate-card"),
        pytest.param(duplicate_first("faces"), "duplicate faces key", id="duplicate-face"),
        pytest.param(
            duplicate_first("printings"), "duplicate printings key", id="duplicate-printing"
        ),
        pytest.param(duplicate_first("aliases"), "duplicate aliases key", id="duplicate-alias"),
        pytest.param(orphan_first("printings"), "orphan printings row", id="orphan-printing"),
        pytest.param(orphan_first("faces"), "orphan faces row", id="orphan-face"),
        pytest.param(orphan_first("aliases"), "orphan aliases row", id="orphan-alias"),
        pytest.param(
            representative_from("Fire // Ice"),
            "representative printing must belong",
            id="representative-of-another-card",
        ),
        pytest.param(
            lambda payload: card(payload, "Lightning Bolt").update(source_scryfall_id=UNKNOWN_UUID),
            "representative printing must belong",
            id="representative-missing",
        ),
        pytest.param(
            lambda payload: card(payload, "Lightning Bolt").update(name_key="Lightning Bolt"),
            "invalid name_key",
            id="stale-name-key",
        ),
        pytest.param(face_index_gap, "contiguous from zero", id="face-index-gap"),
        pytest.param(
            transform_without_faces, "multi-face layout requires its faces", id="faceless-transform"
        ),
        pytest.param(face_alias_missing, "missing canonical or face alias", id="face-alias"),
        pytest.param(
            canonical_alias_missing, "missing canonical or face alias", id="canonical-alias"
        ),
        pytest.param(unnormalized_alias, "alias key is not normalized", id="unnormalized-alias"),
        pytest.param(duplicate_image_slot, "duplicate printing image slot", id="image-slot"),
        pytest.param(image_for_missing_face, "image references missing face", id="image-face"),
        pytest.param(renamed_set, "conflicting set names", id="set-name-conflict"),
    ],
)
def test_schema_valid_catalogs_with_broken_relationships_are_rejected(payload, change, message):
    change(payload)

    with pytest.raises(ValueError, match=message):
        validate_catalog(payload)


def with_distinct_sets(payload, total):
    template = printing_of(payload, "Lightning Bolt")
    existing = {row["set_code"] for row in payload["printings"]}
    payload["printings"].extend(
        {
            **template,
            "scryfall_id": f"extra-{index}",
            "set_code": f"x{index}",
            "set_name": f"X{index}",
        }
        for index in range(total - len(existing))
    )
    return payload


def test_set_vocabulary_bound_is_inclusive(payload):
    validate_relationships(with_distinct_sets(copy.deepcopy(payload), 4096))

    with pytest.raises(ValueError, match="set vocabulary exceeds metadata bound"):
        validate_relationships(with_distinct_sets(payload, 4097))


def test_manifest_detects_same_length_export_corruption(exported):
    raw, manifest = exported
    corrupted = raw.replace(b'"source":"scryfall"', b'"source":"scryfalL"', 1)
    assert len(corrupted) == len(raw)
    assert corrupted != raw

    with pytest.raises(ValueError, match="export checksum mismatch"):
        validate_manifest(manifest, corrupted)


def test_manifest_must_describe_the_snapshot_it_seals(exported):
    raw, manifest = exported
    other = {**manifest, "catalog_snapshot_id": "catalog-" + "0" * 64}

    with pytest.raises(ValueError, match="snapshot mismatch"):
        validate_manifest(other, raw)


@pytest.mark.parametrize("table", ["cards", "faces", "printings", "aliases"])
def test_manifest_row_counts_must_match_every_table(exported, table):
    raw, manifest = exported
    miscounted = copy.deepcopy(manifest)
    miscounted["row_counts"][table] += 1

    with pytest.raises(ValueError, match=f"{table} count mismatch"):
        validate_manifest(miscounted, raw)


def test_resealed_manifest_still_validates_the_catalog_it_seals(exported):
    raw, manifest = exported
    payload = json.loads(raw)
    card(payload, "Lightning Bolt")["name_key"] = "Lightning Bolt"
    resealed_raw = canonical_bytes(payload)
    resealed = {
        **manifest,
        "export_sha256": sha256(resealed_raw).hexdigest(),
        "export_bytes": len(resealed_raw),
    }

    with pytest.raises(ValueError, match="invalid name_key"):
        validate_manifest(resealed, resealed_raw)
