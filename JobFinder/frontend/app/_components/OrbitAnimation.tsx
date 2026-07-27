"use client";

import { useEffect, useRef } from "react";

type AnimState = "idle" | "uploaded" | "done";

interface Props {
  state:             AnimState;
  thumbnailUrl?:     string | null;
  onThumbnailReady?: () => void;
  onDoneComplete?:   () => void;
  mousePosRef:       React.MutableRefObject<{ x: number; y: number } | null>;
  clickFlashRef:     React.MutableRefObject<number>;
  /** True while a blocked (at-cap) upload attempt's rejection message is
   * showing — tints the document icon's contour and "+" red for the same
   * window. This tint is deliberately idle-only: the icon isn't drawn in
   * "uploaded" state, and "done" always renders untinted (hardcoded `false`
   * on that draw call below) even though `rejected` can still be true there
   * — e.g. a drop rejected mid-animation, since `rejectAdd()` isn't gated on
   * `animState`. The rejection feedback is scoped to idle on purpose, not
   * because the two states can't overlap. */
  rejected?:         boolean;
  /** Incremented on every rejected attempt (even while `rejected` is already
   * true) so the icon's shake burst restarts on a re-click, the same way
   * `clickFlashRef` restarts the click ripple. */
  rejectTick?:       number;
}

interface AmbientParticle {
  x: number; y: number; vx: number; vy: number;
  r: number; a: number;
  birthDelay: number; scale: number;
}
interface OrbitParticle {
  angle: number; rx: number; ry: number; spd: number;
  dx: number; dy: number; r: number; a: number;
  birthDelay: number; scale: number;
}

function doneOffset(t: number): number {
  if (t <= 0) return 0;
  return -16 * Math.sin(Math.PI * t) + t * t * t * 295;
}

// Quadratic ease-out: fast start, slow end
function easeOut(t: number): number {
  return 1 - (1 - t) * (1 - t);
}

// Continuous stand-in for the old shakeReject CSS keyframes (which animated a
// DOM element): a decaying oscillation over SHAKE_DURATION_MS, since canvas
// has no discrete keyframe percentages to reuse.
const SHAKE_DURATION_MS = 400;
function shakeOffset(elapsedMs: number): number {
  if (elapsedMs >= SHAKE_DURATION_MS) return 0;
  const t = elapsedMs / SHAKE_DURATION_MS;
  return Math.sin(t * Math.PI * 6) * 4 * (1 - t);
}

