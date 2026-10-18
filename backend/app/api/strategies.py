import difflib
import io
import uuid
import zipfile
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.deps import DB, CurrentUser, audit
from app.models import Strategy, StrategyCompatibilityReport, StrategyVersion
from app.schemas import CloneIn, NewVersionIn, StrategyPatch
from app.services.strategy_import import _unique_slug, create_version, import_scripts, slugify

router = APIRouter(prefix="/strategies", tags=["strategies"])

MAX_FILES_PER_REQUEST = 300


def _own(db, user, strategy_id: uuid.UUID) -> Strategy:
    st = db.scalar(select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
                   .options(selectinload(Strategy.versions).selectinload(StrategyVersion.report)))
    if st is None:
        raise HTTPException(404, "Strategy not found.")
    return st


def _version(st: Strategy, version_id: uuid.UUID) -> StrategyVersion:
    for v in st.versions:
        if v.id == version_id:
            return v
    raise HTTPException(404, "Version not found.")


def _summary(st: Strategy) -> dict:
    latest = st.versions[-1] if st.versions else None
    rep = latest.report if latest else None
    return {
        "id": st.id, "name": st.name, "slug": st.slug, "category": st.category, "tags": st.tags,
        "archived": st.archived, "created_at": st.created_at, "updated_at": st.updated_at,
        "version_count": len(st.versions),
        "latest_version": latest and {
            "id": latest.id, "number": latest.version_number, "pine_version": latest.pine_version,
            "script_kind": latest.script_kind.value, "declared_title": latest.declared_title,
            "source_filename": latest.source_filename, "created_at": latest.created_at,
            "input_count": len(latest.inputs),
        },
        "classification": rep.classification.value if rep else None,
        "finding_counts": {sev: sum(f["severity"] == sev for f in rep.findings) for sev in ("critical", "warning", "info")} if rep else {},
        "supported_timeframes": st.supported_timeframes,
        "backtest_count": 0,  # backtests arrive in Phase 3
    }


@router.get("")
def list_strategies(
    user: CurrentUser, db: DB,
    q: str | None = Query(default=None, max_length=200),
    classification: str | None = None,
    kind: str | None = None,
    tag: str | None = None,
    include_archived: bool = False,
):
    stmt = (select(Strategy).where(Strategy.user_id == user.id)
            .options(selectinload(Strategy.versions).selectinload(StrategyVersion.report),
                     selectinload(Strategy.versions).selectinload(StrategyVersion.inputs)))
    if not include_archived:
        stmt = stmt.where(Strategy.archived.is_(False))
    rows = [_summary(s) for s in db.scalars(stmt.order_by(Strategy.name))]
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r["name"].lower() or any(needle in t.lower() for t in r["tags"])
                or (r["latest_version"] and needle in (r["latest_version"]["source_filename"] or "").lower())]
    if classification:
        rows = [r for r in rows if r["classification"] == classification]
    if kind:
        rows = [r for r in rows if r["latest_version"] and r["latest_version"]["script_kind"] == kind]
    if tag:
        rows = [r for r in rows if tag in r["tags"]]
    return rows


@router.get("/stats")
def library_stats(user: CurrentUser, db: DB):
    latest = (select(StrategyVersion.strategy_id, func.max(StrategyVersion.version_number).label("n"))
              .join(Strategy).where(Strategy.user_id == user.id, Strategy.archived.is_(False))
              .group_by(StrategyVersion.strategy_id).subquery())
    rows = db.execute(
        select(StrategyCompatibilityReport.classification, StrategyVersion.script_kind, func.count())
        .join(StrategyVersion, StrategyCompatibilityReport.version_id == StrategyVersion.id)
        .join(latest, (latest.c.strategy_id == StrategyVersion.strategy_id) & (latest.c.n == StrategyVersion.version_number))
        .group_by(StrategyCompatibilityReport.classification, StrategyVersion.script_kind)
    ).all()
    by_cls: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for cls, kind, n in rows:
        by_cls[cls.value] = by_cls.get(cls.value, 0) + n
        by_kind[kind.value] = by_kind.get(kind.value, 0) + n
    return {"total": sum(by_cls.values()), "by_classification": by_cls, "by_kind": by_kind}


@router.post("/import")
async def import_files(
    request: Request, user: CurrentUser, db: DB,
    files: list[UploadFile] = File(...),
    on_title_match: Literal["new_version", "new_strategy"] = Form("new_version"),
):
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(413, f"Upload at most {MAX_FILES_PER_REQUEST} files at once, or put them in a ZIP.")
    payload = []
    for f in files:
        payload.append((f.filename or "upload", await f.read()))
    report = import_scripts(db, user.id, payload, on_title_match=on_title_match)
    audit(db, user, "strategy_import", detail={"files": len(payload), "counts": report.counts}, request=request)
    db.commit()
    return {"counts": report.counts, "items": [i.__dict__ for i in report.items]}


@router.get("/{strategy_id}")
def get_strategy(strategy_id: uuid.UUID, user: CurrentUser, db: DB):
    st = _own(db, user, strategy_id)
    out = _summary(st)
    out.update({k: getattr(st, k) for k in (
        "description", "hypothesis", "entry_conditions", "exit_conditions", "stop_methodology",
        "target_methodology", "session_restrictions", "notes", "known_limitations", "cloned_from_strategy_id")})
    out["versions"] = [{
        "id": v.id, "number": v.version_number, "created_at": v.created_at, "source_filename": v.source_filename,
        "source_sha256": v.source_sha256, "source_bytes": v.source_bytes, "pine_version": v.pine_version,
        "script_kind": v.script_kind.value, "change_note": v.change_note,
        "classification": v.report.classification.value if v.report else None,
        "cloned_from_version_id": v.cloned_from_version_id,
    } for v in reversed(st.versions)]
    return out


