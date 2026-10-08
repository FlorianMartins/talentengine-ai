"""Visual redaction (Module 1).

Every image goes through three steps before anything else may look at it:

1. **Metadata stripping**: the image is re-encoded from raw pixels, which drops EXIF/XMP/IPTC blocks
   (GPS position, author, camera serial number, editing software...). What was removed is reported.
2. **Region detection**: a pluggable ``RegionDetector`` returns boxes for faces, school logos,
   name tags, ID cards and any visible personal text. The default is a local vision-language model
   (Qwen2.5-VL through Ollama) so no image ever leaves the client's infrastructure.
3. **Masking**: each region is pixelated *and* blurred (pixelation alone can be partially reversed
   on small regions; the blur on top removes that).

If no detector can run, the pipeline fails closed: the image is quarantined, never analysed in clear.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import re
from dataclasses import dataclass
from typing import Protocol

import httpx
from PIL import ExifTags, Image, ImageFilter

log = logging.getLogger(__name__)

SENSITIVE_REGION_KINDS = ("face", "school_logo", "name_tag", "id_document", "personal_text", "license_plate")


@dataclass(frozen=True)
class Region:
    kind: str
    x: int
    y: int
    width: int
    height: int
    score: float = 1.0


class DetectorUnavailable(RuntimeError):
    """Raised when a detector cannot run (model missing, service down). Triggers quarantine."""


class RegionDetector(Protocol):
    name: str

    def detect(self, image: Image.Image) -> list[Region]: ...

    def describe(self, image: Image.Image) -> str: ...


@dataclass
class VisionResult:
    image_bytes: bytes
    media_type: str
    regions: list[Region]
    metadata_removed: list[str]
    caption: str
    detector: str


# --------------------------------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------------------------------

_DETECT_PROMPT = (
    "You are a privacy filter. List every region of this image that could identify a person or their "
    "demographics: faces, school or university logos, name tags, ID documents, visible personal text "
    "(names, addresses, phone numbers), licence plates. Answer ONLY with JSON: "
    '{"regions": [{"kind": "face|school_logo|name_tag|id_document|personal_text|license_plate", '
    '"box": [x_min, y_min, x_max, y_max]}]} with coordinates normalised to 0-1000. '
    'Answer {"regions": []} if there is none.'
)

_DESCRIBE_PROMPT = (
    "Describe the work shown in this portfolio image for a skills assessment, in 2-4 factual sentences: "
    "what was produced, the techniques and materials visible, and cues of technical complexity or "
    "quality control. Never describe people (no age, gender, ethnicity, clothing or appearance)."
)


class OllamaVLMDetector:
    """Local vision-language model (Qwen2.5-VL by default) served by Ollama."""

    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self.name = f"ollama:{model}"
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _ask(self, image: Image.Image, prompt: str, json_mode: bool) -> str:
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=90)
        payload: dict[str, object] = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "user", "content": prompt,
                          "images": [base64.b64encode(buf.getvalue()).decode()]}],
            "options": {"temperature": 0},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise DetectorUnavailable(f"{self.name}: {exc}") from exc
        return str(resp.json().get("message", {}).get("content", ""))

    def detect(self, image: Image.Image) -> list[Region]:
        raw = self._ask(image, _DETECT_PROMPT, json_mode=True)
        try:
            items = json.loads(raw).get("regions", [])
        except (json.JSONDecodeError, AttributeError) as exc:
            # An unparseable answer is not "no face": fail closed.
            raise DetectorUnavailable(f"{self.name}: unparseable detector output") from exc
        w, h = image.size
        regions = []
        for item in items:
            box = item.get("box") if isinstance(item, dict) else None
            if not (isinstance(box, list) and len(box) == 4):
                continue
            x0, y0, x1, y1 = (max(0.0, min(1000.0, float(v))) for v in box)
            regions.append(Region(
                kind=str(item.get("kind", "personal_text")),
                x=int(x0 * w / 1000), y=int(y0 * h / 1000),
                width=max(1, int((x1 - x0) * w / 1000)), height=max(1, int((y1 - y0) * h / 1000)),
            ))
        return regions

    def describe(self, image: Image.Image) -> str:
        return self._ask(image, _DESCRIBE_PROMPT, json_mode=False).strip()


class OpenCVFaceDetector:
    """Classic Haar-cascade face detector (``pip install talentengine-ai[vision]``). Faces only."""

    name = "opencv:haar-frontalface"

    def __init__(self) -> None:
        try:
            import cv2
        except ImportError as exc:  # pragma: no cover - depends on the optional extra
            raise DetectorUnavailable("opencv-python-headless is not installed") from exc
        self._cv2 = cv2
        self._cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def detect(self, image: Image.Image) -> list[Region]:  # pragma: no cover - optional extra
        import numpy as np

        gray = self._cv2.cvtColor(np.array(image.convert("RGB")), self._cv2.COLOR_RGB2GRAY)
        faces = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4)
        return [Region("face", int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def describe(self, image: Image.Image) -> str:  # pragma: no cover - optional extra
        return ""


class NoDetector:
    name = "none"

    def detect(self, image: Image.Image) -> list[Region]:
        raise DetectorUnavailable("no visual detector configured")

    def describe(self, image: Image.Image) -> str:
        return ""


# --------------------------------------------------------------------------------------------------
# Redaction
# --------------------------------------------------------------------------------------------------

_SAFE_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def _metadata_tags(image: Image.Image) -> list[str]:
    removed: set[str] = set()
    exif = image.getexif()
    for tag_id in exif:
        removed.add(ExifTags.TAGS.get(tag_id, f"tag-{tag_id}"))
    if exif.get_ifd(ExifTags.IFD.GPSInfo):
        removed.add("GPSInfo")
    for key in image.info:
        if key in {"exif", "xmp", "XML:com.adobe.xmp", "icc_profile", "comment", "photoshop", "iptc"}:
            removed.add(key)
    return sorted(removed)


def mask_regions(image: Image.Image, regions: list[Region]) -> Image.Image:
    out = image.convert("RGB").copy()
    for r in regions:
        pad_x, pad_y = int(r.width * 0.15), int(r.height * 0.15)  # margin: hair line, logo edge
        box = (max(0, r.x - pad_x), max(0, r.y - pad_y),
               min(out.width, r.x + r.width + pad_x), min(out.height, r.y + r.height + pad_y))
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        patch = out.crop(box)
        small = patch.resize((max(1, patch.width // 16), max(1, patch.height // 16)), Image.Resampling.BILINEAR)
        patch = small.resize(patch.size, Image.Resampling.NEAREST).filter(ImageFilter.GaussianBlur(radius=12))
        out.paste(patch, box)
    return out


def redact_image(data: bytes, detector: RegionDetector, *, describe: bool = True) -> VisionResult:
    """Strip metadata, detect and mask sensitive regions. Raises DetectorUnavailable to quarantine."""
    with Image.open(io.BytesIO(data)) as src:
        src.load()
        fmt = src.format or "PNG"
        removed = _metadata_tags(src)
        # Re-encoding from raw pixels is what actually drops the metadata blocks.
        clean = Image.frombytes(src.convert("RGB").mode, src.size, src.convert("RGB").tobytes())
    regions = [r for r in detector.detect(clean) if r.width > 0 and r.height > 0]
    masked = mask_regions(clean, regions)
    caption = ""
    if describe:
        try:
            caption = _strip_people(detector.describe(masked))
        except DetectorUnavailable:
            caption = ""
    out_fmt = fmt if fmt in _SAFE_FORMATS else "PNG"
    buf = io.BytesIO()
    masked.save(buf, format=out_fmt)
    return VisionResult(buf.getvalue(), _SAFE_FORMATS[out_fmt], regions, removed, caption, detector.name)


_PEOPLE_WORDS = re.compile(
    r"[^.]*\b(?:man|woman|men|women|boy|girl|person|people|homme|femme|garçon|fille|personne|years old|"
    r"skin|hair|cheveux|peau|beard|barbe|smiling|souriant)\b[^.]*\.?",
    re.IGNORECASE,
)


def _strip_people(caption: str) -> str:
    """Second line of defence: drop any caption sentence that still talks about a person."""
    return " ".join(_PEOPLE_WORDS.sub("", caption).split())


def build_detector(kind: str, ollama_url: str, model: str) -> RegionDetector:
    if kind == "ollama":
        return OllamaVLMDetector(ollama_url, model)
    if kind == "opencv":
        try:
            return OpenCVFaceDetector()
        except DetectorUnavailable:
            log.warning("OpenCV detector requested but not installed: images will be quarantined")
    return NoDetector()
