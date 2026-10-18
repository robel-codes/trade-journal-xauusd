"""Import Pine Script files into the strategy library.

Scripts are untrusted input. They are decoded as text, stored byte-for-byte as uploaded (after UTF-8
decoding), hashed, and statically analyzed. Nothing is executed and nothing is rewritten.
"""

from __future__ import annotations

import hashlib
import io
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Strategy,
    StrategyCompatibilityReport,
    StrategyInput,
    StrategyVersion,
)
from app.pine.analyzer import analyze, normalized_hash

SCRIPT_EXTENSIONS = {".pine", ".txt"}
ARCHIVE_EXTENSIONS = {".zip"}


class ImportRejected(Exception):
    pass


@dataclass
class ImportItem:
    filename: str
    status: str  # imported | new_version | duplicate | near_duplicate | error
    message: str
    strategy_id: uuid.UUID | None = None
    version_id: uuid.UUID | None = None
    strategy_name: str = ""
    classification: str | None = None
    script_kind: str | None = None


@dataclass
class ImportReport:
    items: list[ImportItem] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for i in self.items:
            out[i.status] = out.get(i.status, 0) + 1
        return out


def decode_script(raw: bytes, filename: str) -> str:
    limit = get_settings().max_script_bytes
    if len(raw) > limit:
        raise ImportRejected(f"{filename} is {len(raw):,} bytes; the limit for one script is {limit:,} bytes.")
    if b"\x00" in raw:
        raise ImportRejected(f"{filename} contains binary data, so it is not a Pine Script text file.")
    try:
        text = raw.decode("utf-8")  # a BOM, if present, is kept so exports are byte-identical
    except UnicodeDecodeError as e:
        raise ImportRejected(
            f"{filename} is not valid UTF-8 (byte {e.start}). Re-save it as UTF-8 from TradingView's editor."
        ) from None
    if not text.strip():
        raise ImportRejected(f"{filename} is empty.")
    return text


def expand_uploads(files: list[tuple[str, bytes]]) -> tuple[list[tuple[str, bytes]], list[ImportItem]]:
    """Turn uploaded files (scripts and ZIPs) into a flat list of (name, bytes) scripts plus errors."""
    s = get_settings()
    scripts: list[tuple[str, bytes]] = []
    errors: list[ImportItem] = []
    for name, raw in files:
        ext = PurePosixPath(name.lower()).suffix
        if ext in SCRIPT_EXTENSIONS:
            scripts.append((name, raw))
        elif ext in ARCHIVE_EXTENSIONS:
            if len(raw) > s.max_zip_bytes:
                errors.append(ImportItem(name, "error", f"Archive is larger than {s.max_zip_bytes:,} bytes."))
                continue
            try:
                zf = zipfile.ZipFile(io.BytesIO(raw))
            except zipfile.BadZipFile:
                errors.append(ImportItem(name, "error", "Not a valid ZIP archive."))
                continue
            members = [m for m in zf.infolist() if not m.is_dir()]
            if len(members) > s.max_zip_members:
                errors.append(ImportItem(name, "error", f"Archive has {len(members)} files; the limit is {s.max_zip_members}."))
                continue
            total = sum(m.file_size for m in members)
            if total > s.max_zip_uncompressed_bytes:
                errors.append(ImportItem(name, "error", "Archive expands beyond the allowed size."))
                continue
            for m in members:
                p = PurePosixPath(m.filename)
                label = f"{name}/{m.filename}"
                if p.is_absolute() or ".." in p.parts:
                    errors.append(ImportItem(label, "error", "Unsafe path inside archive; skipped."))
                    continue
                if any(part.startswith(".") or part == "__MACOSX" for part in p.parts):
                    continue  # OS metadata, silently ignored by design
                mext = p.suffix.lower()
                if mext in ARCHIVE_EXTENSIONS:
                    errors.append(ImportItem(label, "error", "Nested archives are not supported."))
                    continue
                if mext not in SCRIPT_EXTENSIONS:
                    errors.append(ImportItem(label, "error", f"Unsupported file type {mext or '(none)'}; use .pine or .txt."))
                    continue
                if m.compress_size and m.file_size / m.compress_size > 200:
                    errors.append(ImportItem(label, "error", "Compression ratio is suspiciously high; skipped."))
                    continue
                scripts.append((label, zf.read(m)))
        else:
            errors.append(ImportItem(name, "error", f"Unsupported file type {ext or '(none)'}; use .pine, .txt or .zip."))
    return scripts, errors


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:150] or "strategy"


