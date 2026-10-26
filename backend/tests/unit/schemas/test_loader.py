import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.schemas import load_schema_definition, required_fields, seed_canonical_schema, treaty_figure_fields


def test_load_schema_definition_has_58_fields():
    definition = load_schema_definition()
    assert definition["id"] == "bordereaux-pc-v1"
    assert len(definition["fields"]) == 58  # 52 bordereaux fields + 6 treaty figures


def test_treaty_figure_fields_are_the_six_group_j_fields():
    definition = load_schema_definition()
    fields = treaty_figure_fields(definition)
    assert fields == [
        "treaty_commission_pct",
        "treaty_brokerage_pct",
        "treaty_tax_pct",
        "treaty_cession_pct",
        "treaty_order_pct",
        "treaty_fx_rate",
    ]
    # Every treaty figure is explicitly sourced from user input, not the file.
    for f in definition["fields"]:
        if f["category"] == "TREATY_FIGURES":
            assert f["source"] == "user_input"


def test_required_fields_are_mandatory_only():
    definition = load_schema_definition()
    mandatory = required_fields(definition)
    assert "gross_premium" in mandatory
    assert "limit" not in mandatory  # optional
    assert "treaty_brokerage_pct" not in mandatory  # conditional


def test_money_role_fields_cover_the_premium_flow():
    load_schema_definition()
    from bordereaux.schemas.loader import MONEY_ROLE_BY_FIELD

    assert MONEY_ROLE_BY_FIELD["gross_premium"] == "GROSS"
    assert MONEY_ROLE_BY_FIELD["commission"] == "COMMISSION"
    assert MONEY_ROLE_BY_FIELD["tax"] == "TAX"
    assert MONEY_ROLE_BY_FIELD["net_premium"] == "NET"
    assert MONEY_ROLE_BY_FIELD["final_net_premium"] == "FINAL_NET"
    assert MONEY_ROLE_BY_FIELD["gross_premium_our_share"] == "OUR_SHARE"


async def test_seed_canonical_schema_is_idempotent(db_session: AsyncSession):
    first = await seed_canonical_schema(db_session)
    await db_session.commit()
    second = await seed_canonical_schema(db_session)
    assert first.id == second.id == "bordereaux-pc-v1"


async def test_changed_dictionary_is_stored_as_a_new_version_and_the_old_one_is_kept(db_session: AsyncSession, monkeypatch):
    from bordereaux.models.schema import CanonicalSchema
    from bordereaux.schemas import loader

    original = loader.load_schema_definition()
    # A database seeded before the alias additions: same id, older version and content.
    old = {**original, "version": "1.0.0", "fields": original["fields"][:-1]}
    db_session.add(CanonicalSchema(id=original["id"], name=old["name"], version="1.0.0", definition=old))
    await db_session.commit()

    current = await seed_canonical_schema(db_session)
    await db_session.commit()
    assert current.id == f"{original['id']}@{original['version']}" and current.version == original["version"]
    assert current.definition == original
    assert (await db_session.get(CanonicalSchema, original["id"])).definition == old  # history untouched
    assert (await seed_canonical_schema(db_session)).id == current.id  # and it is stable

    # Editing the YAML without bumping its version is refused, not silently ignored.
    edited = {**original, "fields": [{**original["fields"][0], "aliases": ["Brand New Alias"]}, *original["fields"][1:]]}
    monkeypatch.setattr(loader, "load_schema_definition", lambda filename="bordereaux_pc_v1.yaml": edited)
    with pytest.raises(loader.SchemaVersionError):
        await loader.seed_canonical_schema(db_session)


def test_fingerprint_ignores_key_order():
    from bordereaux.schemas.loader import definition_fingerprint

    assert definition_fingerprint({"a": 1, "b": [1, 2]}) == definition_fingerprint({"b": [1, 2], "a": 1})
    assert definition_fingerprint({"a": 1}) != definition_fingerprint({"a": 2})
