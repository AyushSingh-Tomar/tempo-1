from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from bordereaux.core.exceptions import ConflictError, NotFoundError, ValidationError
from bordereaux.storage import paths
from bordereaux.storage.local import LocalStorageService
from bordereaux.storage.service import StorageResult, StorageService

pytestmark = pytest.mark.unit


def test_satisfies_protocol(storage: LocalStorageService) -> None:
    assert isinstance(storage, StorageService)


async def test_upload_download_checksum_round_trip(storage: LocalStorageService) -> None:
    data = b"policy_no,gross\nP1,10000\n"
    result = await storage.upload("p/sources/a/original/file.csv", data, content_type="text/csv")

    assert isinstance(result, StorageResult)
    assert result.path == "p/sources/a/original/file.csv"
    assert result.size_bytes == len(data)
    assert result.checksum == hashlib.sha256(data).hexdigest()
    assert result.content_type == "text/csv"
    assert result.created_at.tzinfo is not None

    assert await storage.download(result.path) == data
    assert await storage.checksum(result.path) == result.checksum
    assert await storage.verify_checksum(result.path, result.checksum.upper())
    assert not await storage.verify_checksum(result.path, "0" * 64)


async def test_upload_async_iterator(storage: LocalStorageService) -> None:
    chunks = [b"abc", b"def", b"ghi"]

    async def gen():
        for c in chunks:
            yield c

    result = await storage.upload("x/stream.bin", gen())
    assert result.size_bytes == 9
    assert result.checksum == hashlib.sha256(b"abcdefghi").hexdigest()
    assert await storage.download("x/stream.bin") == b"abcdefghi"


async def test_download_stream_in_chunks(tmp_path: Path) -> None:
    svc = LocalStorageService(tmp_path / "s", chunk_size=4)
    await svc.upload("a/b.bin", b"0123456789")
    received = [c async for c in svc.download_stream("a/b.bin")]
    assert received == [b"0123", b"4567", b"89"]


async def test_immutability_conflict_and_idempotent_reupload(storage: LocalStorageService) -> None:
    first = await storage.upload("k/raw.csv", b"one")
    same = await storage.upload("k/raw.csv", b"one")
    assert same.checksum == first.checksum

    with pytest.raises(ConflictError):
        await storage.upload("k/raw.csv", b"two")
    assert await storage.download("k/raw.csv") == b"one"

    replaced = await storage.upload("k/raw.csv", b"two", overwrite=True)
    assert replaced.checksum == hashlib.sha256(b"two").hexdigest()
    assert await storage.download("k/raw.csv") == b"two"


async def test_upload_file_and_download_to_file(storage: LocalStorageService, tmp_path: Path) -> None:
    src = tmp_path / "local.xlsx"
    src.write_bytes(b"PK\x03\x04fake-xlsx")
    result = await storage.upload_file("p/sources/a/original/local.xlsx", src)
    assert result.checksum == hashlib.sha256(src.read_bytes()).hexdigest()

    dest = tmp_path / "out" / "copy.xlsx"
    await storage.download_to_file(result.path, dest)
    assert dest.read_bytes() == src.read_bytes()

    with pytest.raises(NotFoundError):
        await storage.upload_file("p/missing", tmp_path / "nope.bin")


async def test_missing_objects(storage: LocalStorageService) -> None:
    assert not await storage.exists("nope/x")
    with pytest.raises(NotFoundError):
        await storage.download("nope/x")
    with pytest.raises(NotFoundError):
        async for _ in storage.download_stream("nope/x"):
            pass
    with pytest.raises(NotFoundError):
        await storage.download_to_file("nope/x", Path("unused"))
    await storage.delete("nope/x")  # no-op


async def test_exists_delete_and_list(storage: LocalStorageService) -> None:
    await storage.upload("proj/sources/a1/original/f.csv", b"1")
    await storage.upload("proj/sources/a2/original/g.csv", b"22")
    await storage.upload("proj/runs/r1/reports/rep.json", b"{}")
    await storage.upload("other/x.bin", b"x")

    assert await storage.exists("proj/sources/a1/original/f.csv")

    objs = await storage.list_objects("proj/sources")
    assert [o.path for o in objs] == ["proj/sources/a1/original/f.csv", "proj/sources/a2/original/g.csv"]
    assert objs[1].size_bytes == 2

    partial = await storage.list_objects("proj/sources/a")  # S3-style partial prefix
    assert len(partial) == 2
    assert len(await storage.list_objects("")) == 4
    assert len(await storage.list_objects("proj", max_keys=1)) == 1
    assert await storage.list_objects("does/not/exist") == []

    await storage.delete("proj/sources/a1/original/f.csv")
    assert not await storage.exists("proj/sources/a1/original/f.csv")


@pytest.mark.parametrize("bad", ["", "   ", "/abs/path", "C:/windows/x", "../escape", "a/../../b", "a//b"])
async def test_rejects_unsafe_paths(storage: LocalStorageService, bad: str) -> None:
    with pytest.raises(ValidationError):
        await storage.upload(bad, b"x")


async def test_backslashes_are_normalized(storage: LocalStorageService) -> None:
    result = await storage.upload("a\\b\\c.txt", b"x")
    assert result.path == "a/b/c.txt"
    assert await storage.exists("a/b/c.txt")


async def test_directory_at_target_is_conflict(storage: LocalStorageService) -> None:
    await storage.upload("d/inner/file.txt", b"x")
    with pytest.raises(ConflictError):
        await storage.upload("d/inner", b"y")


def test_presigned_url_is_file_uri(storage: LocalStorageService) -> None:
    url = storage.get_presigned_url("a/b.txt")
    assert url.startswith("file:///")
    with pytest.raises(ValidationError):
        storage.get_presigned_url("a/b.txt", method="DELETE")


async def test_health_check(storage: LocalStorageService) -> None:
    assert await storage.health_check() is True


async def test_no_temp_files_left_behind(storage: LocalStorageService) -> None:
    await storage.upload("t/a.bin", b"a")
    with pytest.raises(ConflictError):
        await storage.upload("t/a.bin", b"b")
    leftovers = [p.name for p in (storage.root / "t").iterdir()]
    assert leftovers == ["a.bin"]


def test_path_helpers() -> None:
    pid, aid, vid, rid = uuid4(), uuid4(), uuid4(), uuid4()
    assert paths.raw_source_path(pid, aid, "../../evil/Bord ereaux.xlsx") == (
        f"{pid}/sources/{aid}/original/Bord ereaux.xlsx"
    )
    assert paths.parsed_version_path(pid, aid, vid) == f"{pid}/sources/{aid}/parsed/{vid}.parquet"
    assert paths.profile_path(pid, vid) == f"{pid}/profiles/{vid}.json"
    assert paths.mapping_set_path(pid, vid) == f"{pid}/mappings/{vid}.json"
    assert paths.cleaned_data_path(pid, rid, 2) == f"{pid}/runs/{rid}/cleaned/attempt-2.parquet"
    assert paths.processed_artifact_path(pid, rid, vid, ".XLSX") == f"{pid}/runs/{rid}/processed/{vid}.xlsx"
    assert paths.report_artifact_path(pid, rid, vid, "pdf") == f"{pid}/runs/{rid}/reports/{vid}.pdf"
    assert paths.safe_filename("...") == "file"
    assert paths.safe_filename("a:b*c?.csv") == "a_b_c_.csv"
    with pytest.raises(ValueError):
        paths.report_artifact_path(pid, rid, vid, "../x")
