"""Filesystem-backed research notebook persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from config import DATA_DIR


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned or "notebook"


def _default_cells() -> list[dict[str, Any]]:
    return [
        {
            "id": "cell-1",
            "type": "code",
            "content": "# Start here\nprint('New notebook')",
            "output": [],
        }
    ]


@dataclass
class NotebookRecord:
    id: str
    profile: str
    name: str
    description: str
    cells: list[dict[str, Any]]
    created_at: str
    updated_at: str

    @property
    def cell_count(self) -> int:
        return len(self.cells)

    def to_dict(self, *, is_active: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "profile": self.profile,
            "name": self.name,
            "description": self.description,
            "cell_count": self.cell_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": is_active,
            "cells": self.cells,
        }

    def summary(self, *, is_active: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "profile": self.profile,
            "name": self.name,
            "description": self.description,
            "cell_count": self.cell_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_active": is_active,
        }


class NotebookService:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_path = Path(base_dir or DATA_DIR) / "notebooks"
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _profile_path(self, profile: str) -> Path:
        path = self.base_path / profile
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _meta_path(self, profile: str) -> Path:
        return self._profile_path(profile) / "meta.json"

    def _notebook_path(self, profile: str, notebook_id: str) -> Path:
        return self._profile_path(profile) / f"{notebook_id}.json"

    def _load_meta(self, profile: str) -> dict[str, Any]:
        path = self._meta_path(profile)
        if not path.exists():
            return {"active_notebook_id": None}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {"active_notebook_id": None}

    def _save_meta(self, profile: str, meta: dict[str, Any]) -> None:
        self._meta_path(profile).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def _read_record(self, profile: str, notebook_id: str) -> NotebookRecord | None:
        path = self._notebook_path(profile, notebook_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return NotebookRecord(
            id=data["id"],
            profile=data["profile"],
            name=data["name"],
            description=data.get("description", ""),
            cells=data.get("cells", []),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def _write_record(self, record: NotebookRecord) -> None:
        path = self._notebook_path(record.profile, record.id)
        payload = record.to_dict()
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_notebooks(self, profile: str) -> tuple[list[dict[str, Any]], str | None]:
        meta = self._load_meta(profile)
        active_id = meta.get("active_notebook_id")
        profile_path = self._profile_path(profile)
        records: list[NotebookRecord] = []
        for path in profile_path.glob("*.json"):
            if path.name == "meta.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(
                    NotebookRecord(
                        id=data["id"],
                        profile=data["profile"],
                        name=data["name"],
                        description=data.get("description", ""),
                        cells=data.get("cells", []),
                        created_at=data["created_at"],
                        updated_at=data["updated_at"],
                    )
                )
            except Exception:
                continue
        records.sort(key=lambda item: item.updated_at, reverse=True)
        summaries = [record.summary(is_active=(record.id == active_id)) for record in records]
        return summaries, active_id

    def get_notebook(self, profile: str, notebook_id: str) -> NotebookRecord:
        record = self._read_record(profile, notebook_id)
        if record is None:
            raise FileNotFoundError(notebook_id)
        return record

    def create_notebook(
        self,
        profile: str,
        *,
        name: str,
        description: str = "",
        cells: list[dict[str, Any]] | None = None,
        activate: bool = True,
    ) -> NotebookRecord:
        notebook_id = f"{_slugify(name)}-{uuid4().hex[:8]}"
        now = _utc_now()
        record = NotebookRecord(
            id=notebook_id,
            profile=profile,
            name=name.strip() or "Untitled Notebook",
            description=description.strip(),
            cells=cells if cells is not None and len(cells) > 0 else _default_cells(),
            created_at=now,
            updated_at=now,
        )
        self._write_record(record)
        if activate:
            self.set_active_notebook(profile, notebook_id)
        return record

    def update_notebook(
        self,
        profile: str,
        notebook_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        cells: list[dict[str, Any]] | None = None,
        activate: bool | None = None,
    ) -> NotebookRecord:
        record = self.get_notebook(profile, notebook_id)
        if name is not None:
            record.name = name.strip() or record.name
        if description is not None:
            record.description = description.strip()
        if cells is not None:
            record.cells = cells
        record.updated_at = _utc_now()
        self._write_record(record)
        if activate is True:
            self.set_active_notebook(profile, notebook_id)
        elif activate is False:
            meta = self._load_meta(profile)
            if meta.get("active_notebook_id") == notebook_id:
                meta["active_notebook_id"] = None
                self._save_meta(profile, meta)
        return record

    def duplicate_notebook(self, profile: str, notebook_id: str, *, name: str | None = None) -> NotebookRecord:
        source = self.get_notebook(profile, notebook_id)
        duplicate_name = name.strip() if name else f"{source.name} Copy"
        return self.create_notebook(
            profile,
            name=duplicate_name,
            description=source.description,
            cells=source.cells,
            activate=True,
        )

    def delete_notebook(self, profile: str, notebook_id: str) -> None:
        path = self._notebook_path(profile, notebook_id)
        if path.exists():
            path.unlink()
        meta = self._load_meta(profile)
        if meta.get("active_notebook_id") == notebook_id:
            meta["active_notebook_id"] = None
            self._save_meta(profile, meta)
        summaries, active_id = self.list_notebooks(profile)
        if meta.get("active_notebook_id") is None and summaries:
            self.set_active_notebook(profile, summaries[0]["id"])

    def set_active_notebook(self, profile: str, notebook_id: str) -> None:
        record = self.get_notebook(profile, notebook_id)
        meta = self._load_meta(profile)
        meta["active_notebook_id"] = record.id
        self._save_meta(profile, meta)

    def resolve_active_notebook(self, profile: str) -> NotebookRecord | None:
        _, active_id = self.list_notebooks(profile)
        if not active_id:
            return None
        return self._read_record(profile, active_id)

