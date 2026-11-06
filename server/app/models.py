"""The nine tables of the data model, as SQLAlchemy declarative models (P1-01).

The field-by-field dictionary in docs/data-model-en.md §3 is the source of truth;
every column here is transcribed from it, in dictionary order. Types follow §2:
snake_case tables, <entity>_id primary keys, BIGINT / TIMESTAMP / SMALLINT 0-1
booleans, SMALLINT enum codes (never a database ENUM), NUMERIC for ratios and
coordinates, and lowercase column names throughout.

Timestamps are naive and always UTC; the application writes UTC, never local.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

# SQLite (tests, dev default) has no BIGINT autoincrement primary key: only a plain
# INTEGER PRIMARY KEY is a rowid alias and auto-generates. PostgreSQL (production)
# gets BIGINT. Same logical type, rendered per dialect.
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")


class SysUser(Base):
    """Accounts, roles, login state (data model §3.1)."""

    __tablename__ = "sys_user"

    user_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    salt: Mapped[str] = mapped_column(String(32))
    role_code: Mapped[str] = mapped_column(String(16))  # observer / analyst / algo / admin
    real_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[int] = mapped_column(SmallInteger, server_default="1")  # 1 active, 0 disabled
    fail_count: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SysLog(Base):
    """Append-only audit trail (data model §3.2). Never updated or deleted in place."""

    __tablename__ = "sys_log"
    __table_args__ = (Index("ix_sys_log_created_at", "created_at"),)

    log_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.user_id"), index=True
    )  # NULL for automated actions
    module: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32))  # login / review / deploy / config
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    before_value: Mapped[str | None] = mapped_column(Text)  # JSON
    after_value: Mapped[str | None] = mapped_column(Text)  # JSON
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MediaAsset(Base):
    """One captured frame and its metadata (data model §3.3)."""

    __tablename__ = "media_asset"
    __table_args__ = (
        Index("ix_media_asset_session_captured", "session_id", "captured_at"),
        Index("ix_media_asset_captured_at", "captured_at"),
        Index("ix_media_asset_file_hash", "file_hash"),
    )

    asset_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    frame_id: Mapped[str] = mapped_column(String(32), unique=True)  # YYYYMMDDTHHMMSS-mmmm
    session_id: Mapped[str] = mapped_column(String(32))
    point_code: Mapped[str] = mapped_column(String(32))
    file_path: Mapped[str] = mapped_column(String(512))  # relative to data/
    thumb_path: Mapped[str | None] = mapped_column(String(512))
    file_size: Mapped[int] = mapped_column(BigInteger)  # bytes
    file_hash: Mapped[str] = mapped_column(CHAR(64))  # SHA-256, for dedup
    captured_at: Mapped[datetime] = mapped_column(DateTime)  # UTC, millisecond precision
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    exposure_us: Mapped[int | None] = mapped_column(Integer)
    gain_db: Mapped[float | None] = mapped_column(Numeric(5, 2))
    quality_score: Mapped[int] = mapped_column(SmallInteger, server_default="0")  # 0-100
    quality_flag: Mapped[int] = mapped_column(SmallInteger, server_default="0")  # 0 ok, 1 retake
    is_retake: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    turbidity_rel: Mapped[int | None] = mapped_column(SmallInteger)  # NULL without sensor
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DetectTask(Base):
    """One detection run: model, parameters, progress (data model §3.4)."""

    __tablename__ = "detect_task"

    task_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    task_code: Mapped[str] = mapped_column(String(32), unique=True)  # DTyyMMdd-serial
    task_type: Mapped[int] = mapped_column(SmallInteger)  # 1 live, 2 batch
    model_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("model_version.model_id"), index=True
    )
    asset_count: Mapped[int] = mapped_column(Integer)
    conf_thr: Mapped[float] = mapped_column(Numeric(4, 2), server_default="0.50")
    iou_thr: Mapped[float] = mapped_column(Numeric(4, 2), server_default="0.45")
    max_det: Mapped[int] = mapped_column(Integer, server_default="100")
    # The one documented exception to the no-lists rule: a JSON array such as
    # ["holothurian","chlamys"], NULL meaning all classes (data model §2).
    class_filter: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[int] = mapped_column(
        SmallInteger, server_default="0"
    )  # 0 queued / 1 running / 2 done / 3 failed / 4 cancelled
    progress: Mapped[int] = mapped_column(SmallInteger, server_default="0")  # percent
    obj_count: Mapped[int] = mapped_column(Integer, server_default="0")
    error_msg: Mapped[str | None] = mapped_column(String(512))
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.user_id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class DetectObject(Base):
    """One detection box (data model §3.5)."""

    __tablename__ = "detect_object"
    __table_args__ = (
        Index("ix_detect_object_frame_id", "frame_id"),
        Index("ix_detect_object_task_class", "task_id", "class_code"),
        Index("ix_detect_object_review_status", "review_status"),
    )

    object_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("detect_task.task_id"), index=True)
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("media_asset.asset_id"), index=True
    )
    frame_id: Mapped[str] = mapped_column(String(32))  # denormalised for fast lookup
    class_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("species_dict.class_code"), index=True
    )
    confidence: Mapped[float] = mapped_column(Numeric(5, 4))  # 0-1
    x: Mapped[float] = mapped_column(Numeric(8, 5))  # normalised box, left edge
    y: Mapped[float] = mapped_column(Numeric(8, 5))  # top edge
    w: Mapped[float] = mapped_column(Numeric(8, 5))  # width
    h: Mapped[float] = mapped_column(Numeric(8, 5))  # height
    track_id: Mapped[int | None] = mapped_column(BigInteger)
    is_manual: Mapped[int] = mapped_column(SmallInteger, server_default="0")  # 0 auto, 1 drawn
    review_status: Mapped[int] = mapped_column(
        SmallInteger, server_default="0"
    )  # 0 pending / 1 confirmed / 2 modified / 3 rejected
    version_no: Mapped[int] = mapped_column(Integer, server_default="1")  # +1 per review
    hard_flag: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    hard_reason: Mapped[str | None] = mapped_column(
        String(32)
    )  # low_conf / modified / inconsistent
    reviewed_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.user_id"), index=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SpeciesDict(Base):
    """Class definitions and per-class thresholds (data model §3.6).

    class_code order is a contract: it must match labels.txt of the model,
    exactly and in order (data model §3.6, in bold).
    """

    __tablename__ = "species_dict"

    species_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    class_code: Mapped[str] = mapped_column(String(32), unique=True)
    cn_name: Mapped[str] = mapped_column(String(32))
    latin_name: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[int] = mapped_column(SmallInteger)  # 1 economic / 2 pest / 3 environment
    conf_thr: Mapped[float] = mapped_column(Numeric(4, 2), server_default="0.50")
    in_stat: Mapped[int] = mapped_column(SmallInteger, server_default="1")
    status: Mapped[int] = mapped_column(SmallInteger, server_default="1")  # 1 active, 0 disabled
    remark: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ModelVersion(Base):
    """Weight file, metrics, online state (data model §3.7)."""

    __tablename__ = "model_version"

    model_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    version_name: Mapped[str] = mapped_column(String(64), unique=True)  # v8n-E3-001
    weight_path: Mapped[str] = mapped_column(String(512))
    onnx_path: Mapped[str | None] = mapped_column(String(512))
    labels_path: Mapped[str] = mapped_column(String(512))
    dataset_ref: Mapped[str | None] = mapped_column(String(128))
    map50: Mapped[float | None] = mapped_column(Numeric(5, 4))
    map50_95: Mapped[float | None] = mapped_column(Numeric(5, 4))
    recall_avg: Mapped[float | None] = mapped_column(Numeric(5, 4))
    fps: Mapped[float | None] = mapped_column(Numeric(6, 2))
    params_m: Mapped[float | None] = mapped_column(Numeric(6, 2))
    status: Mapped[int] = mapped_column(
        SmallInteger, server_default="0"
    )  # 0 cand / 1 online / 2 off
    is_online: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TrainExperiment(Base):
    """Dataset snapshot, hyper-parameters, metrics (data model §3.8)."""

    __tablename__ = "train_experiment"

    exp_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    exp_name: Mapped[str] = mapped_column(String(64))  # e.g. E3
    model_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("model_version.model_id"), index=True
    )
    dataset_snapshot: Mapped[str] = mapped_column(String(128))
    split_ratio: Mapped[str] = mapped_column(String(16))  # e.g. 7:2:1
    seed: Mapped[int] = mapped_column(Integer)
    epochs: Mapped[int] = mapped_column(Integer)
    batch_size: Mapped[int] = mapped_column(Integer)
    lr: Mapped[float] = mapped_column(Numeric(8, 6))
    augment_json: Mapped[str | None] = mapped_column(Text)
    map50: Mapped[float | None] = mapped_column(Numeric(5, 4))
    map50_95: Mapped[float | None] = mapped_column(Numeric(5, 4))
    recall_avg: Mapped[float | None] = mapped_column(Numeric(5, 4))
    fps: Mapped[float | None] = mapped_column(Numeric(6, 2))
    params_m: Mapped[float | None] = mapped_column(Numeric(6, 2))
    is_baseline: Mapped[int] = mapped_column(SmallInteger, server_default="0")
    note: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SysMessage(Base):
    """In-app notifications (data model §3.9)."""

    __tablename__ = "sys_message"

    msg_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    msg_type: Mapped[str] = mapped_column(String(32))  # capture_failed / task_failed / report_done
    level: Mapped[int] = mapped_column(SmallInteger, server_default="1")  # 1 info / 2 warn / 3 crit
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str | None] = mapped_column(String(512))
    target_role: Mapped[str | None] = mapped_column(String(16))  # NULL = everyone
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[str | None] = mapped_column(String(64))
    is_read: Mapped[int] = mapped_column(SmallInteger, server_default="0")  # 0 unread, 1 read
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


TABLES = (
    SysUser,
    SysLog,
    MediaAsset,
    DetectTask,
    DetectObject,
    SpeciesDict,
    ModelVersion,
    TrainExperiment,
    SysMessage,
)

# Column counts from data model §1 — the dictionary is the contract, and this
# map is what fails a test the moment a column is added or dropped on one side
# only. Update both together, in the same commit.
EXPECTED_COLUMNS = {
    "sys_user": 13,
    "sys_log": 10,
    "media_asset": 18,
    "detect_task": 16,
    "detect_object": 19,
    "species_dict": 10,
    "model_version": 14,
    "train_experiment": 18,
    "sys_message": 10,
}
