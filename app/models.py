# app/models.py
import os
from datetime import datetime, date
from enum import Enum
from flask import current_app
from werkzeug.utils import secure_filename
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db

from sqlalchemy.orm import validates, relationship, backref
from sqlalchemy import (
    CheckConstraint,
    UniqueConstraint,
    Column,
    Integer,
    String,
    ForeignKey,
    DateTime,
    Date,
    Boolean,
    Enum as SAEnum,   # alias to avoid clashing with Python's Enum
    text,
    event,
    func,
    Text
)



role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


# --- NEW Permission model ---
class Permission(db.Model):
    __tablename__ = "permissions"
    id   = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(128), unique=True, nullable=False, index=True)  # e.g. "users.view"
    name = db.Column(db.String(256), nullable=False)                           # display name

    def __repr__(self):
        return f"<Permission {self.code}>"
# -------------------------
# Roles
# -------------------------
class Role(db.Model):
    __tablename__ = "roles"

    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # users that belong to this role
    users = db.relationship("User", backref="role", lazy="dynamic")

    # NEW: many-to-many to Permission
    permissions = db.relationship(
        "Permission",
        secondary=role_permissions,
        lazy="selectin",  # eager-ish, avoids N+1
        backref=db.backref("roles", lazy="selectin"),
    )

    def __repr__(self) -> str:
        return f"<Role {self.name}>"

# -------------------------
# Departments
# -------------------------
class Department(db.Model):
    __tablename__ = "departments"
    __table_args__ = (db.UniqueConstraint("name", name="uq_departments_name"),)

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False, index=True)

    # Director/Manager (single source of truth for privileges)
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    manager = db.relationship(
        "User",
        foreign_keys=[manager_id],
        backref=db.backref("managed_departments", lazy="dynamic"),
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<Department {self.name} (manager_id={self.manager_id})>"


# -------------------------
# Users
# -------------------------
class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # Profile
    first_name   = db.Column(db.String(80), nullable=False)
    last_name    = db.Column(db.String(80), nullable=False)

    # Legacy free-text department (display only; real membership via department_id)
    department   = db.Column(db.String(120))

    # Contact / identifiers
    email        = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(40))
    id_number    = db.Column(db.String(64), unique=True, nullable=False, index=True)
    embg         = db.Column(db.String(32), unique=True, index=True)
    bank_account = db.Column(db.String(64))    # Трансакциска сметка
    city         = db.Column(db.String(120))   # Град
    address      = db.Column(db.String(255))   # Адреса на живеење
    # PTO allocation (business days)
    vacation_days = db.Column(db.Integer, nullable=False, default=0, server_default=text("0"))

    # Auth
    username      = db.Column(db.String(80), unique=True, index=True)
    password_hash = db.Column(db.String(255))

    # Role (optional)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"))

    # Department membership (optional)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), index=True)
    dept = db.relationship(
        "Department",
        foreign_keys=[department_id],
        backref=db.backref("members", lazy="dynamic"),
    )
    avatar_url = Column(String(512), nullable=True)
    avatar_updated_at = Column(DateTime, nullable=True)  # optional, handy for cache-busting
    
    # Status & timestamps
    is_active    = db.Column(db.Boolean, nullable=False, server_default=text("1"))
    is_suspended = db.Column(db.Boolean, nullable=False, server_default=text("0"))
    created_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_admin    = db.Column(db.Boolean, nullable=False, server_default=text("0"))
    # ---- auth helpers ----
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return bool(self.password_hash) and check_password_hash(self.password_hash, raw_password)

    # ---- convenience ----
    @property
    def full_name(self) -> str:
        fn = (self.first_name or "").strip()
        ln = (self.last_name or "").strip()
        full = f"{fn} {ln}".strip()
        return full or (self.username or self.email)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.full_name}>"


# ---- normalization: always store email lowercase ----
@event.listens_for(User, "before_insert")
def _user_email_lower_insert(mapper, connection, target):
    if target.email:
        target.email = target.email.strip().lower()

@event.listens_for(User, "before_update")
def _user_email_lower_update(mapper, connection, target):
    if target.email:
        target.email = target.email.strip().lower()


