"""Computer vision analysis service.

Tries to load a trained PyTorch classifier from the configured model directory.
When no weights are found (the common case in the repo's current state), it falls
back to a transparent, deterministic image-statistics heuristic so the feature is
usable end-to-end. The ``is_demo`` flag is always surfaced so callers can label
results honestly.

All ML/numerics imports (numpy, Pillow, torch) are lazy so the rest of the API
starts even when those optional weights/libraries are not installed yet.
"""

from __future__ import annotations

import io
import logging
import os
from typing import Any

from app.core.config import settings
from app.core.exceptions import AppException, ValidationException

logger = logging.getLogger("medivision.services.vision")


MODALITIES: dict[str, list[str]] = {
    "brain_mri": ["Normal", "Glioma", "Meningioma", "Pituitary Tumor"],
    "chest_xray": ["Normal", "Pneumonia", "Tuberculosis", "COVID-19"],
    "skin": ["Benign Nevus", "Melanoma", "Basal Cell Carcinoma", "Squamous Cell Carcinoma"],
    "eye": ["Normal", "Diabetic Retinopathy", "Glaucoma", "Cataract"],
    "blood_smear": ["Normal", "Malaria", "Leukemia", "Anemia"],
}

MAX_IMAGE_PIXELS = 4000
SUPPORTED_IMAGE_FORMATS = {"JPEG", "PNG"}


def _np():
    import numpy as np
    return np


def _pil():
    from PIL import Image
    return Image


def _normalize_modality(modality: str) -> str:
    key = modality.strip().lower()
    if key not in MODALITIES:
        raise ValidationException(
            f"Unsupported image modality '{modality}'",
            details={"supported": sorted(MODALITIES)},
        )
    return key


def _decode_image(image_bytes: bytes):
    Image = _pil()
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except Exception as exc:
        raise ValidationException(
            "Unable to read image. Only JPEG/PNG images are accepted.",
            details={"error": str(exc)},
        )
    if image.format not in SUPPORTED_IMAGE_FORMATS:
        image = image.convert("RGB")
    if max(image.size) > MAX_IMAGE_PIXELS:
        image.thumbnail((MAX_IMAGE_PIXELS, MAX_IMAGE_PIXELS))
    return image


def _softmax(np, x) -> Any:
    ex = np.exp(x - np.max(x))
    return ex / ex.sum()


def _fallback_predict(modality: str, image) -> dict:
    """Deterministic heuristic using basic image statistics."""
    np = _np()
    classes = MODALITIES[modality]
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    if gray.size == 0:
        raise ValidationException("Image is empty after decoding")
    gray = gray / 255.0

    mean = float(gray.mean())
    std = float(gray.std())
    gy, gx = np.gradient(gray)
    edge_energy = float(np.sqrt(gx**2 + gy**2).mean())
    std2 = float(np.asarray(image.convert("RGB"), dtype=np.float32).std())

    # Heuristic features mapped to plausible classes per modality.
    feats = {
        "brain_mri": [mean, std, edge_energy, 1.0 - abs(std2 - 0.55)],
        "chest_xray": [1.0 - abs(std2 - 0.5), edge_energy, mean, 0.4 * mean + 0.6 * edge_energy],
        "skin": [std2, 1.0 - abs(mean - 0.45), edge_energy, 1.0 - abs(mean - 0.6)],
        "eye": [1.0 - abs(mean - 0.4), 1.0 - abs(std - 0.3), edge_energy, 1.0 - abs(std2 - 0.5)],
        "blood_smear": [1.0 - abs(mean - 0.5), std, edge_energy, 1.0 - abs(std2 - 0.35)],
    }
    weights = [0.4, 0.3, 0.2, 0.1]
    logits = np.array(
        [sum(w * f for w, f in zip(weights, feats[modality])) for _ in classes],
        dtype=np.float64,
    )
    logits += np.linspace(0, 0.12, len(classes))
    probs = _softmax(np, logits * 6.0)
    probs = np.round(probs, 4)

    order = np.argsort(probs)[::-1]
    probabilities = {classes[i]: float(probs[i]) for i in order}
    top_index = int(order[0])

    label = classes[top_index]
    confidence = float(probs[top_index])
    explanation = (
        f"Demo analysis ({label}) computed from image statistics (brightness, texture, "
        f"edge energy) because no trained model weights are loaded. Confidence "
        f"{confidence * 100:.1f}%. This is not a clinical result."
    )
    return {
        "prediction_label": label,
        "confidence": round(confidence, 4),
        "class_probabilities": probabilities,
        "model_name": "rule_based_fallback_v1",
        "is_demo": True,
        "explanation": explanation,
    }


