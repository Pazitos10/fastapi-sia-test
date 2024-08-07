from datetime import datetime
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import relationship, mapped_column, Mapped
from sqlalchemy.sql import func
from typing import Optional, List
from ..database import Base
from ..audit_mixin import AuditMixin

class Folder(Base, AuditMixin):
    __tablename__ = "folder"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entity.id"))
    entity: Mapped["src.entity.models.Entity"] = relationship(
        "src.entity.models.Entity"
    )
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenant.id"))
    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="folders"
    )
    devices: Mapped[List["src.device.models.Device"]] = relationship(
        "src.device.models.Device", back_populates="folder"
    )
    parent_id: Mapped[int] = mapped_column(ForeignKey("folder.id"), nullable=True)
    subfolders = relationship("Folder")

    @property
    def tags(self):
        return self.entity.tags

    def add_tag(self, tag: "src.tag.models.Tag") -> None:
        self.tags.append(tag)
