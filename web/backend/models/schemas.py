"""Pydantic-схемы."""

from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


class VideoStatus(str, Enum):
    ready = "ready"
    converting = "converting"
    error = "error"


class AnnotationStatus(str, Enum):
    none = "none"
    auto = "auto"
    manual = "manual"


class VideoInfo(BaseModel):
    id: str                          # stem файла (уникальный ключ)
    filename: str                    # полное имя файла с расширением
    status: VideoStatus = VideoStatus.ready
    fps: float = 0
    total_frames: int = 0
    duration: float = 0
    width: int = 0
    height: int = 0
    size_mb: float = 0
    thumbnail: Optional[str] = None
    annotation_status: AnnotationStatus = AnnotationStatus.none
    has_analysis: bool = False
    video_url: str = ""              # URL для воспроизведения


class VideoListResponse(BaseModel):
    videos: list[VideoInfo]
    total: int


class StrokeAnnotation(BaseModel):
    id: int
    start_frame: int
    contact_frame: Optional[int] = None
    end_frame: int
    start_time: Optional[float] = None
    contact_time: Optional[float] = None
    end_time: Optional[float] = None
    type: str = "other"
    type_confidence: Optional[float] = None
    quality: Any = 5                 # может быть int или float
    errors: list[str] = []
    auto_detected: bool = False
    hand: Optional[str] = None       # для совместимости со старыми разметками
    notes: str = ""


class AnnotationData(BaseModel):
    video: str                       # имя файла видео (как в старых разметках)
    fps: float = 30
    frames: int = 0
    duration: float = 0
    strokes: list[StrokeAnnotation] = []
    auto_detected: bool = False
    updated_at: Optional[str] = None


class StrokeUpdate(BaseModel):
    start_frame: Optional[int] = None
    contact_frame: Optional[int] = None
    end_frame: Optional[int] = None
    type: Optional[str] = None
    quality: Optional[Any] = None
    errors: Optional[list[str]] = None
    notes: Optional[str] = None


class AnalysisStatus(str, Enum):
    idle = "idle"
    extracting_features = "extracting_features"
    detecting_phases = "detecting_phases"
    classifying = "classifying"
    detecting_errors = "detecting_errors"
    done = "done"
    error = "error"


class AnalysisProgress(BaseModel):
    video_id: str
    status: AnalysisStatus
    progress: float = 0
    message: str = ""


class SkeletonFrame(BaseModel):
    frame: int
    landmarks: Optional[dict[str, list[float]]]
    connections: list[list[str]]
    detected: bool