from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.mapping.service import generate_mapping_candidates
from bordereaux.cleaning.service import acknowledge_cleaning, run_cleaning
from sqlalchemy import select

from bordereaux.core.exceptions import BusinessRuleError, StateError
from bordereaux.ingestion.service import create_processing_run_with_upload, validate_processing_run
from bordereaux.mapping.service import (
    approve_candidate,
    approve_exact_matches,
    create_manual_mapping,
    finalize_mappings,
    list_candidates,
    reject_candidate,
    reopen_candidate,
    set_target_format,
)
from bordereaux.models.mapping import ApprovedMapping
from bordereaux.models.project import Project, User
from bordereaux.storage.local import LocalStorageService

pytestmark = [pytest.mark.unit, pytest.mark.integration]

FIXTURES = Path(__file__).resolve().parents[4] / "Initial provided Info" / "Test_files"
skip_no_fixtures = pytest.mark.skipif(not FIXTURES.exists(), reason="fixture directory not present")


async def _prepare_run(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User, filename: str):
    content = (FIXTURES / filename).read_bytes()
    result = await create_processing_run_with_upload(db_session, storage, project.id, filename, content, user.id, sheet_name="Bordereaux")
    run = result["run"]
    await validate_processing_run(db_session, storage, run.id, user.id)
    await run_cleaning(db_session, storage, run.id, user.id)
    await acknowledge_cleaning(db_session, storage, run.id, user.id)
    await generate_mapping_candidates(db_session, storage, run.id, user.id)
    return run


@skip_no_fixtures
async def test_exact_and_fuzzy_resolution(db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User):
    run = await _prepare_run(db_session, storage, project, user, "test_map_01_exact_fuzzy.xlsx")
    candidates = await list_candidates(db_session, run.id)
    by_source = {c.source_column: c for c in candidates}

    # "UMR" is an exact match.
    assert by_source["UMR"].target_field == "umr"
    assert by_source["UMR"].evidence[0]["stage"] == "EXACT"
    # A dictionary term mapped to its dictionary field is a 100% match.
    assert float(by_source["UMR"].confidence_total) == 1.0

    # Abbreviated headers resolve via fuzzy matching - typos ("Net Prm") and
    # abbreviations ("Pol Nmbr", "Grs Prem") alike - with the stage recorded as evidence.
    assert by_source["Net Prm"].target_field == "net_premium"
    assert by_source["Net Prm"].evidence[0]["stage"] == "FUZZY"
    assert by_source["Pol Nmbr"].target_field == "policy_ref"
    assert by_source["Pol Nmbr"].evidence[0]["stage"] == "FUZZY"
    assert by_source["Grs Prem"].target_field == "gross_premium"

    # A header with no dictionary or fuzzy signal is never silently guessed - it
    # falls through to pass-through rather than a wrong auto-mapping.
    assert by_source["Our Internal Ref"].target_field == "extra_our_internal_ref"
    assert by_source["Our Internal Ref"].status == "APPROVED"

    # Never auto-approved just because the name looks similar.
    fuzzy = [c for c in candidates if c.evidence and c.evidence[0].get("stage") == "FUZZY"]
    assert fuzzy and all(c.status == "PROPOSED" and c.auto_approve_eligible is False for c in fuzzy)


