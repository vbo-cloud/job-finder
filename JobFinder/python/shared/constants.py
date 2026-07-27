"""Shared constants used across agents and scripts."""

# Scale factor for PDF-to-JPEG thumbnail rendering via pypdfium2.
# 0.4 ≈ 29 DPI — sufficient for a 176 px wide card without excessive file size.
THUMBNAIL_SCALE: float = 0.4

# Scale factor for the large thumbnail served in the CV detail view.
# 2.0 ≈ 144 DPI — covers the detail panel up to ~1190 px, sufficient for 1440 px Retina displays.
THUMBNAIL_SCALE_LG: float = 2.0

# Maximum number of CVs a user may have stored at once. Single source of truth for the
# server-side cap enforced in routers/cv.py::upload_cv. Bump this one value to loosen the
# cap for a future freemium/premium/standard plan tier — no per-user plan lookup exists yet
# (UserProfile has no plan/tier field), so this stays a plain constant for now. Must be kept
# in sync with UNLOCKED_CV_SLOTS in JobFinder/frontend/lib/cvSlots.ts (frontend/backend are
# separate runtimes — no shared source of truth between them today).
MAX_CVS_PER_USER: int = 2
