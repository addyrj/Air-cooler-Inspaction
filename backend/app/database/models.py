"""SQLite database — no PostgreSQL needed."""
from sqlalchemy import (
    create_engine, Column, Integer, String,
    Float, Boolean, DateTime, Text, JSON,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import os

DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./inspection.db")

engine = create_engine(
    DB_PATH,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine,
)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Cooler(Base):
    __tablename__ = "coolers"
    id         = Column(Integer, primary_key=True, index=True)
    serial_no  = Column(String(100), unique=True, nullable=False)
    model      = Column(String(100), default="Brize Glacier 110")
    batch_no   = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Inspection(Base):
    __tablename__ = "inspections"
    id                 = Column(Integer, primary_key=True, index=True)
    cooler_id          = Column(Integer, nullable=False)
    started_at         = Column(DateTime, default=datetime.utcnow)
    completed_at       = Column(DateTime, nullable=True)
    duration_seconds   = Column(Float, nullable=True)
    result             = Column(String(20), default="IN_PROGRESS")
    rotation_completed = Column(Float, default=0.0)
    frames_captured    = Column(Integer, default=0)
    frames_analysed    = Column(Integer, default=0)
    model_version      = Column(String(20), default="v1.0")
    fail_reasons       = Column(JSON, default=list)
    operator_id        = Column(String(50), default="unknown")
    synced_cloud       = Column(Boolean, default=False)
    sync_attempts      = Column(Integer, default=0)
    created_at         = Column(DateTime, default=datetime.utcnow)


class Defect(Base):
    __tablename__ = "defects"
    id             = Column(Integer, primary_key=True, index=True)
    inspection_id  = Column(Integer, nullable=False, index=True)
    camera_id      = Column(Integer)
    rotation_angle = Column(Float)
    defect_type    = Column(String(50))
    anomaly_score  = Column(Float)
    confidence     = Column(Float)
    image_path     = Column(String(500))
    bbox           = Column(JSON)
    created_at     = Column(DateTime, default=datetime.utcnow)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    id            = Column(Integer, primary_key=True, index=True)
    inspection_id = Column(Integer, nullable=False, index=True)
    sensor_type   = Column(String(50))
    value         = Column(Float)
    unit          = Column(String(20))
    status        = Column(String(20))
    recorded_at   = Column(DateTime, default=datetime.utcnow)


class Correction(Base):
    """Stores human feedback on model predictions for retraining."""
    __tablename__ = "corrections"
    id              = Column(Integer, primary_key=True, index=True)
    image_id        = Column(String(100), nullable=False, index=True)  # UUID of saved image
    image_path      = Column(String(500), nullable=True)
    predicted       = Column(String(20), nullable=False)   # PASS/FAIL/RECHECK
    actual          = Column(String(20), nullable=False)   # what it really was
    correct_type    = Column(String(50), nullable=True)    # correct defect type if known
    anomaly_score   = Column(Float, nullable=True)
    notes           = Column(Text, nullable=True)
    applied         = Column(Boolean, default=False)       # moved to training set?
    created_at      = Column(DateTime, default=datetime.utcnow)


def create_tables():
    Base.metadata.create_all(bind=engine)
    print("Database tables created (inspection.db)")


if __name__ == "__main__":
    create_tables()