export default function OrbitAnimation({ state, thumbnailUrl, onThumbnailReady, onDoneComplete, mousePosRef, clickFlashRef, rejected = false, rejectTick = 0 }: Props) {
  const canvasRef          = useRef<HTMLCanvasElement>(null);
  const stateRef           = useRef(state);
  const thumbRef           = useRef<HTMLCanvasElement | null>(null);
  const onDoneCompleteRef    = useRef(onDoneComplete);
  const onThumbnailReadyRef  = useRef(onThumbnailReady);
  const rejectedRef          = useRef(rejected);
  const rejectShakeStartRef  = useRef<number | null>(null);

  useEffect(() => { stateRef.current = state; }, [state]);
  useEffect(() => { onDoneCompleteRef.current   = onDoneComplete; },   [onDoneComplete]);
  useEffect(() => { onThumbnailReadyRef.current = onThumbnailReady; }, [onThumbnailReady]);
  useEffect(() => { rejectedRef.current = rejected; }, [rejected]);
  useEffect(() => {
    // Guard, not redundancy: rejectTick starts at 0, so this skips the effect's
    // mount run — without it the icon would shake once on every page load.
    if (rejectTick > 0) rejectShakeStartRef.current = performance.now();
  }, [rejectTick]);

  // Render PDF thumbnail with pdfjs-dist v3
  useEffect(() => {
    if (!thumbnailUrl) { thumbRef.current = null; return; }
    let cancelled = false;
    async function renderPdf() {
      try {
        const pdfjsLib = await import("pdfjs-dist");
        // v3 classic worker — served from /public as a regular JS file
        pdfjsLib.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.js";
        const pdf      = await pdfjsLib.getDocument(thumbnailUrl!).promise;
        const page     = await pdf.getPage(1);
        const viewport = page.getViewport({ scale: 0.2 });
        const canvas   = document.createElement("canvas");
        canvas.width   = viewport.width;
        canvas.height  = viewport.height;
        const ctx      = canvas.getContext("2d")!;
        await page.render({ canvasContext: ctx, viewport }).promise;
        if (!cancelled) {
          thumbRef.current = canvas;
          onThumbnailReadyRef.current?.();
        }
      } catch {
        if (!cancelled) onThumbnailReadyRef.current?.();
      }
    }
    void renderPdf();
    return () => { cancelled = true; };
  }, [thumbnailUrl, onThumbnailReady]);

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx    = canvas.getContext("2d")!;
    let W = 0, H = 0, CX = 0, CY = 0, totalFrames = 0;

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      W = canvas.clientWidth; H = canvas.clientHeight;
      CX = W / 2; CY = H / 2;
      canvas.width  = W * dpr;
      canvas.height = H * dpr;
      ctx.scale(dpr, dpr);
    }
    resize();

    // Particles with staggered birth delays (1–2 s at 60 fps = 60–120 frames)
    const ambient: AmbientParticle[] = Array.from({ length: 220 }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      vx: (Math.random() - 0.5) * 0.3, vy: (Math.random() - 0.5) * 0.3,
      r: 0.15 + Math.random() * 0.8,
      a: 0.03 + Math.random() * 0.14,
      birthDelay: 60 + Math.random() * 60,
      scale: 0,
    }));

    const orbits: OrbitParticle[] = Array.from({ length: 60 }, () => ({
      angle: Math.random() * Math.PI * 2,
      rx: 100 + Math.random() * 320,
      ry: 40  + Math.random() * 140,
      spd: (Math.random() > 0.5 ? 1 : -1) * (0.0015 + Math.random() * 0.0025),
      dx: (Math.random() - 0.5) * 360,
      dy: (Math.random() - 0.5) * 200,
      r: 1.8 + Math.random() * 2.4,
      a: 0.18 + Math.random() * 0.3,
      birthDelay: 60 + Math.random() * 60,
      scale: 0,
    }));

    let cp = 0, dp = 0, hoverLerp = 0, rafId = 0;
    let prevState: AnimState = "idle";
    let doneCompleteFired = false;

    function resetParticles() {
      for (const p of ambient)  { p.scale = 0; p.birthDelay = totalFrames + Math.random() * 60; }
      for (const op of orbits)  { op.scale = 0; op.birthDelay = totalFrames + Math.random() * 60; }
    }

    // ── Document icon ──────────────────────────────────────────
    function drawDocument(textRgb: string, rejectRgb: string, isRejected: boolean) {
      const x = CX - 22, y = CY - 27;
      const fold = 12, r = 4;
      ctx.save();

      if (hoverLerp > 0) {
        ctx.save();
        ctx.globalAlpha = hoverLerp * 0.55;
        ctx.shadowBlur  = 28; ctx.shadowColor = "rgba(170,210,255,0.7)";
        ctx.fillStyle   = "rgba(170,210,255,0.06)";
        ctx.beginPath(); ctx.ellipse(CX, CY, 34, 40, 0, 0, Math.PI * 2); ctx.fill();
        ctx.restore();
      }

      const iconColor = getComputedStyle(document.documentElement).getPropertyValue("--canvas-icon").trim() || "#383838";
      ctx.fillStyle = iconColor;
      ctx.beginPath();
      ctx.moveTo(x + r, y); ctx.lineTo(x + 44 - fold, y);
      ctx.lineTo(x + 44, y + fold); ctx.lineTo(x + 44, y + 54 - r);
      ctx.arcTo(x + 44, y + 54, x + 44 - r, y + 54, r);
      ctx.lineTo(x + r, y + 54);
      ctx.arcTo(x, y + 54, x, y + 54 - r, r);
      ctx.lineTo(x, y + r); ctx.arcTo(x, y, x + r, y, r);
      ctx.closePath(); ctx.fill();
      if (isRejected) {
        // Reuses the still-current body path (fill() doesn't clear it) so the
        // contour traces the exact same outline instead of a separate rect.
        ctx.lineWidth = 2;
        ctx.strokeStyle = `rgb(${rejectRgb})`;
        ctx.stroke();
      }

      ctx.fillStyle = "#252525";
      ctx.beginPath();
      ctx.moveTo(x + 44 - fold, y); ctx.lineTo(x + 44 - fold, y + fold);
      ctx.lineTo(x + 44, y + fold); ctx.closePath(); ctx.fill();

      ctx.fillStyle = `rgba(${textRgb},${0.5 + hoverLerp * 0.35})`;
      ctx.font = "600 7.5px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.fillText("CV", CX, y + 5);

      ctx.strokeStyle = `rgba(${textRgb},0.055)`; ctx.lineWidth = 1;
      for (let i = 0; i < 4; i++) {
        ctx.beginPath(); ctx.moveTo(x + 6, y + 20 + i * 7); ctx.lineTo(x + 38, y + 20 + i * 7); ctx.stroke();
      }

      ctx.strokeStyle = isRejected ? `rgb(${rejectRgb})` : `rgba(${textRgb},${0.5 + hoverLerp * 0.4})`;
      ctx.lineWidth = 1.8 + hoverLerp * 0.8; ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(CX - 9, CY); ctx.lineTo(CX + 9, CY);
      ctx.moveTo(CX, CY - 9);  ctx.lineTo(CX, CY + 9);
      ctx.stroke();
      ctx.restore();
    }

    // ── Thumbnail (PDF render or fallback) ─────────────────────
    function drawThumbnail(yOffset: number, alpha: number) {
      const dw = 44, dh = 54, fold = 12, r = 4;
      const lx = CX - dw / 2, ty = CY - dh / 2 + yOffset;
      ctx.save(); ctx.globalAlpha = alpha;

      ctx.beginPath();
      ctx.moveTo(lx + r, ty); ctx.lineTo(lx + dw - fold, ty);
      ctx.lineTo(lx + dw, ty + fold); ctx.lineTo(lx + dw, ty + dh - r);
      ctx.arcTo(lx + dw, ty + dh, lx + dw - r, ty + dh, r);
      ctx.lineTo(lx + r, ty + dh);
      ctx.arcTo(lx, ty + dh, lx, ty + dh - r, r);
      ctx.lineTo(lx, ty + r); ctx.arcTo(lx, ty, lx + r, ty, r);
      ctx.closePath(); ctx.clip();

      const thumb = thumbRef.current;
      if (thumb) {
        ctx.drawImage(thumb, lx, ty, dw, dh);
      } else {
        ctx.fillStyle = "#f0eff5"; ctx.fillRect(lx, ty, dw, dh);
        ctx.strokeStyle = "rgba(0,0,0,0.08)"; ctx.lineWidth = 1;
        for (let i = 0; i < 6; i++) {
          ctx.beginPath(); ctx.moveTo(lx + 5, ty + 10 + i * 8); ctx.lineTo(lx + 39, ty + 10 + i * 8); ctx.stroke();
        }
        ctx.fillStyle = "#e53e3e"; ctx.fillRect(lx + 24, ty + 3, 16, 9);
        ctx.fillStyle = "#ffffff"; ctx.font = "600 5.5px system-ui";
        ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText("PDF", lx + 32, ty + 7.5);
      }

      ctx.fillStyle = "rgba(0,0,0,0.18)";
      ctx.beginPath();
      ctx.moveTo(lx + dw - fold, ty); ctx.lineTo(lx + dw - fold, ty + fold);
      ctx.lineTo(lx + dw, ty + fold); ctx.closePath(); ctx.fill();

      ctx.restore();
    }

    // ── Click ripple ───────────────────────────────────────────
    function drawClickRipple() {
      const flash = clickFlashRef.current;
      if (flash <= 0) return;
      // Decay rate tuned for a ~150ms shockwave at 60fps (was 0.055, ~300ms —
      // halved on request). The ripple radius below, (1-flash)*65, scales
      // automatically with this rate: no separate change needed there if the
      // decay is retuned again.
      clickFlashRef.current = Math.max(0, flash - 0.11);
      ctx.save();
      ctx.beginPath(); ctx.arc(CX, CY, (1 - flash) * 65, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(170,210,255,${flash * 0.55})`; ctx.lineWidth = 1.5; ctx.stroke();
      ctx.restore();
    }

    function draw() {
      totalFrames++;
      const s = stateRef.current;

      // Detect done → idle transition: reset particles for staggered re-appearance
      if (s === "idle" && prevState === "done") {
        cp = 0; dp = 0; doneCompleteFired = false;
        resetParticles();
      }
      prevState = s;

      if (s === "uploaded") cp = Math.min(1, cp + 0.028);
      if (s === "done") {
        dp = Math.min(1, dp + 0.018);
        // Auto-reset after animation completes — particles re-appear without user click
        if (dp >= 1 && !doneCompleteFired) {
          doneCompleteFired = true;
          setTimeout(() => onDoneCompleteRef.current?.(), 200);
        }
      }
      if (s === "idle") { cp = 0; dp = 0; }

      const mp = mousePosRef.current;
      const isHover = (s === "idle" || s === "done") && mp !== null
        && Math.abs(mp.x - CX) < 28 && Math.abs(mp.y - CY) < 34;
      hoverLerp += ((isHover ? 1 : 0) - hoverLerp) * 0.12;

      // Read theme CSS vars each frame so the canvas reacts instantly to theme switches
      const style        = getComputedStyle(document.documentElement);
      const bgColor      = style.getPropertyValue("--bg-page").trim()        || "#0a0a0f";
      const ambient_rgb  = style.getPropertyValue("--canvas-ambient").trim() || "200,210,230";
      const orbit_rgb    = style.getPropertyValue("--canvas-orbit").trim()   || "170,210,255";
      const iconTextRgb  = style.getPropertyValue("--canvas-icon-text").trim() || "255,255,255";
      const rejectRgb    = style.getPropertyValue("--canvas-reject").trim()   || "248,113,113";

      ctx.fillStyle = bgColor; ctx.fillRect(0, 0, W, H);

      // Ambient particles — staggered birth with ease-out scale
      for (const p of ambient) {
        if (totalFrames >= p.birthDelay && p.scale < 1) {
          p.scale = Math.min(1, p.scale + (1 - p.scale) * 0.18);
        }
        if (p.scale <= 0) continue;
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.scale(easeOut(p.scale), easeOut(p.scale));
        ctx.beginPath(); ctx.arc(0, 0, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${ambient_rgb},${p.a})`; ctx.fill();
        ctx.restore();
      }

      // Orbit particles — staggered birth with ease-out scale
      const spdBoost = 1 + hoverLerp * 0.4;
      const conv = s === "uploaded" ? cp : s === "done" ? 1 : 0;
      const fade = s === "done" ? Math.max(0, 1 - dp * 1.6) : 1;
      for (const op of orbits) {
        if (totalFrames >= op.birthDelay && op.scale < 1) {
          op.scale = Math.min(1, op.scale + (1 - op.scale) * 0.18);
        }
        if (op.scale <= 0) continue;
        op.angle += op.spd * spdBoost;
        const ox = CX + op.dx + op.rx * Math.cos(op.angle);
        const oy = CY + op.dy + op.ry * Math.sin(op.angle);
        const zf = Math.sin(op.angle);
        const sc = 0.65 + 0.35 * (zf + 1) * 0.5;
        const px = ox + (CX - ox) * conv;
        const py = oy + (CY - oy) * conv;
        const a  = op.a * sc * (conv > 0 ? Math.max(0, 1 - conv) : 1) * fade;
        const drawScale = easeOut(op.scale);
        ctx.save();
        ctx.translate(px, py);
        ctx.scale(drawScale, drawScale);
        ctx.beginPath(); ctx.arc(0, 0, op.r * sc, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${orbit_rgb},${a})`; ctx.fill();
        ctx.restore();
      }

      if (s === "idle") {
        const shakeStart = rejectShakeStartRef.current;
        const dx = shakeStart !== null ? shakeOffset(performance.now() - shakeStart) : 0;
        ctx.save();
        ctx.translate(dx, 0);
        drawDocument(iconTextRgb, rejectRgb, rejectedRef.current);
        ctx.restore();
      }
      if (s === "uploaded") { drawThumbnail(0, 1); }
      if (s === "done") {
        // isRejected hardcoded false: rejection feedback is scoped to idle by
        // design, not because "rejected" can't be true here too (it can, if a
        // drop is rejected mid-animation — see the Props doc above).
        drawDocument(iconTextRgb, rejectRgb, false);
        drawThumbnail(doneOffset(dp), Math.max(0, 1 - dp * 1.35));
      }

      drawClickRipple();
    }

    function animate() { rafId = requestAnimationFrame(animate); draw(); }
    animate();

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    return () => { cancelAnimationFrame(rafId); ro.disconnect(); };
  }, [mousePosRef, clickFlashRef]);

  return <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" style={{ display: "block" }} />;
}