def _model_path() -> str | None:
    directory = os.path.abspath(os.path.join(os.getcwd(), settings.vision_model_dir))
    if not os.path.isdir(directory):
        return None
    candidates = ["model.pt", "best.pt", "model.pth", "best.pth", "resnet50_finetuned.pt"]
    for name in candidates:
        path = os.path.join(directory, name)
        if os.path.exists(path):
            return path
    return None


def _torch_predict(modality: str, image) -> dict | None:
    """Attempt a real model inference; returns None on any failure."""
    path = _model_path()
    if not path:
        return None
    try:
        import torch
        import torchvision.transforms as transforms
        from torchvision import models
    except Exception as exc:  # torch unavailable
        logger.warning("Torch unavailable for vision inference: %s", exc)
        return None

    np = _np()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    try:
        model = models.resnet18(weights=None)
        num_classes = len(MODALITIES[modality])
        model.fc = torch.nn.Linear(model.fc.in_features, num_classes)
        state = torch.load(path, map_location=device)
        if isinstance(state, dict) and "state_dict" in state:
            state = state["state_dict"]
        model.load_state_dict(state)
        model.to(device).eval()

        transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        tensor = transform(image.convert("RGB")).unsqueeze(0).to(device)
        with torch.no_grad():
            logits = model(tensor)[0]
            probs = torch.softmax(logits, dim=0).cpu().numpy()

        probs = np.round(probs, 4)
        order = np.argsort(probs)[::-1]
        classes = MODALITIES[modality]
        probabilities = {classes[int(i)]: float(probs[int(i)]) for i in order}
        top_index = int(order[0])
        return {
            "prediction_label": classes[top_index],
            "confidence": round(float(probs[top_index]), 4),
            "class_probabilities": probabilities,
            "model_name": f"resnet18_{modality}",
            "is_demo": False,
            "explanation": f"Real model inference using {os.path.basename(path)}.",
        }
    except Exception as exc:
        logger.warning("Model inference failed, falling back to rule-based: %s", exc)
        return None


def analyze_image(modality: str, image_bytes: bytes) -> dict:
    key = _normalize_modality(modality)
    image = _decode_image(image_bytes)
    result = _torch_predict(key, image) or _fallback_predict(key, image)
    result["modality"] = key
    result["status"] = "completed"
    return result


# Jet colormap corners (pure float, no numpy needed at module load).
_RED = (1.0, 0.0, 0.0)
_GREEN = (0.0, 1.0, 0.0)
_BLUE = (0.0, 0.0, 1.0)
_YELLOW = (1.0, 1.0, 0.0)
_CYAN = (0.0, 1.0, 1.0)


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _jet_color(t: float) -> tuple[int, int, int]:
    if t < 0.125:
        c = _lerp(_BLUE, _CYAN, t / 0.125)
    elif t < 0.375:
        c = _lerp(_CYAN, _GREEN, (t - 0.125) / 0.25)
    elif t < 0.625:
        c = _lerp(_GREEN, _YELLOW, (t - 0.375) / 0.25)
    elif t < 0.875:
        c = _lerp(_YELLOW, _RED, (t - 0.625) / 0.25)
    else:
        c = _RED
    return (
        int(255 * max(0.0, min(1.0, c[0]))),
        int(255 * max(0.0, min(1.0, c[1]))),
        int(255 * max(0.0, min(1.0, c[2]))),
    )


def build_saliency(image_bytes: bytes) -> bytes | None:
    """Produce a grad-CAM-like saliency heatmap (edge-magnitude based) as PNG bytes."""
    try:
        np = _np()
        Image = _pil()
        image = _decode_image(image_bytes)
        gray = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
        gy, gx = np.gradient(gray)
        magnitude = np.sqrt(gx**2 + gy**2)
        normalized = magnitude / (magnitude.max() + 1e-6)

        h, w = normalized.shape
        heat = np.zeros((h, w, 3), dtype=np.uint8)
        for i in range(h):
            for j in range(w):
                heat[i, j] = _jet_color(float(normalized[i, j]))
        out = Image.fromarray(heat, mode="RGB")
        buf = io.BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Saliency map generation failed: %s", exc)
        return None