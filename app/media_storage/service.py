from __future__ import annotations

from datetime import datetime
import hashlib
import mimetypes
from pathlib import Path
import re
from typing import Mapping
from uuid import uuid4

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models
from app.media_storage.backend import StorageBackend
from app.media_storage.errors import (
    MediaArtifactError,
    MediaArtifactOwnershipError,
    MediaArtifactStateError,
    StorageError,
)


ARTIFACT_KINDS = frozenset(
    {
        "product_reference",
        "creator_reference",
        "provider_output",
        "master_video",
        "video_preview",
        "thumbnail",
        "quality_frame",
        "contact_sheet",
        "generation_report",
        "publishing_export",
    }
)
ACTIVE_MEDIA_STATUSES = frozenset({"ready", "archived"})
MIN_SIGNED_URL_TTL_SECONDS = 30
MAX_SIGNED_URL_TTL_SECONDS = 900


class MediaArtifactService:
    """Tenant-safe media persistence and ephemeral access capabilities."""

    def __init__(self, db: Session, backends: Mapping[str, StorageBackend]):
        self.db = db
        self.backends = dict(backends)
        if not self.backends:
            raise MediaArtifactError("At least one storage backend is required.")

    def store_bytes(
        self,
        *,
        organization_id: int,
        created_by_user_profile_id: int,
        backend_name: str,
        kind: str,
        content: bytes,
        mime_type: str,
        original_filename: str | None = None,
        product_id: int | None = None,
        product_ugc_recipe_draft_id: int | None = None,
        video_job_id: int | None = None,
        retention_class: str = "standard",
        retention_until: datetime | None = None,
        legal_hold: bool = False,
        metadata: dict | None = None,
    ) -> models.MediaArtifact:
        backend = self._backend(backend_name)
        self._require_actor(organization_id, created_by_user_profile_id)
        self._validate_links(
            organization_id=organization_id,
            product_id=product_id,
            product_ugc_recipe_draft_id=product_ugc_recipe_draft_id,
            video_job_id=video_job_id,
        )
        normalized_kind = self._kind(kind)
        normalized_mime = self._mime_type(mime_type)
        normalized_retention = self._retention_class(retention_class)
        if not content:
            raise MediaArtifactError("A media artifact cannot be empty.")
        safe_metadata = self._safe_metadata(metadata)
        safe_original_filename = self._original_filename(original_filename)
        public_id = uuid4().hex
        object_key = self.build_object_key(
            organization_id=organization_id,
            public_id=public_id,
            kind=normalized_kind,
            original_filename=safe_original_filename,
            product_id=product_id,
            product_ugc_recipe_draft_id=product_ugc_recipe_draft_id,
            video_job_id=video_job_id,
        )
        stored = backend.put_bytes(
            object_key,
            content,
            mime_type=normalized_mime,
            original_filename=safe_original_filename,
        )
        expected_sha = hashlib.sha256(content).hexdigest()
        if (
            stored.backend_name != backend.name
            or stored.bucket != backend.bucket
            or stored.key != object_key
            or stored.size_bytes != len(content)
            or stored.sha256 != expected_sha
        ):
            try:
                backend.delete(object_key)
            finally:
                raise MediaArtifactStateError("Storage backend returned inconsistent object metadata.")

        artifact = models.MediaArtifact(
            public_id=public_id,
            organization_id=organization_id,
            created_by_user_profile_id=created_by_user_profile_id,
            product_id=product_id,
            product_ugc_recipe_draft_id=product_ugc_recipe_draft_id,
            video_job_id=video_job_id,
            kind=normalized_kind,
            backend_name=backend.name,
            bucket=backend.bucket,
            object_key=object_key,
            object_version=stored.version_id,
            etag=stored.etag,
            original_filename=safe_original_filename,
            mime_type=normalized_mime,
            size_bytes=stored.size_bytes,
            sha256=expected_sha,
            status="ready",
            metadata_json=safe_metadata,
            retention_class=normalized_retention,
            retention_until=retention_until,
            legal_hold=bool(legal_hold),
        )
        try:
            self.db.add(artifact)
            self.db.flush()
        except Exception:
            # The row definitely did not reach COMMIT, so this upload is safe
            # to compensate.  Once COMMIT is attempted its outcome can be
            # ambiguous (for example, a lost response after the server commits),
            # and deleting the canonical object would corrupt a durable row.
            self.db.rollback()
            try:
                backend.delete(object_key)
            except StorageError:
                pass
            raise
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        try:
            self.db.refresh(artifact)
        except Exception:
            self.db.rollback()
            raise
        return artifact

    def store_file_idempotent(
        self,
        *,
        organization_id: int,
        created_by_user_profile_id: int,
        backend_name: str,
        idempotency_key: str,
        kind: str,
        source: Path,
        mime_type: str,
        original_filename: str | None = None,
        product_id: int | None = None,
        product_ugc_recipe_draft_id: int | None = None,
        video_job_id: int | None = None,
        retention_class: str = "standard",
        retention_until: datetime | None = None,
        legal_hold: bool = False,
        metadata: dict | None = None,
        trusted_worker: bool = False,
    ) -> models.MediaArtifact:
        """Stream one worker file into shared storage exactly once.

        The stable idempotency key also derives the opaque object identity, so
        a retry after a process or database failure targets the same object and
        never creates a second library item.
        """

        backend = self._backend(backend_name)
        if trusted_worker:
            self._require_attributable_actor(organization_id, created_by_user_profile_id)
        else:
            self._require_actor(organization_id, created_by_user_profile_id)
        self._validate_links(
            organization_id=organization_id,
            product_id=product_id,
            product_ugc_recipe_draft_id=product_ugc_recipe_draft_id,
            video_job_id=video_job_id,
        )
        key = self._idempotency_key(idempotency_key)
        normalized_kind = self._kind(kind)
        normalized_mime = self._mime_type(mime_type)
        normalized_retention = self._retention_class(retention_class)
        safe_metadata = self._safe_metadata(metadata)
        safe_original_filename = self._original_filename(original_filename or Path(source).name)

        existing = self._existing_idempotent(organization_id, key)
        if existing is not None:
            return self._validate_idempotent_artifact(
                existing,
                backend=backend,
                kind=normalized_kind,
                product_id=product_id,
                draft_id=product_ugc_recipe_draft_id,
                video_job_id=video_job_id,
            )

        source = Path(source)
        if not source.is_file():
            raise MediaArtifactStateError("Worker media source file is missing.")
        expected_sha, expected_size = self._file_fingerprint(source)
        if expected_size <= 0:
            raise MediaArtifactStateError("Worker media source file is empty.")
        public_id = hashlib.sha256(
            f"media-artifact\0{organization_id}\0{key}".encode("utf-8")
        ).hexdigest()[:32]
        object_key = self.build_object_key(
            organization_id=organization_id,
            public_id=public_id,
            kind=normalized_kind,
            original_filename=safe_original_filename,
            product_id=product_id,
            product_ugc_recipe_draft_id=product_ugc_recipe_draft_id,
            video_job_id=video_job_id,
        )

        stored = backend.head(object_key)
        object_preexisted = stored is not None
        if stored is None:
            stored = backend.put_file(
                object_key,
                source,
                mime_type=normalized_mime,
                original_filename=safe_original_filename,
            )
        if (
            stored.backend_name != backend.name
            or stored.bucket != backend.bucket
            or stored.key != object_key
            or stored.size_bytes != expected_size
            or (stored.sha256 and stored.sha256 != expected_sha)
        ):
            if not object_preexisted:
                try:
                    backend.delete(object_key)
                except StorageError:
                    pass
            raise MediaArtifactStateError("Stored worker object failed integrity verification.")
        if object_preexisted and not stored.sha256:
            try:
                existing_content = backend.read_bytes(object_key)
            except StorageError as exc:
                raise MediaArtifactStateError(
                    "Preexisting worker object could not be verified."
                ) from exc
            if (
                len(existing_content) != expected_size
                or hashlib.sha256(existing_content).hexdigest() != expected_sha
            ):
                raise MediaArtifactStateError(
                    "Preexisting worker object failed integrity verification."
                )

        artifact = models.MediaArtifact(
            public_id=public_id,
            idempotency_key=key,
            organization_id=organization_id,
            created_by_user_profile_id=created_by_user_profile_id,
            product_id=product_id,
            product_ugc_recipe_draft_id=product_ugc_recipe_draft_id,
            video_job_id=video_job_id,
            kind=normalized_kind,
            backend_name=backend.name,
            bucket=backend.bucket,
            object_key=object_key,
            object_version=stored.version_id,
            etag=stored.etag,
            original_filename=safe_original_filename,
            mime_type=normalized_mime,
            size_bytes=stored.size_bytes,
            sha256=expected_sha,
            status="ready",
            metadata_json=safe_metadata,
            retention_class=normalized_retention,
            retention_until=retention_until,
            legal_hold=bool(legal_hold),
        )
        try:
            self.db.add(artifact)
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            winner = self._existing_idempotent(organization_id, key)
            if winner is not None:
                return self._validate_idempotent_artifact(
                    winner,
                    backend=backend,
                    kind=normalized_kind,
                    product_id=product_id,
                    draft_id=product_ugc_recipe_draft_id,
                    video_job_id=video_job_id,
                )
            # Another writer can still be committing the deterministic row.
            # Keep its deterministic object for an idempotent retry.
            raise
        except Exception:
            self.db.rollback()
            if not object_preexisted:
                try:
                    backend.delete(object_key)
                except StorageError:
                    pass
            raise
        try:
            self.db.commit()
        except Exception:
            # COMMIT may have succeeded remotely even when the client receives
            # an error.  Never compensate storage after this boundary.
            self.db.rollback()
            raise
        try:
            self.db.refresh(artifact)
        except Exception:
            # The row is already durable; deleting its object here would leave
            # a committed MediaArtifact pointing at missing bytes.
            self.db.rollback()
            raise
        return artifact

    def get_owned(
        self,
        public_id: str,
        *,
        organization_id: int,
    ) -> models.MediaArtifact:
        artifact = self.db.scalar(
            select(models.MediaArtifact).where(
                models.MediaArtifact.public_id == str(public_id),
                models.MediaArtifact.organization_id == organization_id,
            )
        )
        if artifact is None:
            raise MediaArtifactOwnershipError("Media artifact was not found in this organization.")
        self._assert_tenant_key(artifact)
        return artifact

    def read_worker_input(
        self,
        artifact_id: int,
        *,
        organization_id: int,
        product_id: int,
        expected_kind: str,
        max_size_bytes: int,
    ) -> tuple[models.MediaArtifact, bytes]:
        """Read an immutable provider input after tenant and integrity checks.

        This is deliberately a worker-only, capability-free path: it reads the
        configured private backend directly and never creates or persists a
        signed URL.  Both backend metadata and the downloaded bytes must match
        the database fingerprint before the caller may submit paid work.
        """

        artifact = self.db.scalar(
            select(models.MediaArtifact).where(
                models.MediaArtifact.id == int(artifact_id),
                models.MediaArtifact.organization_id == int(organization_id),
            )
        )
        if artifact is None:
            raise MediaArtifactOwnershipError(
                "Recipe input artifact was not found in this organization."
            )
        self._assert_tenant_key(artifact)
        kind = self._kind(expected_kind)
        if artifact.kind != kind or artifact.product_id != int(product_id):
            raise MediaArtifactOwnershipError(
                "Recipe input artifact is outside the requested product scope."
            )
        maximum = int(max_size_bytes)
        if maximum <= 0:
            raise MediaArtifactStateError("Recipe input size limit is invalid.")
        if (
            artifact.status != "ready"
            or artifact.deleted_at is not None
            or artifact.size_bytes <= 0
            or artifact.size_bytes > maximum
            or not str(artifact.mime_type or "").lower().startswith("image/")
            or not re.fullmatch(r"[a-f0-9]{64}", str(artifact.sha256 or ""))
        ):
            raise MediaArtifactStateError("Recipe input artifact is not a usable image.")
        backend = self._backend(artifact.backend_name)
        if backend.bucket != artifact.bucket:
            raise MediaArtifactStateError(
                "Recipe input artifact bucket does not match the configured backend."
            )
        try:
            stored = backend.head(artifact.object_key)
            if (
                stored is None
                or stored.backend_name != artifact.backend_name
                or stored.bucket != artifact.bucket
                or stored.key != artifact.object_key
                or stored.size_bytes != artifact.size_bytes
                or (stored.sha256 and stored.sha256 != artifact.sha256)
            ):
                raise MediaArtifactStateError(
                    "Recipe input object is missing or its stored fingerprint changed."
                )
            content = backend.read_bytes(artifact.object_key)
        except StorageError as exc:
            raise MediaArtifactStateError("Recipe input object could not be read.") from exc
        if (
            len(content) != artifact.size_bytes
            or hashlib.sha256(content).hexdigest() != artifact.sha256
        ):
            raise MediaArtifactStateError(
                "Recipe input bytes failed integrity verification."
            )
        return artifact, content

    def signed_get_url(
        self,
        public_id: str,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        expires_seconds: int = 300,
        download: bool = False,
        allow_team_scope: bool = False,
    ) -> str:
        artifact = self.require_view_access(
            public_id,
            organization_id=organization_id,
            actor_user_profile_id=actor_user_profile_id,
            allow_team_scope=allow_team_scope,
        )
        if artifact.status not in ACTIVE_MEDIA_STATUSES or artifact.deleted_at is not None:
            raise MediaArtifactStateError("Media artifact is not available for access.")
        ttl = int(expires_seconds)
        if not MIN_SIGNED_URL_TTL_SECONDS <= ttl <= MAX_SIGNED_URL_TTL_SECONDS:
            raise MediaArtifactStateError(
                f"Signed URL lifetime must be {MIN_SIGNED_URL_TTL_SECONDS} to {MAX_SIGNED_URL_TTL_SECONDS} seconds."
            )
        backend = self._backend(artifact.backend_name)
        if backend.bucket != artifact.bucket:
            raise MediaArtifactStateError("Artifact bucket does not match the configured backend.")
        return backend.create_signed_get_url(
            artifact.object_key,
            expires_seconds=ttl,
            download_filename=(artifact.original_filename or f"{artifact.public_id}{self._suffix_for_mime(artifact.mime_type)}")
            if download
            else None,
        )

    def require_view_access(
        self,
        public_id: str,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        allow_team_scope: bool = False,
    ) -> models.MediaArtifact:
        """Resolve an artifact only when the actor may see it in the workspace."""

        membership = self._require_actor(organization_id, actor_user_profile_id)
        if allow_team_scope and str(membership.role).strip().casefold() not in {"owner", "admin"}:
            raise MediaArtifactOwnershipError("Team media access requires an owner or admin role.")
        artifact = self.get_owned(public_id, organization_id=organization_id)
        if not allow_team_scope:
            self._require_personal_or_assigned_access(
                artifact,
                actor_user_profile_id=actor_user_profile_id,
            )
        return artifact

    def list_owned(
        self,
        *,
        organization_id: int,
        product_id: int | None = None,
        created_by_user_profile_id: int | None = None,
        kind: str | None = None,
        include_archived: bool = True,
        limit: int = 100,
        visible_to_user_profile_id: int | None = None,
    ) -> list[models.MediaArtifact]:
        query = select(models.MediaArtifact).where(
            models.MediaArtifact.organization_id == organization_id,
            models.MediaArtifact.deleted_at.is_(None),
        )
        if not include_archived:
            query = query.where(models.MediaArtifact.status == "ready")
        else:
            query = query.where(models.MediaArtifact.status.in_(ACTIVE_MEDIA_STATUSES))
        if product_id is not None:
            query = query.where(models.MediaArtifact.product_id == product_id)
        if created_by_user_profile_id is not None:
            query = query.where(
                models.MediaArtifact.created_by_user_profile_id == created_by_user_profile_id
            )
        if kind is not None:
            query = query.where(models.MediaArtifact.kind == self._kind(kind))
        if visible_to_user_profile_id is not None:
            actor_id = int(visible_to_user_profile_id)
            self._require_actor(organization_id, actor_id)
            assigned_task = exists(
                select(models.CreatorTask.id).where(
                    models.CreatorTask.organization_id == organization_id,
                    models.CreatorTask.assignee_user_profile_id == actor_id,
                    models.CreatorTask.media_artifact_id == models.MediaArtifact.id,
                    models.CreatorTask.status != "cancelled",
                )
            )
            query = query.where(
                or_(
                    models.MediaArtifact.created_by_user_profile_id == actor_id,
                    assigned_task,
                )
            )
        return list(
            self.db.scalars(
                query.order_by(models.MediaArtifact.created_at.desc(), models.MediaArtifact.id.desc()).limit(
                    min(max(int(limit), 1), 200)
                )
            )
        )

    def archive(
        self,
        public_id: str,
        *,
        organization_id: int,
        actor_user_profile_id: int,
        now: datetime | None = None,
    ) -> models.MediaArtifact:
        self._require_actor(organization_id, actor_user_profile_id)
        artifact = self.get_owned(public_id, organization_id=organization_id)
        if artifact.status == "archived":
            return artifact
        if artifact.status != "ready" or artifact.deleted_at is not None:
            raise MediaArtifactStateError("Only a ready artifact can be archived.")
        artifact.status = "archived"
        artifact.archived_at = now or models.utcnow()
        self.db.commit()
        self.db.refresh(artifact)
        return artifact

    def restore(
        self,
        public_id: str,
        *,
        organization_id: int,
        actor_user_profile_id: int,
    ) -> models.MediaArtifact:
        self._require_actor(organization_id, actor_user_profile_id)
        artifact = self.get_owned(public_id, organization_id=organization_id)
        if artifact.status != "archived" or artifact.deleted_at is not None:
            raise MediaArtifactStateError("Only an archived artifact can be restored.")
        artifact.status = "ready"
        artifact.archived_at = None
        self.db.commit()
        self.db.refresh(artifact)
        return artifact

    @classmethod
    def build_object_key(
        cls,
        *,
        organization_id: int,
        public_id: str,
        kind: str,
        original_filename: str | None,
        product_id: int | None = None,
        product_ugc_recipe_draft_id: int | None = None,
        video_job_id: int | None = None,
    ) -> str:
        if int(organization_id) <= 0 or not re.fullmatch(r"[a-f0-9]{32}", public_id):
            raise MediaArtifactError("Invalid tenant object-key identity.")
        for label, value in (
            ("product", product_id),
            ("Product UGC draft", product_ugc_recipe_draft_id),
            ("video job", video_job_id),
        ):
            if value is not None and int(value) <= 0:
                raise MediaArtifactError(f"Invalid {label} id for object key.")
        safe_kind = cls._kind(kind)
        suffix = cls._suffix(original_filename)
        return (
            f"organizations/{int(organization_id):08d}/"
            f"products/{int(product_id) if product_id else 'unassigned'}/"
            f"drafts/{int(product_ugc_recipe_draft_id) if product_ugc_recipe_draft_id else 'unassigned'}/"
            f"videos/{int(video_job_id) if video_job_id else 'unassigned'}/"
            f"{safe_kind}/{public_id}{suffix}"
        )

    def _require_actor(
        self,
        organization_id: int,
        user_profile_id: int,
    ) -> models.Membership:
        organization = self.db.get(models.Organization, organization_id)
        profile = self.db.get(models.UserProfile, user_profile_id)
        membership = self.db.scalar(
            select(models.Membership).where(
                models.Membership.organization_id == organization_id,
                models.Membership.user_profile_id == user_profile_id,
                models.Membership.status == "active",
            )
        )
        if (
            organization is None
            or organization.status != "active"
            or profile is None
            or not profile.is_active
            or profile.status != "active"
            or membership is None
        ):
            raise MediaArtifactOwnershipError("An active organization membership is required.")
        return membership

    def _require_personal_or_assigned_access(
        self,
        artifact: models.MediaArtifact,
        *,
        actor_user_profile_id: int,
    ) -> None:
        actor_id = int(actor_user_profile_id)
        if artifact.created_by_user_profile_id == actor_id:
            return
        assigned = self.db.scalar(
            select(models.CreatorTask.id).where(
                models.CreatorTask.organization_id == artifact.organization_id,
                models.CreatorTask.assignee_user_profile_id == actor_id,
                models.CreatorTask.media_artifact_id == artifact.id,
                models.CreatorTask.status != "cancelled",
            )
        )
        if assigned is None:
            raise MediaArtifactOwnershipError(
                "Media artifact is neither owned by nor assigned to this creator."
            )

    def _require_attributable_actor(self, organization_id: int, user_profile_id: int) -> None:
        """Allow a trusted worker to finish already-authorized provider work."""

        organization = self.db.get(models.Organization, organization_id)
        profile = self.db.get(models.UserProfile, user_profile_id)
        if organization is None or organization.status != "active" or profile is None:
            raise MediaArtifactOwnershipError("Worker media requires an attributable organization user.")

    def _validate_links(
        self,
        *,
        organization_id: int,
        product_id: int | None,
        product_ugc_recipe_draft_id: int | None,
        video_job_id: int | None,
    ) -> None:
        product = self.db.get(models.Product, product_id) if product_id else None
        if product_id and (product is None or product.organization_id != organization_id):
            raise MediaArtifactOwnershipError("Product is outside the organization.")
        draft = (
            self.db.get(models.ProductUGCRecipeDraft, product_ugc_recipe_draft_id)
            if product_ugc_recipe_draft_id
            else None
        )
        if product_ugc_recipe_draft_id:
            if draft is None or draft.product.organization_id != organization_id:
                raise MediaArtifactOwnershipError("Product UGC draft is outside the organization.")
            if product_id and draft.product_id != product_id:
                raise MediaArtifactOwnershipError("Product UGC draft does not belong to the linked product.")
        video_job = self.db.get(models.VideoJob, video_job_id) if video_job_id else None
        if video_job_id:
            if video_job is None or video_job.organization_id != organization_id:
                raise MediaArtifactOwnershipError("Video job is outside the organization.")
            if product_id and video_job.product_id != product_id:
                raise MediaArtifactOwnershipError("Video job does not belong to the linked product.")
            if product_ugc_recipe_draft_id and video_job.source_product_ugc_draft_id != product_ugc_recipe_draft_id:
                raise MediaArtifactOwnershipError("Video job does not belong to the linked Product UGC draft.")

    def _assert_tenant_key(self, artifact: models.MediaArtifact) -> None:
        expected = f"organizations/{int(artifact.organization_id):08d}/"
        if not artifact.object_key.startswith(expected):
            raise MediaArtifactOwnershipError("Artifact object key violates the tenant prefix.")

    def _backend(self, name: str) -> StorageBackend:
        backend = self.backends.get(str(name))
        if backend is None:
            raise MediaArtifactStateError("Storage backend is not configured.")
        return backend

    def _existing_idempotent(
        self,
        organization_id: int,
        idempotency_key: str,
    ) -> models.MediaArtifact | None:
        return self.db.scalar(
            select(models.MediaArtifact).where(
                models.MediaArtifact.organization_id == organization_id,
                models.MediaArtifact.idempotency_key == idempotency_key,
            )
        )

    def _validate_idempotent_artifact(
        self,
        artifact: models.MediaArtifact,
        *,
        backend: StorageBackend,
        kind: str,
        product_id: int | None,
        draft_id: int | None,
        video_job_id: int | None,
    ) -> models.MediaArtifact:
        self._assert_tenant_key(artifact)
        if (
            artifact.backend_name != backend.name
            or artifact.bucket != backend.bucket
            or artifact.kind != kind
            or artifact.product_id != product_id
            or artifact.product_ugc_recipe_draft_id != draft_id
            or artifact.video_job_id != video_job_id
            or artifact.status not in ACTIVE_MEDIA_STATUSES
            or artifact.deleted_at is not None
        ):
            raise MediaArtifactStateError("Media idempotency key belongs to another artifact scope.")
        stored = backend.head(artifact.object_key)
        if (
            stored is None
            or stored.size_bytes != artifact.size_bytes
            or (stored.sha256 and stored.sha256 != artifact.sha256)
        ):
            raise MediaArtifactStateError("Idempotent media object is missing or changed.")
        if not stored.sha256:
            try:
                content = backend.read_bytes(artifact.object_key)
            except StorageError as exc:
                raise MediaArtifactStateError(
                    "Idempotent media object could not be verified."
                ) from exc
            if (
                len(content) != artifact.size_bytes
                or hashlib.sha256(content).hexdigest() != artifact.sha256
            ):
                raise MediaArtifactStateError("Idempotent media object is missing or changed.")
        return artifact

    @staticmethod
    def _kind(value: str) -> str:
        kind = str(value or "").strip().lower()
        if kind not in ARTIFACT_KINDS:
            raise MediaArtifactError("Unsupported media artifact kind.")
        return kind

    @staticmethod
    def _mime_type(value: str) -> str:
        mime = str(value or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*", mime):
            raise MediaArtifactError("A valid MIME type is required.")
        return mime[:160]

    @staticmethod
    def _retention_class(value: str) -> str:
        normalized = str(value or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", normalized):
            raise MediaArtifactError("Invalid retention class.")
        return normalized

    @staticmethod
    def _idempotency_key(value: str) -> str:
        key = str(value or "").strip()
        if not key or len(key) > 200 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", key):
            raise MediaArtifactError("A stable non-secret media idempotency key is required.")
        return key

    @staticmethod
    def _file_fingerprint(path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    @staticmethod
    def _safe_metadata(value: dict | None) -> dict:
        metadata = dict(value or {})
        forbidden = ("signed_url", "token", "secret", "password", "authorization", "cookie")

        def contains_capability(item) -> bool:
            if isinstance(item, dict):
                return any(
                    any(part in str(key).lower() for part in forbidden)
                    or contains_capability(child)
                    for key, child in item.items()
                )
            if isinstance(item, (list, tuple, set)):
                return any(contains_capability(child) for child in item)
            if isinstance(item, str):
                lowered = item.lower()
                return bool(
                    re.search(
                        r"https?://[^\s]+[?&](?:x-amz-signature|signature|token|access_token)=",
                        lowered,
                    )
                    or lowered.startswith("bearer ")
                )
            return False

        if contains_capability(metadata):
            raise MediaArtifactError("Artifact metadata must not contain credentials or signed URLs.")
        return metadata

    @staticmethod
    def _original_filename(value: str | None) -> str | None:
        if not value:
            return None
        name = Path(value).name.replace("\r", "").replace("\n", "")[:255]
        return name or None

    @staticmethod
    def _suffix(filename: str | None) -> str:
        suffix = Path(filename or "").suffix.lower()
        return suffix if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix) else ""

    @staticmethod
    def _suffix_for_mime(mime_type: str) -> str:
        return mimetypes.guess_extension(mime_type) or ""
