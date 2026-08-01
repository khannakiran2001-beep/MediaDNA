"""Service layer — application use-cases (ingest, fork, version)."""
from __future__ import annotations

from sqlalchemy.orm import Session

import re

from ..models import Asset
from ..repositories import (
    AssetRepository,
    AuditRepository,
    RelationshipRepository,
)
from . import genblaze_runner, pipeline, search
from .providers import get_provider
from .storage import get_storage


class AssetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.assets = AssetRepository(db)
        self.rels = RelationshipRepository(db)
        self.audit = AuditRepository(db)
        self.storage = get_storage()
        self.provider = get_provider()

    def ingest(
        self,
        *,
        filename: str,
        raw: bytes,
        mime_type: str,
        prompt: str = "",
        negative_prompt: str = "",
        model: str = "",
        provider_name: str = "",
        project: str = "",
        campaign: str = "",
        tags: list[str] | None = None,
        generation_params: dict | None = None,
        parent_id: str | None = None,
        owner_id: str | None = None,
        owner_email: str = "",
    ) -> Asset:
        asset = Asset(
            name=filename,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model or ("uploaded" if not model else model),
            provider=provider_name or self.provider.name,
            project=project,
            campaign=campaign,
            tags=tags or [],
            generation_params=generation_params or {},
            owner_id=owner_id,
            owner_email=owner_email,
        )
        # establish version lineage
        if parent_id:
            parent = self.assets.get(parent_id)
            if parent:
                asset.parent_id = parent.id
                asset.root_id = parent.root_id or parent.id
                asset.version = self.assets.max_version(asset.root_id) + 1
        # persist row first to obtain id
        asset = self.assets.add(asset)
        if not asset.root_id:
            asset.root_id = asset.id
            self.assets.save(asset)

        # run Genblaze pipeline
        result = pipeline.run(
            asset_id=asset.id,
            filename=filename,
            raw=raw,
            mime_type=mime_type,
            prompt=prompt,
            provider=self.provider,
        )

        # store artifacts
        for key, (data, ctype) in result.artifacts.items():
            self.storage.put(key, data, ctype)
        asset.storage_backend = self.storage.name

        # apply DNA fields
        for field_name, value in result.fields.items():
            setattr(asset, field_name, value)
        asset.mime_type = mime_type
        self.assets.save(asset)

        # relationships: explicit parent edge + auto-detected
        if asset.parent_id:
            self.rels.add(asset.parent_id, asset.id, "edited_to", 1.0)
        existing = [a for a in self.assets.all() if a.id != asset.id]
        for target_id, kind, score in search.find_relationships(asset, existing):
            self.rels.add(asset.id, target_id, kind, float(score))

        self.audit.log("ingest", asset.id, {"filename": filename, "provider": asset.provider})
        return asset

    def generate(
        self,
        *,
        prompt: str,
        negative_prompt: str = "",
        model: str = "flux",
        project: str = "",
        campaign: str = "",
        tags: list[str] | None = None,
        owner_id: str | None = None,
        owner_email: str = "",
    ) -> Asset:
        """Generate via the real Genblaze Pipeline, then run the analysis pipeline.

        Genblaze orchestrates the generation step and produces a verified
        provenance manifest; the resulting bytes are stored (B2 via the official
        SDK, or local) and analysed for the DNA record / semantic search.
        """
        gen = genblaze_runner.run_generation(prompt, model=model, modality="image")
        slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:40] or "generated"
        asset = self.ingest(
            filename=f"{slug}.png",
            raw=gen.raw,
            mime_type=gen.media_type,
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            provider_name="Genblaze",
            project=project,
            campaign=campaign,
            tags=tags or [],
            generation_params={
                "generated": True,
                "genblaze_run_id": gen.run_id,
                "generation_backend": gen.generation_backend,
                "manifest_canonical_hash": gen.canonical_hash,
                "manifest_verified": gen.manifest_verified,
                "model": model,
            },
            owner_id=owner_id,
            owner_email=owner_email,
        )
        # The Genblaze manifest is the authoritative provenance record.
        if gen.manifest:
            asset.provenance = {
                "source": "genblaze",
                "genblaze_run_id": gen.run_id,
                "canonical_hash": gen.canonical_hash,
                "verified": gen.manifest_verified,
                "manifest": gen.manifest,
            }
            self.assets.save(asset)
        self.audit.log("generate", asset.id, {
            "prompt": prompt,
            "genblaze_run_id": gen.run_id,
            "manifest_verified": gen.manifest_verified,
            "backend": gen.generation_backend,
        })
        return asset

    def fork(self, source_id: str, new_prompt: str | None, note: str) -> Asset | None:
        source = self.assets.get(source_id)
        if not source:
            return None
        raw = self.storage.get(source.storage_key)
        child = self.ingest(
            filename=f"fork_{source.name}",
            raw=raw,
            mime_type=source.mime_type,
            prompt=new_prompt or source.prompt,
            negative_prompt=source.negative_prompt,
            model=source.model,
            provider_name=source.provider,
            project=source.project,
            campaign=source.campaign,
            tags=source.tags,
            generation_params={**(source.generation_params or {}), "forked_from": source.id, "note": note},
            parent_id=source.id,
        )
        self.rels.add(source.id, child.id, "forked_to", 1.0)
        self.audit.log("fork", child.id, {"source": source.id, "note": note})
        return child
