"""Live: server has AI OFF; a user supplies their own key through the API; the app must use it.
Run from backend/:  venv/Scripts/python.exe .scratch/live_user_key_e2e.py   (key read from ../future-notes-for-myself.txt, never printed)"""
import asyncio, re, sys, tempfile
from pathlib import Path
sys.path.insert(0, "src")
import httpx
from bordereaux.config import Settings
from bordereaux.main import create_app

KEY = re.search(r'API KEY\s*:\s*"?([A-Za-z0-9_\-]{16,})"?', Path("../future-notes-for-myself.txt").read_text(encoding="utf-8")).group(1)
F = Path("../Initial provided Info/Test_files/test_map_02_semantic.xlsx")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
H = {"Authorization": "Bearer dev-alice-analyst"}

async def main():
    tmp = Path(tempfile.mkdtemp())
    s = Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{(tmp/'k.db').as_posix()}", storage_root=tmp/"storage",
                 llm_enabled=False, llm_provider="disabled")
    app = create_app(s)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t", timeout=300) as c:
            st = (await c.get("/api/v1/ai/status", headers=H)).json()["data"]
            print("before :", st["available"], st["key_source"], "|", st["reason"])
            bad = (await c.put("/api/v1/me/ai-key", json={"api_key": "definitely-not-a-valid-key-123"}, headers=H)).json()["data"]
            print("bad key:", "saved=", bad["saved"], bad["test"]["status"], "-", bad["test"]["message"][:70])
            ok = (await c.put("/api/v1/me/ai-key", json={"api_key": KEY}, headers=H)).json()["data"]
            print("real   : saved=", ok["saved"], ok["test"]["status"], f"{ok['test']['latency_ms']}ms", "source=", ok["key_source"], "hint=", ok["user_key"]["hint"])
            assert KEY not in (await c.get("/api/v1/me/ai-key", headers=H)).text
            pid = (await c.post("/api/v1/projects", json={"name": "k"}, headers=H)).json()["data"]["id"]
            r = await c.post(f"/api/v1/projects/{pid}/processing-runs", files={"file": (F.name, F.read_bytes(), XLSX)}, headers=H)
            base = f"/api/v1/processing-runs/{r.json()['data']['run']['id']}"
            for step, kw in (("validate", {"params": {"sheet_name": "Bordereaux"}}), ("clean", {}), ("cleaning/acknowledge", {})):
                assert (await c.post(f"{base}/{step}", headers=H, **kw)).status_code == 200
            await c.put(f"{base}/mappings/target-format", json={"mode": "DEFAULT"}, headers=H)
            g = (await c.post(f"{base}/mappings/generate", headers=H)).json()["data"]["ai"]
            print("mapping:", g["status"], g["message"], f"({g['latency_ms']}ms, {g['model']})")
            other = (await c.get("/api/v1/ai/status", headers={"Authorization": "Bearer dev-bob-analyst"})).json()["data"]
            print("bob    :", other["available"], other["key_source"])
            print("removed:", (await c.delete("/api/v1/me/ai-key", headers=H)).json()["data"]["key_source"])
asyncio.run(main())
