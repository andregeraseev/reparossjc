import hashlib
from dataclasses import dataclass
from uuid import uuid4

from .models import ServiceRequestAttachment

MAX_IMAGES_PER_REQUEST = 8
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024


class UploadValidationError(ValueError):
    pass


@dataclass
class ValidatedImage:
    uploaded_file: object
    content_type: str
    extension: str
    size_bytes: int
    checksum_sha256: str


def _detected_image(header):
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", "jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", "png"
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None


def validate_images(files, *, existing_count=0, existing_bytes=0):
    files = list(files or [])
    if existing_count + len(files) > MAX_IMAGES_PER_REQUEST:
        raise UploadValidationError(f"Envie no máximo {MAX_IMAGES_PER_REQUEST} imagens por chamado.")
    validated = []
    total = int(existing_bytes or 0)
    for uploaded in files:
        size = int(getattr(uploaded, "size", 0) or 0)
        if size < 1:
            raise UploadValidationError("Uma das imagens está vazia.")
        if size > MAX_IMAGE_BYTES:
            raise UploadValidationError("Cada imagem pode ter no máximo 8 MB.")
        uploaded.seek(0)
        header = uploaded.read(16)
        detected = _detected_image(header)
        if detected is None:
            raise UploadValidationError("Use somente imagens JPG, PNG ou WebP.")
        content_type, extension = detected
        digest = hashlib.sha256()
        uploaded.seek(0)
        for chunk in uploaded.chunks():
            digest.update(chunk)
        uploaded.seek(0)
        total += size
        if total > MAX_TOTAL_BYTES:
            raise UploadValidationError("O conjunto de imagens pode ter no máximo 24 MB.")
        validated.append(ValidatedImage(uploaded, content_type, extension, size, digest.hexdigest()))
    return validated


def create_attachments(service_request, validated, *, uploaded_by=None):
    created = []
    current = None
    try:
        start = service_request.image_attachments.count()
        for index, image in enumerate(validated, start=start + 1):
            attachment = ServiceRequestAttachment(
                id="AT" + uuid4().hex[:24],
                service_request=service_request,
                display_name=f"Foto {index}",
                content_type=image.content_type,
                size_bytes=image.size_bytes,
                checksum_sha256=image.checksum_sha256,
                uploaded_by=uploaded_by,
            )
            filename = f"foto-{index:02d}.{image.extension}"
            attachment.file.save(filename, image.uploaded_file, save=False)
            current = attachment
            attachment.save()
            created.append(attachment)
            current = None
        return created
    except Exception:
        if current is not None:
            try:
                current.file.delete(save=False)
            except Exception:
                pass
        for attachment in created:
            try:
                attachment.file.delete(save=False)
            except Exception:
                pass
        raise
