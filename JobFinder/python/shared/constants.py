"""Shared constants used across agents and scripts."""

# Scale factor for PDF-to-JPEG thumbnail rendering via pypdfium2.
# 0.4 ≈ 29 DPI — sufficient for a 176 px wide card without excessive file size.
THUMBNAIL_SCALE: float = 0.4
