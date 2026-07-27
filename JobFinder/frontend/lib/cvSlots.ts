/**
 * Single source of truth for the CV library's slot limits. Bump UNLOCKED_CV_SLOTS to change
 * how many CVs a user may hold at once — the only frontend value that needs to move for a
 * future freemium/premium/standard plan tier (no per-user plan lookup exists yet, so this
 * stays a plain constant). Must be kept in sync with MAX_CVS_PER_USER in
 * JobFinder/python/shared/constants.py — that constant is what actually enforces the cap;
 * this one only drives what the library grid shows and blocks client-side.
 */
export const UNLOCKED_CV_SLOTS = 2;

/** Total cells drawn in the library grid: unlocked slots + locked (future) slots. */
export const TOTAL_LIBRARY_SLOTS = 10;
