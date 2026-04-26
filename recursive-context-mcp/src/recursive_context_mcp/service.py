"""Service layer for recursive-context-mcp."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from .config import RecursiveContextConfig
from .context_io import list_files, make_source, read_context_slice, search_context
from .models import BufferRecord, ContextSession, ContextSource, ProgramRunRecord, now_utc
from .program import execute_program
from .store import RecursiveContextStore


class ProgramContextAPI:
    """Small context API exposed to optional inspection programs."""

    def __init__(self, service: "RecursiveContextService", session_id: str):
        self._service = service
        self._session_id = session_id

    def stats(self) -> dict[str, Any]:
        return self._service.inspect_context(self._session_id, max_files=0)["stats"]

    def list_files(self, glob: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self._service.list_context_files(self._session_id, glob=glob, limit=limit)["files"]

    def search(self, query: str, glob: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        return self._service.search_context(self._session_id, query=query, glob=glob, limit=limit)["hits"]

    def read(self, source_id: str, relative_path: str | None = None, start_line: int = 1, max_lines: int = 80) -> str:
        return self._service.read_context_slice(
            self._session_id,
            source_id=source_id,
            relative_path=relative_path,
            start_line=start_line,
            max_lines=max_lines,
        )["slice"]["text"]


class RecursiveContextService:
    """Application service for RLM-style context sessions."""

    def __init__(self, store: RecursiveContextStore, config: RecursiveContextConfig):
        self._store = store
        self._config = config

    def start_session(
        self,
        context_uris: list[str],
        name: str = "",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not context_uris:
            raise ValueError("context_uris must contain at least one local path")
        sources = [make_source(uri) for uri in context_uris]
        session = ContextSession(
            name=name,
            description=description,
            sources=sources,
            metadata=metadata or {},
        )
        self._store.create_session(session)
        return {
            "session_id": session.id,
            "decision": "READY",
            "sources": [source.model_dump(mode="json") for source in session.sources],
            "instruction": (
                "Treat the registered context as an external environment. Inspect and slice it before "
                "asking sub-queries or answering from memory."
            ),
        }

    def _session(self, session_id: str) -> ContextSession:
        return self._store.get_session(session_id)

    @staticmethod
    def _source_by_id(session: ContextSession, source_id: str) -> ContextSource:
        for source in session.sources:
            if source.id == source_id:
                return source
        raise KeyError(f"Unknown source_id: {source_id}")

    def inspect_context(self, session_id: str, max_files: int = 30) -> dict[str, Any]:
        session = self._session(session_id)
        files = list_files(session.sources, limit=max_files if max_files > 0 else 100000)
        all_files = files if max_files == 0 else list_files(session.sources, limit=100000)
        stats = {
            "source_count": len(session.sources),
            "file_count": len(all_files),
            "text_file_count": sum(1 for entry in all_files if entry.is_text),
            "total_bytes": sum(entry.size_bytes for entry in all_files),
        }
        return {
            "session_id": session.id,
            "name": session.name,
            "description": session.description,
            "stats": stats,
            "sources": [source.model_dump(mode="json") for source in session.sources],
            "files": [entry.model_dump(mode="json") for entry in files[:max_files]] if max_files > 0 else [],
        }

    def list_context_files(self, session_id: str, glob: str | None = None, limit: int = 100) -> dict[str, Any]:
        session = self._session(session_id)
        files = list_files(session.sources, glob=glob, limit=limit)
        return {"session_id": session_id, "files": [entry.model_dump(mode="json") for entry in files]}

    def search_context(
        self,
        session_id: str,
        query: str,
        regex: bool = False,
        glob: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        session = self._session(session_id)
        hits = search_context(session.sources, query=query, config=self._config, regex=regex, glob=glob, limit=limit)
        return {"session_id": session_id, "hits": [hit.model_dump(mode="json") for hit in hits]}

    def read_context_slice(
        self,
        session_id: str,
        source_id: str,
        relative_path: str | None = None,
        start_line: int = 1,
        max_lines: int = 80,
    ) -> dict[str, Any]:
        session = self._session(session_id)
        source = self._source_by_id(session, source_id)
        result = read_context_slice(
            source,
            relative_path=relative_path,
            start_line=start_line,
            max_lines=max_lines,
            config=self._config,
        )
        return {"session_id": session_id, "slice": result.model_dump(mode="json")}

    def commit_buffer(
        self,
        session_id: str,
        name: str,
        content: str,
        kind: str = "note",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._session(session_id)
        record = BufferRecord(
            session_id=session_id,
            name=name,
            kind=kind,  # type: ignore[arg-type]
            content=content,
            metadata=metadata or {},
        )
        self._store.add_buffer(record)
        return {"session_id": session_id, "buffer": record.model_dump(mode="json")}

    def get_buffer(self, session_id: str, buffer_id: str | None = None, name: str | None = None) -> dict[str, Any]:
        record = self._store.get_buffer(session_id, buffer_id=buffer_id, name=name)
        return {"session_id": session_id, "buffer": record.model_dump(mode="json")}

    def list_buffers(self, session_id: str, kind: str | None = None) -> dict[str, Any]:
        self._session(session_id)
        buffers = self._store.list_buffers(session_id, kind=kind)
        return {"session_id": session_id, "buffers": [buffer.model_dump(mode="json") for buffer in buffers]}

    def prepare_sub_query(
        self,
        session_id: str,
        prompt: str,
        slice_refs: list[dict[str, Any]] | None = None,
        buffer_names: list[str] | None = None,
        name: str = "sub-query",
    ) -> dict[str, Any]:
        self._session(session_id)
        packet: dict[str, Any] = {"prompt": prompt, "slices": [], "buffers": []}

        for ref in slice_refs or []:
            packet["slices"].append(
                self.read_context_slice(
                    session_id,
                    source_id=ref["source_id"],
                    relative_path=ref.get("relative_path"),
                    start_line=int(ref.get("start_line", 1)),
                    max_lines=int(ref.get("max_lines", 80)),
                )["slice"]
            )

        for buffer_name in buffer_names or []:
            packet["buffers"].append(self.get_buffer(session_id, name=buffer_name)["buffer"])

        record = BufferRecord(
            session_id=session_id,
            name=name,
            kind="sub_query",
            content=str(packet),
            metadata={"packet": packet},
        )
        self._store.add_buffer(record)
        return {
            "session_id": session_id,
            "sub_query_buffer_id": record.id,
            "packet": packet,
            "instruction": "Send this packet to the chosen sub-agent/model, then record the result.",
        }

    def record_sub_result(
        self,
        session_id: str,
        sub_query_buffer_id: str,
        content: str,
        name: str = "sub-result",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._session(session_id)
        self._store.get_buffer(session_id, buffer_id=sub_query_buffer_id)
        record = BufferRecord(
            session_id=session_id,
            name=name,
            kind="sub_result",
            content=content,
            metadata={"sub_query_buffer_id": sub_query_buffer_id, **(metadata or {})},
        )
        self._store.add_buffer(record)
        return {"session_id": session_id, "buffer": record.model_dump(mode="json")}

    def run_program(self, session_id: str, code: str) -> dict[str, Any]:
        self._session(session_id)
        if not self._config.enable_programs:
            record = ProgramRunRecord(
                session_id=session_id,
                code=code,
                error="Program execution is disabled. Set RECURSIVE_CONTEXT_ENABLE_PROGRAMS=true to enable it.",
            )
            self._store.add_program_run(record)
            return {"session_id": session_id, "run": record.model_dump(mode="json"), "enabled": False}

        try:
            result, stdout = execute_program(code, ProgramContextAPI(self, session_id))
            record = ProgramRunRecord(session_id=session_id, code=code, result=result, stdout=stdout)
        except Exception as exc:  # noqa: BLE001 - returned as an inspectable program trace
            record = ProgramRunRecord(session_id=session_id, code=code, error=str(exc))
        self._store.add_program_run(record)
        return {"session_id": session_id, "run": record.model_dump(mode="json"), "enabled": True}

    def finalize_session(
        self,
        session_id: str,
        summary: str,
        buffer_names: list[str] | None = None,
    ) -> dict[str, Any]:
        self._session(session_id)
        selected_buffers = []
        for name in buffer_names or []:
            selected_buffers.append(self.get_buffer(session_id, name=name)["buffer"])
        record = BufferRecord(
            session_id=session_id,
            name="final",
            kind="final",
            content=summary,
            metadata={"included_buffers": selected_buffers},
        )
        self._store.add_buffer(record)
        session = self._session(session_id)
        session.updated_at = now_utc().astimezone(timezone.utc)
        self._store.update_session(session)
        return {"session_id": session_id, "final": record.model_dump(mode="json")}

    def get_session_trace(self, session_id: str) -> dict[str, Any]:
        session = self._session(session_id)
        return {
            "session": session.model_dump(mode="json"),
            "buffers": [buffer.model_dump(mode="json") for buffer in self._store.list_buffers(session_id)],
            "program_runs": [run.model_dump(mode="json") for run in self._store.list_program_runs(session_id)],
            "privacy": {
                "private_chain_of_thought": "not stored",
                "sub_query_packets": "contain explicit slices and public buffer contents only",
            },
        }
