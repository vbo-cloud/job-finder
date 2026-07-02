"""Shared constants used across agents and scripts."""

# Scale factor for PDF-to-JPEG thumbnail rendering via pypdfium2.
# 0.4 ≈ 29 DPI — sufficient for a 176 px wide card without excessive file size.
THUMBNAIL_SCALE: float = 0.4

# Scale factor for the large thumbnail served in the CV detail view.
# 2.0 ≈ 144 DPI — covers the detail panel up to ~1190 px, sufficient for 1440 px Retina displays.
THUMBNAIL_SCALE_LG: float = 2.0