# -------------------------
# Agreements (employment contracts)
# -------------------------
class Agreement(db.Model):
    __tablename__ = "agreements"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    start_date = db.Column(db.Date, nullable=False)
    months = db.Column(db.Integer, nullable=False, default=1)
    end_date = db.Column(db.Date, nullable=False)

    # status: 'active' | 'cancelled' | 'expired'
    status = db.Column(
        db.String(16),
        nullable=False,
        default="active",
        index=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    user = db.relationship(
        "User",
        backref=db.backref("agreements", lazy="dynamic"),
    )

    attachments = db.relationship(
        "Attachment",
        back_populates="agreement",
        lazy="selectin",
        cascade="all, delete-orphan",
        foreign_keys="Attachment.agreement_id"
    )
    def __repr__(self) -> str:
        return (
            f"<Agreement id={self.id} user_id={self.user_id} "
            f"{self.start_date}→{self.end_date} status={self.status}>"
        )


# -------------------------
# Vacation (time off — Mon–Fri business days)
# -------------------------
class Vacation(db.Model):
    __tablename__ = "vacations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Dates
    start_date  = db.Column(db.Date, nullable=False)
    days        = db.Column(db.Integer, nullable=False, default=1)   # business days (Mon–Fri)
    end_date    = db.Column(db.Date, nullable=False)                 # last off business day
    return_date = db.Column(db.Date, nullable=False)                 # first working day after

    holidays_csv = db.Column(db.Text, nullable=True)                 # comma-separated YYYY-MM-DD excluded from count

    # status: 'active' | 'completed' | 'cancelled'
    status = db.Column(db.String(16), nullable=False, default="active", index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relations
    user = db.relationship("User", backref=db.backref("vacations", lazy="dynamic"))

    # Attachments
    attachments = db.relationship(
        "Attachment",
        back_populates="vacation",
        lazy="selectin",
        cascade="all, delete-orphan",
        foreign_keys="Attachment.vacation_id",
    )

    # ---- Optional hardening: coerce incoming date-like values ----
    @staticmethod
    def _coerce_date(val):
        if val is None:
            return None
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            return datetime.strptime(val.strip(), "%Y-%m-%d").date()
        raise ValueError("Unsupported date value for Date column.")

    @validates("start_date", "end_date", "return_date")
    def _validate_dates(self, key, val):
        return self._coerce_date(val)

    def __repr__(self) -> str:
        return f"<Vacation id={self.id} user_id={self.user_id} {self.start_date}+{self.days}={self.end_date} {self.status}>"


# -------------------------
# Sick Leave
# -------------------------
class SickLeave(db.Model):
    __tablename__ = "sick_leaves"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    start_date = db.Column(db.Date, nullable=False)
    end_date   = db.Column(db.Date, nullable=False)

    # Dropdown values: "Терет на фирма", "Терет на фонд", "Породилно", "100% повреда на работа"
    kind = db.Column(db.String(64), nullable=False, index=True)

    # Business-day counter (Mon–Fri) computed when created/updated
    business_days = db.Column(db.Integer, nullable=False, default=0)

    # Excluded holiday dates (comma-separated YYYY-MM-DD)
    holidays_csv = db.Column(db.Text, nullable=True)

    comments = db.Column(db.Text, nullable=True)

    # status: 'active' (today <= end_date) | 'history' (auto after end) | 'cancelled'
    status = db.Column(db.String(16), nullable=False, default="active", index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship("User", backref=db.backref("sick_leaves", lazy="dynamic"))

    attachments = db.relationship(
        "Attachment",
        back_populates="sick_leave",
        lazy="selectin",
        cascade="all, delete-orphan",
        foreign_keys="Attachment.sick_leave_id",
    )

    def __repr__(self) -> str:
        return (
            f"<SickLeave id={self.id} user_id={self.user_id} "
            f"{self.start_date}→{self.end_date} {self.kind} {self.status}>"
        )


# -------------------------
# Reports (Извештај)
# -------------------------
class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)

    sanitary_last = db.Column(db.Date, nullable=True)   # Санитарен преглед — last date
    system_last   = db.Column(db.Date, nullable=True)   # Систематски преглед — last date

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("report", uselist=False))

    def __repr__(self) -> str:
        return f"<Report user_id={self.user_id} sanitary_last={self.sanitary_last} system_last={self.system_last}>"


# -------------------------
# Uniforms (Униформи)
# -------------------------
class Uniform(db.Model):
    __tablename__ = "uniforms"

    id                  = db.Column(db.Integer, primary_key=True)
    user_id             = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    kind                = db.Column(db.String(200), nullable=False)
    assigned_date       = db.Column(db.Date, nullable=False)
    renew_every_months  = db.Column(db.Integer, nullable=False, default=12)
    next_due_date       = db.Column(db.Date, nullable=False)

    # Persist state so it can appear under Active/History
    status              = db.Column(db.String(16), nullable=False, default="active", index=True)

    created_at          = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("uniforms", lazy="dynamic"))

    attachments = db.relationship(
        "Attachment",
        back_populates="uniform",
        lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Uniform id={self.id} user_id={self.user_id} kind={self.kind} next_due={self.next_due_date} status={self.status}>"


# -------------------------
# Trainings (Обука)
# -------------------------
class Training(db.Model):
    __tablename__ = "trainings"

    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    title      = db.Column(db.String(200), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date   = db.Column(db.Date, nullable=False)

    # status: 'active' | 'history' (auto after end) | 'cancelled'
    status     = db.Column(db.String(16), nullable=False, default="active", index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Attachments linked via Attachment.training_id
    attachments = db.relationship("Attachment", back_populates="training", lazy="dynamic")

    user = db.relationship("User", backref=db.backref("trainings", lazy="dynamic"))

    def __repr__(self) -> str:
        return f"<Training id={self.id} user_id={self.user_id} {self.start_date}→{self.end_date} {self.status}>"


# -------------------------
# Rewards & Penalties (Казни и Награди)
# -------------------------
class RewardPenalty(db.Model):
    __tablename__ = "reward_penalties"

    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # "reward" | "penalty"
    type     = db.Column(db.String(16), nullable=False, index=True)

    note     = db.Column(db.Text, nullable=True)
    date     = db.Column(db.Date, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship("User", backref=db.backref("reward_penalties", lazy="dynamic"))

    attachments = db.relationship(
        "Attachment",
        back_populates="reward_penalty",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="Attachment.reward_penalty_id",
    )

    @validates("type")
    def _validate_type(self, key, value):
        v = (value or "").strip().lower()
        if v not in {"reward", "penalty"}:
            raise ValueError("RewardPenalty.type must be 'reward' or 'penalty'.")
        return v

    def __repr__(self) -> str:
        return f"<RewardPenalty id={self.id} user_id={self.user_id} type={self.type} date={self.date}>"


# -------------------------
# Attachments
# -------------------------
class Attachment(db.Model):
    __tablename__ = "attachments"

    id       = db.Column(db.Integer, primary_key=True)
    user_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # Linkable owners (only ONE should be non-null per row)
    agreement_id      = db.Column(db.Integer, db.ForeignKey("agreements.id",       ondelete="CASCADE"), nullable=True, index=True)
    sick_leave_id     = db.Column(db.Integer, db.ForeignKey("sick_leaves.id",      ondelete="CASCADE"), nullable=True, index=True)
    vacation_id       = db.Column(db.Integer, db.ForeignKey("vacations.id",        ondelete="CASCADE"), nullable=True, index=True)
    uniform_id        = db.Column(db.Integer, db.ForeignKey("uniforms.id",         ondelete="CASCADE"), nullable=True, index=True)
    training_id       = db.Column(db.Integer, db.ForeignKey("trainings.id",        ondelete="CASCADE"), nullable=True, index=True)
    reward_penalty_id = db.Column(db.Integer, db.ForeignKey("reward_penalties.id", ondelete="CASCADE"), nullable=True, index=True)

    # File metadata
    filename     = db.Column(db.String(255), nullable=False)               # original (display) name
    stored_name  = db.Column(db.String(255), nullable=False, unique=True)  # safe name on disk
    content_type = db.Column(db.String(128), nullable=True)
    uploaded_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "("
            " (CASE WHEN agreement_id      IS NOT NULL THEN 1 ELSE 0 END)"
            "+(CASE WHEN sick_leave_id     IS NOT NULL THEN 1 ELSE 0 END)"
            "+(CASE WHEN vacation_id       IS NOT NULL THEN 1 ELSE 0 END)"
            "+(CASE WHEN uniform_id        IS NOT NULL THEN 1 ELSE 0 END)"
            "+(CASE WHEN training_id       IS NOT NULL THEN 1 ELSE 0 END)"
            "+(CASE WHEN reward_penalty_id IS NOT NULL THEN 1 ELSE 0 END)"
            ") <= 1",
            name="ck_attachment_single_owner",
        ),
    )

    # Relationships
    user           = db.relationship("User", backref=db.backref("attachments", lazy="dynamic"))
    agreement      = db.relationship("Agreement",     back_populates="attachments", foreign_keys=[agreement_id])
    sick_leave     = db.relationship("SickLeave",     back_populates="attachments", foreign_keys=[sick_leave_id])
    vacation       = db.relationship("Vacation",      back_populates="attachments", foreign_keys=[vacation_id])
    uniform        = db.relationship("Uniform",       back_populates="attachments", foreign_keys=[uniform_id])
    training       = db.relationship("Training",      back_populates="attachments", foreign_keys=[training_id])
    reward_penalty = db.relationship("RewardPenalty", back_populates="attachments", foreign_keys=[reward_penalty_id])

    @validates(
        "agreement_id", "sick_leave_id", "vacation_id",
        "uniform_id", "training_id", "reward_penalty_id",
    )
    def _validate_single_owner(self, key, value):
        owners = {
            "agreement_id":      getattr(self, "agreement_id", None),
            "sick_leave_id":     getattr(self, "sick_leave_id", None),
            "vacation_id":       getattr(self, "vacation_id", None),
            "uniform_id":        getattr(self, "uniform_id", None),
            "training_id":       getattr(self, "training_id", None),
            "reward_penalty_id": getattr(self, "reward_penalty_id", None),
        }
        owners[key] = value
        if sum(1 for v in owners.values() if v is not None) > 1:
            raise ValueError("Attachment can be linked to only one owner entity.")
        return value

    def __repr__(self) -> str:
        owner = (
            ("agr=" + str(self.agreement_id))       if self.agreement_id      is not None else
            ("sl="  + str(self.sick_leave_id))      if self.sick_leave_id     is not None else
            ("vac=" + str(self.vacation_id))        if self.vacation_id       is not None else
            ("uni=" + str(self.uniform_id))         if self.uniform_id        is not None else
            ("trn=" + str(self.training_id))        if self.training_id       is not None else
            ("rwp=" + str(self.reward_penalty_id))  if self.reward_penalty_id is not None else
            "no-owner"
        )
        return f"<Attachment id={self.id} user={self.user_id} {owner} {self.filename}>"

    # ---------- Helper: save upload to disk + DB ----------
    @classmethod
    def save_upload(cls, file_storage, user_id, **owner_kwargs):
        """
        Save a Werkzeug FileStorage to disk and create an Attachment row.

        Uses ATTACHMENTS_DIR (if set), otherwise instance/uploads.
        Sets .stored_name to the on-disk filename.
        """
        if not file_storage or not getattr(file_storage, "filename", ""):
            return None

        # Single source of truth for disk path
        upload_root = current_app.config.get("ATTACHMENTS_DIR")
        if not upload_root:
            upload_root = os.path.join(current_app.instance_path, "uploads")
        os.makedirs(upload_root, exist_ok=True)

        # Unique, safe name
        original = secure_filename(file_storage.filename or "")
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        stored = f"{ts}_{original}" if original else ts

        # Save
        abs_path = os.path.join(upload_root, stored)
        file_storage.save(abs_path)

        # Create row
        att = cls(
            user_id=user_id,
            filename=original or stored,
            stored_name=stored,
            content_type=getattr(file_storage, "mimetype", None),
            uploaded_at=datetime.utcnow(),
            **{k: v for k, v in owner_kwargs.items() if k in {
                "agreement_id", "sick_leave_id", "vacation_id",
                "uniform_id", "training_id", "reward_penalty_id",
            } and v is not None}
        )
        db.session.add(att)
        db.session.flush()
        return att


# --- DRIVE MODELS START ---
class DrivePermission(str, Enum):
    read = "read"
    write = "write"
    full = "full"

class DriveFolder(db.Model):
    __tablename__ = "drive_folders"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    parent_id = Column(Integer, ForeignKey("drive_folders.id", ondelete="CASCADE"), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    parent = relationship("DriveFolder", remote_side=[id], backref="children")
    owner = relationship("User")

    def to_dict(self, current_user_id=None, shared=False):
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "owner_id": self.owner_id,
            "shared": bool(shared and self.owner_id != current_user_id),
        }

class DriveFile(db.Model):
    __tablename__ = "drive_files"
    id = Column(Integer, primary_key=True)
    original_name = Column(String(512), nullable=False)
    stored_name = Column(String(512), nullable=True)
    mimetype = Column(String(255), nullable=True)
    size = Column(Integer, nullable=True)

    folder_id = Column(Integer, ForeignKey("drive_folders.id", ondelete="SET NULL"), nullable=True)
    uploader_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    folder = relationship("DriveFolder", backref="files")
    uploader = relationship("User")

    def to_dict(self, current_user_id=None, shared=False):
        return {
            "id": self.id,
            "original_name": self.original_name,
            "mimetype": self.mimetype,
            "size": self.size,
            "folder_id": self.folder_id,
            "uploader_id": self.uploader_id,
            "uploaded_at": (self.uploaded_at.isoformat() if self.uploaded_at else None),
            "shared": bool(shared and self.uploader_id != current_user_id),
        }

class DriveACL(db.Model):
    """
    Generic ACL row: grants a permission to user for either a folder or a file.
    """
    __tablename__ = "drive_acl"
    id = Column(Integer, primary_key=True)

    target_type = Column(String(8), nullable=False)  # 'folder' | 'file'
    target_id = Column(Integer, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission = Column(SAEnum(DrivePermission, name="drive_permission"), nullable=False, default=DrivePermission.read)

    inherited = Column(Boolean, default=False)  # created by parent-folder propagation
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("target_type", "target_id", "user_id", name="uq_acl_target_user"),
    )
# --- DRIVE MODELS END ---


# =========================
# NOTES / WORK LOG MODELS
# =========================
class TaskCategory(db.Model):
    """
    Per-department quick-pick task categories for Notes.
    """
    __tablename__ = "task_categories"

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=text("1"))

    department = db.relationship("Department", backref=db.backref("task_categories", lazy="dynamic"))

    __table_args__ = (
        UniqueConstraint("department_id", "name", name="uq_taskcategory_department_name"),
    )

    def __repr__(self) -> str:
        return f"<TaskCategory id={self.id} dept={self.department_id} {self.name} active={self.is_active}>"


class WorkLogEntry(db.Model):
    """
    A time block (per user, per local day). Times stored in UTC; UI shows Europe/Skopje.
    Single open block rule: end_time_utc is NULL only for one active block/user.
    status: 'draft' -> 'locked'
    source: 'manual' | 'correction'
    """
    __tablename__ = "work_log_entries"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True)

    # Logical local date (Europe/Skopje) the entry belongs to, even though times are UTC
    work_date = db.Column(db.Date, nullable=False, index=True)

    start_time_utc = db.Column(db.DateTime, nullable=False, index=True)
    end_time_utc   = db.Column(db.DateTime, nullable=True, index=True)  # NULL while active

    task_category_id = db.Column(db.Integer, db.ForeignKey("task_categories.id"), nullable=True)
    note = db.Column(db.Text)

    # cached minutes (computed on close/lock); while open it's best-effort
    minutes = db.Column(db.Integer, nullable=False, default=0, server_default=text("0"))

    # 'draft' or 'locked'
    status = db.Column(db.String(16), nullable=False, default="draft", server_default=text("'draft'"), index=True)
    # 'manual' or 'correction'
    source = db.Column(db.String(16), nullable=False, default="manual", server_default=text("'manual'"), index=True)

    # lightweight real-time signal
    last_heartbeat_utc = db.Column(db.DateTime, nullable=True, index=True)

    user = db.relationship("User", backref=db.backref("work_logs", lazy="dynamic"))
    department = db.relationship("Department")
    category = db.relationship("TaskCategory")

    __table_args__ = (
        CheckConstraint("status in ('draft','locked')", name="ck_worklog_status"),
        CheckConstraint("source in ('manual','correction')", name="ck_worklog_source"),
        # Helpful for queries that expect “at most one open block per user”
        db.Index("ix_worklog_user_open", "user_id", "end_time_utc"),
    )

    def __repr__(self) -> str:
        return f"<WorkLogEntry id={self.id} user={self.user_id} date={self.work_date} status={self.status}>"


