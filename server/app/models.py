"""The fourteen tables of the data model, as SQLAlchemy declarative models (P1-01).

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
    UniqueConstraint,
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
    #: Bumped when the password changes. A token carries the value it was issued under, and the guard
    #: refuses a token whose value is older - which is NFR-S-05's "a password change invalidates
    #: issued tokens", without a session table. Disabling an account is already immediate: the guard
    #: reads `status` on every request.
    token_epoch: Mapped[int] = mapped_column(Integer, server_default="0")
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


class SysParam(Base):
    """Runtime configuration with an audit trail (data model §3.10, FR-M7-01).

    Key/value rather than one column per setting: adding a parameter must not need a migration, and
    the settings are read by code that already knows their names. `value_type` is what lets the reader
    cast a string back to the type it had, so the table stores what was set rather than a string that
    happens to look like a number.
    """

    __tablename__ = "sys_param"

    param_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    param_key: Mapped[str] = mapped_column(String(64), unique=True)
    param_value: Mapped[str] = mapped_column(String(255))
    value_type: Mapped[str] = mapped_column(String(16))  # int / float / bool / str
    remark: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.user_id"), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Dataset(Base):
    """An exported dataset snapshot (data model §3.11, FR-M4-04).

    It exists before any experiment references it: the export page produces a snapshot, and training
    uses it days later. That gap is why the table exists at all — `train_experiment.dataset_snapshot`
    can only name a snapshot that some experiment already used.
    """

    __tablename__ = "dataset"

    dataset_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    snapshot_name: Mapped[str] = mapped_column(String(64), unique=True)  # DS-V3
    manifest_path: Mapped[str] = mapped_column(String(512))  # human-readable copy
    split_ratio: Mapped[str] = mapped_column(String(16))  # 7:2:1
    seed: Mapped[int] = mapped_column(Integer)
    frame_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[int] = mapped_column(
        SmallInteger, server_default="1"
    )  # 0 building, 1 ready, 2 archived
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.user_id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DatasetItem(Base):
    """One frame inside one snapshot, and the split it was assigned to (data model §3.12, AC-18).

    Membership is a table rather than a JSON list because three questions depend on it and all three
    are joins: which frames trained this model, may this frame be cleaned up, and are the groups
    still separated. `group_key` is what keeps similar frames from straddling two splits.
    """

    __tablename__ = "dataset_item"
    __table_args__ = (
        UniqueConstraint("dataset_id", "asset_id", name="uq_dataset_item_asset"),
        Index("ix_dataset_item_dataset_split", "dataset_id", "split"),
    )

    item_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("dataset.dataset_id"), index=True
    )
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("media_asset.asset_id"), index=True
    )
    split: Mapped[int] = mapped_column(SmallInteger)  # 1 train, 2 val, 3 test
    group_key: Mapped[str | None] = mapped_column(String(64))


class Report(Base):
    """One generated inspection report and its file (data model §3.13, FR-M5-04, AC-22).

    The period, template and basis are columns because the history is filtered by them; the document
    itself is a file, exactly as a model's weights are. Without the row the history would be a pile of
    files whose names encode what should have been queryable.
    """

    __tablename__ = "report"

    report_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    report_code: Mapped[str] = mapped_column(String(32), unique=True)  # RPyyMMdd-serial
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    template: Mapped[str] = mapped_column(String(16))  # standard / brief
    basis: Mapped[str] = mapped_column(String(16))  # reviewed / raw
    model_version_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("model_version.model_id"), index=True
    )
    file_path: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[int] = mapped_column(
        SmallInteger, server_default="0"
    )  # 0 generating, 1 ready, 2 failed - the words `serializers.REPORT_STATUS` publishes
    error_msg: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sys_user.user_id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DetectTaskItem(Base):
    """One frame assigned to one task, and the outcome for it (data model §3.14, ADR 12).

    A task does not discover its frames: `create_batch` writes one item per frame when the task is
    created, so the work list is fixed and every worker sees the same one. The row is also where
    "finished" lives - `box_count = 0` with `state = done` is a result, not an absence of one, which
    `detect_object` cannot express because a box needs a class and a geometry.
    """

    __tablename__ = "detect_task_item"
    __table_args__ = (
        UniqueConstraint("task_id", "asset_id", name="uq_detect_task_item_asset"),
        Index("ix_detect_task_item_task_state", "task_id", "state"),
    )

    item_id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("detect_task.task_id"), index=True)
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("media_asset.asset_id"), index=True
    )
    state: Mapped[int] = mapped_column(
        SmallInteger, server_default="0"
    )  # 0 pending / 1 running / 2 done / 3 failed
    box_count: Mapped[int] = mapped_column(Integer, server_default="0")
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


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
    SysParam,
    Dataset,
    DatasetItem,
    Report,
    DetectTaskItem,
)

# Column counts from data model §1 — the dictionary is the contract, and this
# map is what fails a test the moment a column is added or dropped on one side
# only. Update both together, in the same commit.
EXPECTED_COLUMNS = {
    "sys_user": 14,
    "sys_log": 10,
    "media_asset": 18,
    "detect_task": 16,
    "detect_object": 19,
    "species_dict": 10,
    "model_version": 14,
    "train_experiment": 18,
    "sys_message": 10,
    "sys_param": 7,
    "dataset": 9,
    "dataset_item": 5,
    "report": 12,
    "detect_task_item": 7,
}
