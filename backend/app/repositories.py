"""Repository layer — all DB access goes through here (repository pattern)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Asset, AuditLog, Collection, Comment, Relationship


class AssetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, asset: Asset) -> Asset:
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get(self, asset_id: str) -> Asset | None:
        return self.db.get(Asset, asset_id)

    def list(self, limit: int = 100) -> list[Asset]:
        stmt = select(Asset).order_by(Asset.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))

    def all(self) -> list[Asset]:
        return list(self.db.scalars(select(Asset)))

    def by_checksum(self, checksum: str) -> Asset | None:
        return self.db.scalar(select(Asset).where(Asset.checksum == checksum))

    def versions_of(self, root_id: str) -> list[Asset]:
        stmt = select(Asset).where(Asset.root_id == root_id).order_by(Asset.version)
        return list(self.db.scalars(stmt))

    def max_version(self, root_id: str) -> int:
        return self.db.scalar(select(func.max(Asset.version)).where(Asset.root_id == root_id)) or 0

    def save(self, asset: Asset) -> Asset:
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def delete(self, asset: Asset) -> None:
        self.db.delete(asset)
        self.db.commit()


class RelationshipRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, source_id: str, target_id: str, kind: str, score: float = 1.0) -> Relationship:
        rel = Relationship(source_id=source_id, target_id=target_id, kind=kind, score=score)
        self.db.add(rel)
        self.db.commit()
        return rel

    def all(self) -> list[Relationship]:
        return list(self.db.scalars(select(Relationship)))

    def for_asset(self, asset_id: str) -> list[Relationship]:
        stmt = select(Relationship).where(
            (Relationship.source_id == asset_id) | (Relationship.target_id == asset_id)
        )
        return list(self.db.scalars(stmt))


class CommentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, asset_id: str, author: str, body: str) -> Comment:
        c = Comment(asset_id=asset_id, author=author, body=body)
        self.db.add(c)
        self.db.commit()
        self.db.refresh(c)
        return c

    def for_asset(self, asset_id: str) -> list[Comment]:
        stmt = select(Comment).where(Comment.asset_id == asset_id).order_by(Comment.created_at)
        return list(self.db.scalars(stmt))


class AuditRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(self, action: str, asset_id: str | None = None, detail: dict | None = None) -> None:
        self.db.add(AuditLog(action=action, asset_id=asset_id, detail=detail or {}))
        self.db.commit()

    def recent(self, limit: int = 30) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))


class CollectionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, collection: Collection) -> Collection:
        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def all(self) -> list[Collection]:
        return list(self.db.scalars(select(Collection).order_by(Collection.created_at.desc())))

    def get(self, cid: str) -> Collection | None:
        return self.db.get(Collection, cid)