def _unique_slug(db: Session, user_id: uuid.UUID, base: str) -> str:
    slug, n = base, 2
    while db.scalar(select(Strategy.id).where(Strategy.user_id == user_id, Strategy.slug == slug)):
        slug, n = f"{base}-{n}", n + 1
    return slug


def create_version(db: Session, strategy: Strategy, source: str, filename: str, change_note: str = "",
                   cloned_from: StrategyVersion | None = None) -> StrategyVersion:
    result = analyze(source)
    number = (max((v.version_number for v in strategy.versions), default=0)) + 1
    version = StrategyVersion(
        strategy=strategy,
        version_number=number,
        source=source,
        source_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        normalized_sha256=normalized_hash(source),
        source_filename=filename,
        source_bytes=len(source.encode("utf-8")),
        pine_version=result.pine_version,
        script_kind=result.script_kind,
        declared_title=result.declared_title,
        declaration=result.declaration,
        change_note=change_note,
        cloned_from_version_id=cloned_from.id if cloned_from else None,
    )
    version.inputs = [
        StrategyInput(position=p.position, variable=p.variable, input_type=p.input_type, title=p.title,
                      default_raw=p.default_raw, default_value=p.default_value, options=p.options, line=p.line)
        for p in result.inputs
    ]
    version.report = StrategyCompatibilityReport(
        analyzer_version=result.analyzer_version,
        classification=result.classification,
        summary=result.summary,
        findings=[f.__dict__ for f in result.findings],
        function_usage={"calls": result.function_usage, "user_functions": result.user_functions,
                        "imports": result.imports},
    )
    db.add(version)
    return version


def import_scripts(db: Session, user_id: uuid.UUID, files: list[tuple[str, bytes]],
                   on_title_match: str = "new_version") -> ImportReport:
    """Import scripts. `on_title_match`: "new_version" adds a version to the strategy with the same
    declared title; "new_strategy" always creates a separate strategy."""
    report = ImportReport()
    scripts, errors = expand_uploads(files)
    report.items.extend(errors)
    seen_in_batch: dict[str, str] = {}

    for name, raw in scripts:
        try:
            source = decode_script(raw, name)
        except ImportRejected as e:
            report.items.append(ImportItem(name, "error", str(e)))
            continue
        sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
        norm = normalized_hash(source)
        if sha in seen_in_batch or norm in seen_in_batch:
            report.items.append(ImportItem(name, "duplicate", f"Same script as {seen_in_batch.get(sha) or seen_in_batch[norm]} in this upload."))
            continue
        seen_in_batch[sha] = seen_in_batch[norm] = name

        existing = db.execute(
            select(StrategyVersion, Strategy).join(Strategy)
            .where(Strategy.user_id == user_id, StrategyVersion.source_sha256 == sha)
        ).first()
        if existing:
            v, st = existing
            report.items.append(ImportItem(name, "duplicate", f"Identical to {st.name} v{v.version_number}; not imported.",
                                           st.id, v.id, st.name))
            continue
        near = db.execute(
            select(StrategyVersion, Strategy).join(Strategy)
            .where(Strategy.user_id == user_id, StrategyVersion.normalized_sha256 == norm)
        ).first()
        if near:
            v, st = near
            report.items.append(ImportItem(
                name, "near_duplicate",
                f"Differs from {st.name} v{v.version_number} only in comments or whitespace; not imported.",
                st.id, v.id, st.name))
            continue

        title = analyze(source).declared_title
        display = title or PurePosixPath(name).stem
        target = None
        if on_title_match == "new_version" and title:
            target = db.scalar(
                select(Strategy).join(StrategyVersion)
                .where(Strategy.user_id == user_id, StrategyVersion.declared_title == title)
                .order_by(Strategy.created_at).limit(1)
            )
        if target:
            v = create_version(db, target, source, name, change_note=f"Imported from {name}")
            db.flush()
            report.items.append(ImportItem(name, "new_version", f"Added as v{v.version_number} of {target.name}.",
                                           target.id, v.id, target.name, v.report.classification.value,
                                           v.script_kind.value))
            continue
        st = Strategy(user_id=user_id, name=display[:200], slug=_unique_slug(db, user_id, slugify(display)))
        db.add(st)
        db.flush()
        v = create_version(db, st, source, name, change_note=f"Imported from {name}")
        db.flush()
        report.items.append(ImportItem(name, "imported", "Imported.", st.id, v.id, st.name,
                                       v.report.classification.value, v.script_kind.value))
    return report