@router.patch("/{strategy_id}")
def patch_strategy(strategy_id: uuid.UUID, body: StrategyPatch, user: CurrentUser, db: DB):
    st = _own(db, user, strategy_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(st, k, v)
    db.commit()
    return get_strategy(strategy_id, user, db)


@router.get("/{strategy_id}/versions/{version_id}")
def get_version(strategy_id: uuid.UUID, version_id: uuid.UUID, user: CurrentUser, db: DB):
    st = _own(db, user, strategy_id)
    v = _version(st, version_id)
    rep = v.report
    return {
        "id": v.id, "number": v.version_number, "strategy_id": st.id, "source": v.source,
        "source_sha256": v.source_sha256, "source_filename": v.source_filename, "pine_version": v.pine_version,
        "script_kind": v.script_kind.value, "declared_title": v.declared_title, "declaration": v.declaration,
        "created_at": v.created_at, "change_note": v.change_note,
        "inputs": [{"position": i.position, "variable": i.variable, "type": i.input_type, "title": i.title,
                    "default_raw": i.default_raw, "default": i.default_value.get("value") if i.default_value else None,
                    "has_literal_default": bool(i.default_value), "options": i.options, "line": i.line}
                   for i in v.inputs],
        "report": rep and {
            "analyzer_version": rep.analyzer_version, "classification": rep.classification.value,
            "summary": rep.summary, "findings": rep.findings, "function_usage": rep.function_usage,
            "created_at": rep.created_at,
        },
    }


@router.get("/{strategy_id}/versions/{version_id}/source")
def download_source(strategy_id: uuid.UUID, version_id: uuid.UUID, user: CurrentUser, db: DB, request: Request):
    st = _own(db, user, strategy_id)
    v = _version(st, version_id)
    name = v.source_filename.split("/")[-1] or f"{st.slug}-v{v.version_number}.pine"
    audit(db, user, "strategy_export", f"{st.id}:{v.version_number}", request=request)
    db.commit()
    return Response(v.source.encode("utf-8"), media_type="text/plain; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{_safe(name)}"',
                             "X-Source-SHA256": v.source_sha256})


@router.post("/export")
def export_zip(ids: list[uuid.UUID], user: CurrentUser, db: DB, request: Request):
    """ZIP of the latest version of each strategy, exactly as imported."""
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sid in ids[:1000]:
            st = _own(db, user, sid)
            v = st.versions[-1]
            name = _safe(v.source_filename.split("/")[-1] or f"{st.slug}.pine")
            if name in used:
                name = f"{st.slug}-v{v.version_number}-{name}"
            used.add(name)
            zf.writestr(name, v.source.encode("utf-8"))
    audit(db, user, "strategy_export_zip", detail={"count": len(used)}, request=request)
    db.commit()
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="strategies.zip"'})


@router.post("/{strategy_id}/versions", status_code=201)
def add_version(strategy_id: uuid.UUID, body: NewVersionIn, user: CurrentUser, db: DB):
    st = _own(db, user, strategy_id)
    if any(v.source == body.source for v in st.versions):
        raise HTTPException(409, "This source is identical to an existing version.")
    v = create_version(db, st, body.source, st.versions[-1].source_filename if st.versions else "",
                       change_note=body.change_note or "Edited in XAU Lab")
    db.commit()
    return {"id": v.id, "number": v.version_number}


@router.post("/{strategy_id}/clone", status_code=201)
def clone(strategy_id: uuid.UUID, body: CloneIn, user: CurrentUser, db: DB, request: Request):
    src = _own(db, user, strategy_id)
    base = src.versions[-1]
    name = body.name or f"{src.name} (copy)"
    st = Strategy(user_id=user.id, name=name[:200], slug=_unique_slug(db, user.id, slugify(name)),
                  cloned_from_strategy_id=src.id,
                  **{k: getattr(src, k) for k in ("description", "hypothesis", "entry_conditions", "exit_conditions",
                                                  "stop_methodology", "target_methodology", "supported_timeframes",
                                                  "session_restrictions", "tags", "category", "known_limitations")})
    db.add(st)
    db.flush()
    create_version(db, st, base.source, base.source_filename,
                   change_note=f"Cloned from {src.name} v{base.version_number}", cloned_from=base)
    audit(db, user, "strategy_clone", f"{src.id}->{st.id}", request=request)
    db.commit()
    return {"id": st.id}


@router.get("/{strategy_id}/diff")
def diff(strategy_id: uuid.UUID, a: uuid.UUID, b: uuid.UUID, user: CurrentUser, db: DB):
    st = _own(db, user, strategy_id)
    va, vb = _version(st, a), _version(st, b)
    lines = list(difflib.unified_diff(va.source.splitlines(), vb.source.splitlines(),
                                      fromfile=f"v{va.version_number}", tofile=f"v{vb.version_number}", lineterm="", n=3))
    ia = {i.variable or i.title: i.default_raw for i in va.inputs}
    ib = {i.variable or i.title: i.default_raw for i in vb.inputs}
    return {
        "a": va.version_number, "b": vb.version_number, "unified": lines,
        "classification": [va.report.classification.value, vb.report.classification.value],
        "inputs_added": sorted(set(ib) - set(ia)), "inputs_removed": sorted(set(ia) - set(ib)),
        "inputs_changed": sorted(k for k in set(ia) & set(ib) if ia[k] != ib[k]),
    }


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "._- " else "_" for c in name)[:180]