class WorkLogCorrection(db.Model):
    """
    Directors (department managers) add corrections to locked days with a reason.
    Represented both as a correction row and (optionally) as a synthetic locked entry.
    """
    __tablename__ = "work_log_corrections"

    id = db.Column(db.Integer, primary_key=True)

    director_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    user_id       = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False, index=True)

    work_date       = db.Column(db.Date, nullable=False, index=True)
    task_category_id = db.Column(db.Integer, db.ForeignKey("task_categories.id"), nullable=True)

    minutes_delta = db.Column(db.Integer, nullable=False)  # positive or negative
    reason = db.Column(db.Text, nullable=False)

    created_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    director   = db.relationship("User", foreign_keys=[director_id])
    user       = db.relationship("User", foreign_keys=[user_id])
    department = db.relationship("Department")
    category   = db.relationship("TaskCategory")

    def __repr__(self) -> str:
        return f"<WorkLogCorrection id={self.id} dept={self.department_id} user={self.user_id} delta={self.minutes_delta}>"


# plan and realization

class TaskStatus(str, Enum):
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    COMPLETED = "completed"
    DENIED = "denied"
    RETURNED = "returned"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PlanTask(db.Model):
    __tablename__ = "plan_tasks"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)  # assignee
    director_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)   # creator/reviewer
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)

    start_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)

    status = Column(SAEnum(TaskStatus), nullable=False, default=TaskStatus.ASSIGNED)
    priority = Column(SAEnum(TaskPriority), nullable=True)

    deleted_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", foreign_keys=[owner_user_id], backref=backref("plan_tasks_owned", lazy="dynamic"))
    director = relationship("User", foreign_keys=[director_id], backref=backref("plan_tasks_directed", lazy="dynamic"))
    department = relationship("Department", backref=backref("plan_tasks", lazy="dynamic"))

    comments = relationship("PlanComment", back_populates="task", cascade="all, delete-orphan", lazy="dynamic")
    activities = relationship("PlanActivity", back_populates="task", cascade="all, delete-orphan", lazy="dynamic")
    attachments = relationship("Attachment", secondary="plan_task_attachments", lazy="dynamic")

    def soft_delete(self, actor_id: int):
        if self.deleted_at:
            return
        self.deleted_at = datetime.utcnow()
        self.activities.append(PlanActivity.make(self.id, actor_id, "delete", {"deleted_at": True}))

    def restore(self, actor_id: int):
        if not self.deleted_at:
            return
        self.deleted_at = None
        self.activities.append(PlanActivity.make(self.id, actor_id, "restore", {"deleted_at": False}))