@skip_no_fixtures
async def test_unlabelled_money_columns_pass_through_until_financial_checks(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    run = await _prepare_run(db_session, storage, project, user, "test_map_03_arithmetic_passthrough.xlsx")
    candidates = await list_candidates(db_session, run.id)
    by_source = {c.source_column: c for c in candidates}

    # "Vendor Code" / "Priority" are genuine pass-through columns, never
    # dropped, never blocking, auto-approved as extras.
    assert by_source["Vendor Code"].target_field == "extra_vendor_code"
    assert by_source["Vendor Code"].status == "APPROVED"
    assert by_source["Priority"].target_field == "extra_priority"

    # "Amount 1".."Amount 6" carry no name signal. Column relationships are
    # not part of mapping any more (the arithmetic check runs in financial
    # checks once treaty figures exist), so they pass through untouched.
    for c in candidates:
        if c.source_column.startswith("Amount"):
            assert c.target_field.startswith("extra_")
            assert c.status == "APPROVED"
            assert "relationship" not in c.confidence_breakdown and "historical" not in c.confidence_breakdown


@skip_no_fixtures
async def test_finalize_blocks_on_missing_mandatory_fields(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    run = await _prepare_run(db_session, storage, project, user, "test_map_03_arithmetic_passthrough.xlsx")
    with pytest.raises(BusinessRuleError) as exc_info:
        await finalize_mappings(db_session, storage, run.id, user.id)
    assert "missing_fields" in exc_info.value.details[0]


async def test_finalize_allows_missing_fields_when_the_source_file_has_no_matching_column(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    content = b"UMR\nA1\nA2\n"
    result = await create_processing_run_with_upload(db_session, storage, project.id, "f.csv", content, user.id)
    run = result["run"]
    await validate_processing_run(db_session, storage, run.id, user.id)
    await run_cleaning(db_session, storage, run.id, user.id)
    await acknowledge_cleaning(db_session, storage, run.id, user.id)
    await generate_mapping_candidates(db_session, storage, run.id, user.id)

    candidates = await list_candidates(db_session, run.id)
    umr = next(c for c in candidates if c.source_column == "UMR")
    await approve_candidate(db_session, umr.id, user.id)

    mapping_set = await finalize_mappings(db_session, storage, run.id, user.id)
    assert mapping_set.status == "FINALIZED"


async def test_passthrough_never_blocks_and_is_logged(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    content = b"UMR,Totally Unknown Column\nUMR-1,xyz\nUMR-2,abc\n"
    result = await create_processing_run_with_upload(db_session, storage, project.id, "f.csv", content, user.id)
    run = result["run"]
    await validate_processing_run(db_session, storage, run.id, user.id)
    await run_cleaning(db_session, storage, run.id, user.id)
    await acknowledge_cleaning(db_session, storage, run.id, user.id)
    await generate_mapping_candidates(db_session, storage, run.id, user.id)

    candidates = await list_candidates(db_session, run.id)
    unknown = [c for c in candidates if c.source_column == "Totally Unknown Column"][0]
    assert unknown.target_field == "extra_totally_unknown_column"
    assert unknown.status == "APPROVED"
    assert unknown.evidence[0]["reason"] == "no_canonical_match"


async def _csv_run(db_session, storage, project, user, content: bytes, mode: str = "DEFAULT", columns=None):
    result = await create_processing_run_with_upload(db_session, storage, project.id, "f.csv", content, user.id)
    run = result["run"]
    await validate_processing_run(db_session, storage, run.id, user.id)
    await run_cleaning(db_session, storage, run.id, user.id)
    await acknowledge_cleaning(db_session, storage, run.id, user.id)
    await set_target_format(db_session, run.id, user.id, mode, columns)
    await generate_mapping_candidates(db_session, storage, run.id, user.id)
    return run


async def test_no_candidates_until_generated(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    result = await create_processing_run_with_upload(db_session, storage, project.id, "f.csv", b"UMR\nA1\n", user.id)
    run = result["run"]
    await validate_processing_run(db_session, storage, run.id, user.id)
    await run_cleaning(db_session, storage, run.id, user.id)
    await acknowledge_cleaning(db_session, storage, run.id, user.id)
    assert await list_candidates(db_session, run.id) == []


async def test_custom_target_format_maps_to_user_columns(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    run = await _csv_run(
        db_session, storage, project, user,
        b"UMR,Policy Holder Mood,Gross Prem\nU1,happy,100\n",
        mode="CUSTOM", columns=["UMR", "Policy Holder Mood", "Gross Premium"],
    )
    by_source = {c.source_column: c for c in await list_candidates(db_session, run.id)}
    # A user column named exactly like the source header is a 100% match, even
    # when it is not in the default dictionary.
    assert by_source["Policy Holder Mood"].target_field == "policy_holder_mood"
    assert float(by_source["Policy Holder Mood"].confidence_total) == 1.0
    # A user column that matches a dictionary field keeps its canonical field.
    assert by_source["UMR"].target_field == "umr"
    assert by_source["Gross Prem"].target_field == "gross_premium"


async def test_custom_target_format_excludes_dictionary_fields_it_does_not_list(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    run = await _csv_run(
        db_session, storage, project, user,
        b"UMR,Gross Premium\nU1,100\n", mode="CUSTOM", columns=["UMR"],
    )
    by_source = {c.source_column: c for c in await list_candidates(db_session, run.id)}
    assert by_source["Gross Premium"].target_field == "extra_gross_premium"


async def test_target_format_requires_mapping_review_state(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    result = await create_processing_run_with_upload(db_session, storage, project.id, "f.csv", b"UMR\nA1\n", user.id)
    with pytest.raises(StateError):
        await set_target_format(db_session, result["run"].id, user.id, "DEFAULT")


async def test_reject_falls_back_to_passthrough_and_can_be_reopened_or_remapped(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    run = await _csv_run(db_session, storage, project, user, b"UMR,Gross Premium\nU1,100\n")
    cands = {c.source_column: c for c in await list_candidates(db_session, run.id)}
    gp = cands["Gross Premium"]
    assert float(gp.confidence_total) == 1.0

    await reject_candidate(db_session, gp.id, user.id, "wrong column")
    after = [c for c in await list_candidates(db_session, run.id) if c.source_column == "Gross Premium"]
    assert {c.status for c in after} == {"REJECTED", "APPROVED"}
    assert any(c.target_field == "extra_gross_premium" and c.status == "APPROVED" for c in after)

    # Reopen -> approve replaces the fallback pass-through.
    await reopen_candidate(db_session, gp.id, user.id)
    await approve_candidate(db_session, gp.id, user.id)
    after = {c.id: c for c in await list_candidates(db_session, run.id) if c.source_column == "Gross Premium"}
    assert after[gp.id].status == "APPROVED"
    assert all(c.status != "APPROVED" for c in after.values() if c.id != gp.id)

    # Manual re-map supersedes the approval; the target must exist in the format.
    await create_manual_mapping(db_session, run.id, "Gross Premium", "net_premium", user.id)
    with pytest.raises(BusinessRuleError):
        await create_manual_mapping(db_session, run.id, "Gross Premium", "not_a_field", user.id)


async def test_duplicate_target_cannot_be_mapped_twice(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    run = await _csv_run(db_session, storage, project, user, b"UMR,Gross Premium,Gross Prem\nU1,100,100\n")
    await create_manual_mapping(db_session, run.id, "Gross Prem", "gross_premium", user.id)
    with pytest.raises(StateError) as exc:
        await create_manual_mapping(db_session, run.id, "Gross Premium", "gross_premium", user.id)
    assert exc.value.code == "DUPLICATE_TARGET_MAPPING"


async def test_approve_exact_matches_only_approves_100_percent(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    run = await _csv_run(db_session, storage, project, user, b"UMR,Net Prm,Totally Unknown\nU1,90,x\n")
    result = await approve_exact_matches(db_session, run.id, user.id)
    assert result["approved"] == 1  # UMR only; "Net Prm" is a fuzzy (<100%) match
    by_source = {c.source_column: c for c in await list_candidates(db_session, run.id)}
    assert by_source["UMR"].status == "APPROVED"
    assert by_source["Net Prm"].status == "PROPOSED"


async def test_finalize_blocks_on_open_required_proposal_then_passes_after_reject(
    db_session: AsyncSession, storage: LocalStorageService, project: Project, user: User
):
    run = await _csv_run(db_session, storage, project, user, b"UMR,Net Prm\nU1,90\n")
    await approve_exact_matches(db_session, run.id, user.id)
    # "Net Prm" is a mandatory field present in the file but still only proposed.
    with pytest.raises(BusinessRuleError):
        await finalize_mappings(db_session, storage, run.id, user.id)

    net = next(c for c in await list_candidates(db_session, run.id) if c.source_column == "Net Prm")
    await reject_candidate(db_session, net.id, user.id, "not net premium")
    await finalize_mappings(db_session, storage, run.id, user.id)
    approved = {
        a.source_column: a.target_field
        for a in (await db_session.execute(select(ApprovedMapping))).scalars().all()
    }
    assert approved["Net Prm"] == "extra_net_prm"


def test_confidence_weights_have_no_relationship_or_historical_bucket():
    from bordereaux.mapping.scoring import WEIGHTS, calculate_confidence

    assert set(WEIGHTS) == {"semantic", "value", "context", "layout", "ai"}
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9
    assert calculate_confidence({k: 1.0 for k in WEIGHTS}) == pytest.approx(1.0)
