import os, re, ast, sys
from pathlib import Path

ROOT = Path.cwd()
BACKEND = ROOT / "backend"
BORD = BACKEND / "src" / "bordereaux"
DOCS = ROOT / "docs" / "project-context"
MODULES_MD = DOCS / "MODULE_CONTRACTS.md"
MIGRATIONS = BACKEND / "migrations" / "versions"

def read_file(p):
    try:
        return p.read_text(encoding="utf-8")
    except Exception as e:
        return f"<error reading {p}: {e}>"

def find_storage_impls():
    out = []
    storage_dir = BORD / "storage"
    if not storage_dir.exists():
        return "storage/ not found"
    for p in storage_dir.rglob("*.py"):
        src = read_file(p)
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            out.append((str(p), "SYNTAX ERROR: " + str(e)))
            continue
        classes = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                bases = []
                for b in node.bases:
                    try:
                        bases.append(ast.unparse(b))
                    except Exception:
                        bases.append(getattr(b, 'id', str(b)))
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                classes.append({"name": node.name, "bases": bases, "methods": methods})
        if classes:
            out.append((str(p), classes))
    return out

def extract_contract_section():
    if not MODULES_MD.exists():
        return "<MODULE_CONTRACTS.md not found>"
    data = MODULES_MD.read_text(encoding="utf-8")
    sections = {}
    for name in ("StorageService", "AuditService"):
        m = re.search(rf"(#+\s*{re.escape(name)}.*?)(?=\n#+\s*\w|\Z)", data, re.S|re.I)
        sections[name] = m.group(1).strip() if m else "<section not found>"
    return sections

def list_models():
    models_dir = BORD / "models"
    if not models_dir.exists():
        return "models/ not found"
    models = []
    for p in models_dir.rglob("*.py"):
        src = read_file(p)
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            models.append((str(p), "SYNTAX ERROR: " + str(e)))
            continue
        classes = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                tab = None
                for n in node.body:
                    if isinstance(n, ast.Assign):
                        for target in n.targets:
                            if isinstance(target, ast.Name) and target.id == "__tablename__":
                                try:
                                    tab = ast.literal_eval(n.value)
                                except Exception:
                                    tab = "<non-literal>"
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                classes.append({"name": node.name, "tablename": tab, "methods": methods})
        if classes:
            models.append((str(p), classes))
    return models

def list_migrations():
    if not MIGRATIONS.exists():
        return "migrations/versions not found"
    files = [str(p) for p in MIGRATIONS.glob("*.py")]
    return files

def compare_models_to_migrations(models, migrations):
    tabs = []
    for _, clslist in models:
        for c in clslist:
            if c.get("tablename"):
                tabs.append(c["tablename"])
    found = {}
    for m in migrations:
        txt = read_file(Path(m))
        for t in tabs:
            if t and (f"'{t}'" in txt or f'"{t}"' in txt or t in txt):
                found.setdefault(t, []).append(m)
    missing = [t for t in tabs if t not in found]
    return {"found": found, "missing": missing}

def inspect_audit():
    audit_dir = BORD / "audit"
    if not audit_dir.exists():
        return "audit/ not found"
    details = []
    for p in audit_dir.rglob("*.py"):
        src = read_file(p)
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            details.append((str(p), "SYNTAX ERROR: " + str(e)))
            continue
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and re.search(r'(?i)audit', node.name):
                methods = [n for n in node.body if isinstance(n, ast.FunctionDef)]
                method_names = [m.name for m in methods]
                sigs = {}
                for m in methods:
                    args = [a.arg for a in m.args.args]
                    sigs[m.name] = args
                details.append((str(p), node.name, method_names, sigs))
    return details

def inspect_jobs():
    jobs_dir = BORD / "jobs"
    if not jobs_dir.exists():
        return "jobs/ not found"
    findings = []
    for p in jobs_dir.rglob("*.py"):
        txt = read_file(p)
        flags = []
        for token in ("Redis", "redis", "Celery", "celery", "asyncio.Queue", "aioredis", "rq", "huey", "kombu", "select_for_update", "SKIP LOCKED", "for_update"):
            if token in txt:
                flags.append(token)
        if flags:
            findings.append((str(p), flags))
    wiring = []
    for p in BORD.rglob("*.py"):
        txt = read_file(p)
        if any(k in txt for k in ("Celery(", "Redis(", "create_redis_pool", "aioredis", "Queue(")):
            wiring.append(str(p))
    return {"jobs_findings": findings, "wiring_candidates": wiring[:20]}

def static_checks():
    todo = []
    syntax = []
    for p in (BORD).rglob("*.py"):
        txt = read_file(p)
        if "TODO" in txt or "FIXME" in txt:
            lines = []
            for i,l in enumerate(txt.splitlines(),1):
                if "TODO" in l or "FIXME" in l:
                    lines.append(f"L{i}: {l.strip()}")
            todo.append((str(p), lines))
        try:
            ast.parse(txt)
        except SyntaxError as e:
            syntax.append((str(p), str(e)))
    return {"todos": todo, "syntax_errors": syntax}

def write_foundation_notes(content):
    notes_path = ROOT / ".claude" / "agents"
    notes_path.mkdir(parents=True, exist_ok=True)
    target = notes_path / "foundation-notes.md"
    target.write_text(content, encoding="utf-8")
    return str(target)

def main():
    print("Scanning backend/src/bordereaux ---\n")
    print("1) Storage implementations:")
    si = find_storage_impls()
    print(si, "\n")
    print("2) MODULE_CONTRACTS.md excerpts (StorageService / AuditService):")
    print(extract_contract_section(), "\n")
    print("3) Models found under models/:")
    models = list_models()
    print(models, "\n")
    print("4) Migrations under backend/migrations/versions:")
    migrations = list_migrations()
    print(migrations, "\n")
    if isinstance(models, list) and isinstance(migrations, list):
        comp = compare_models_to_migrations(models, migrations)
        print("Model->migration comparison:", comp, "\n")
    print("5) Audit service inspection:")
    print(inspect_audit(), "\n")
    print("6) Jobs inspection (searching for queue integrations):")
    print(inspect_jobs(), "\n")
    print("7) Static checks (TODO/FIXME and syntax errors):")
    print(static_checks(), "\n")
    notes = """Bordereaux Foundation Agent notes

Summary:
The Foundation Agent is responsible for core infra: storage adapters, async job framework, audit logging, and DB models/migrations. This scan uncovered storage implementations, model files, migrations, audit classes, and jobs wiring that need verification and alignment with MODULE_CONTRACTS.md.

Actionable next steps:
- Verify StorageService implementations implement all methods declared in docs/project-context/MODULE_CONTRACTS.md and add missing methods or adapters.
- Ensure every SQLAlchemy model in src/bordereaux/models has a corresponding migration in backend/migrations/versions; create missing migrations.
- Confirm AuditService provides `log` and `query` with expected parameters and add tests to assert audit logging on state changes.
- Wire an app-wide async queue (Redis/Celery/asyncio wrapper) if not present; add docs and initialization code.
- Triage TODO/FIXME items and replace NotImplemented placeholders in high-priority modules (storage, audit, jobs).
- Add unit tests for storage adapters and job claiming logic to reach >=90% coverage for foundation modules.
"""
    written = write_foundation_notes(notes)
    print("Wrote/updated foundation notes at:", written)
    print("\nScan complete. Paste the full output for me to analyze further or grant access to run this script.")

if __name__ == "__main__":
    main()