class PlanTaskAttachment(db.Model):
    __tablename__ = "plan_task_attachments"
    task_id = Column(Integer, ForeignKey("plan_tasks.id"), primary_key=True)
    attachment_id = Column(Integer, ForeignKey("attachments.id"), primary_key=True)


class PlanComment(db.Model):
    __tablename__ = "plan_comments"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("plan_tasks.id"), index=True, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    text = Column(Text, nullable=True)
    is_system = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    task = relationship("PlanTask", back_populates="comments")
    author = relationship("User")

    # Optional: link comment to attachments via generic Attachment model
    attachments = relationship("Attachment", secondary="plan_comment_attachments", lazy="dynamic")


class PlanCommentAttachment(db.Model):
    __tablename__ = "plan_comment_attachments"
    comment_id = Column(Integer, ForeignKey("plan_comments.id"), primary_key=True)
    attachment_id = Column(Integer, ForeignKey("attachments.id"), primary_key=True)


class PlanActivity(db.Model):
    __tablename__ = "plan_activities"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("plan_tasks.id"), index=True, nullable=False)
    actor_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    action = Column(String(64), nullable=False)  # create, assign, reschedule, start, submit, approve, deny, delete, restore, etc.
    payload = Column(Text)                       # JSON string (old->new, notes, etc.)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    task = relationship("PlanTask", back_populates="activities")
    actor = relationship("User")

    @staticmethod
    def make(task_id: int, actor_id: int, action: str, payload_dict=None):
        import json
        return PlanActivity(
            task_id=task_id,
            actor_id=actor_id,
            action=action,
            payload=(json.dumps(payload_dict or {})),
        )




# -------------------------
# Simple permission bindings
# -------------------------




# app/models.py
class DepartmentPermission(db.Model):
    __tablename__ = "department_permissions"
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = db.Column(db.String(128), nullable=False, index=True)  # <-- NOT 'code'
    allowed = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.UniqueConstraint("department_id", "permission", name="uq_department_permission"),
        db.Index("ix_department_permissions_permission", "permission"),
    )



class AgreementTemplate(db.Model):
    __tablename__ = "agreement_templates"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    # "text" stores template body in DB; "docx" stores a file on disk
    type = db.Column(db.Enum("text", "docx", name="agreement_template_type"), nullable=False, default="text")

    # For type="text"
    body = db.Column(db.Text, nullable=True)

    # For type="docx"
    file_path = db.Column(db.String(512), nullable=True)         # stored filename on disk
    content_filename = db.Column(db.String(255), nullable=True)  # original uploaded name

    # Audit
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
