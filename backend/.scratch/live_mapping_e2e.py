"""Live check (real DIAL call): upload a semantic-header workbook, generate mappings and
show what the AI step did. Run from backend/:  venv/Scripts/python.exe .scratch/live_mapping_e2e.py [file] [sheet]
Uses a throw-away database/storage; the key comes from backend/.env and is never printed."""

import asyncio
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "src")
import httpx

from bordereaux.config import Settings
from bordereaux.main import create_app

FIXTURES = Path("../Initial provided Info/Test_files")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
H = {"Authorization": "Bearer dev-admin1-admin"}


async def main(fname: str, sheet: str) -> None:
    tmp = Path(tempfile.mkdtemp())
    settings = Settings(database_url=f"sqlite+aiosqlite:///{(tmp / 'live.db').as_posix()}", storage_root=tmp / "storage")
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=300) as c:
            st = (await c.get("/api/v1/ai/status", headers=H)).json()["data"]
            print("AI status:", st)
            pid = (await c.post("/api/v1/projects", json={"name": "live"}, headers=H)).json()["data"]["id"]
            f = FIXTURES / fname
            r = await c.post(f"/api/v1/projects/{pid}/processing-runs", files={"file": (f.name, f.read_bytes(), XLSX)}, headers=H)
            run_id = r.json()["data"]["run"]["id"]
            base = f"/api/v1/processing-runs/{run_id}"
            for step, kw in (("validate", {"params": {"sheet_name": sheet}}), ("clean", {}), ("cleaning/acknowledge", {})):
                rr = await c.post(f"{base}/{step}", headers=H, **kw)
                assert rr.status_code == 200, rr.text
            await c.put(f"{base}/mappings/target-format", json={"mode": "DEFAULT"}, headers=H)
            t = time.time()
            rr = await c.post(f"{base}/mappings/generate", headers=H)
            print(f"generate -> {rr.status_code} in {time.time() - t:.1f}s")
            print("ai:", rr.json()["data"].get("ai"))
            cands = (await c.get(f"{base}/mappings/candidates", headers=H)).json()["data"]["candidates"]
            for cd in cands:
                ev = [e for e in cd["evidence"] if e.get("type") in ("ai_suggestion", "ai_note", "ai_preferred_other")]
                if ev:
                    print(f"  {cd['source_column']!r:32} -> {cd['target_field']:28} {cd['status']:9} {cd['confidence_total']}  {[ (e['type'], e.get('reason') or e.get('message')) for e in ev]}")
            act = (await c.get(f"{base}/ai/activity", headers=H)).json()["data"]
            print("activity:", [(i["purpose"], i["status"], i["items_sent"], i["items_resolved"], i["latency_ms"]) for i in act["interactions"]])


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "test_map_02_semantic.xlsx", sys.argv[2] if len(sys.argv) > 2 else "Bordereaux"))
