"use client";

import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";
import posthog from "posthog-js";

import apiClient from "@/lib/api/client";
import { loginRequest } from "@/lib/auth/msalConfig";
import { cn } from "@/lib/utils";
import { UNLOCKED_CV_SLOTS } from "@/lib/cvSlots";

import OrbitAnimation from "./OrbitAnimation";
import ScrollHint from "./ScrollHint";

type AnimState = "idle" | "uploaded" | "done";

const MAX_PDF_BYTES = 10 * 1024 * 1024;

interface Props {
  onUploadComplete?: (cvId: string) => void;
  onAnimationComplete?: (thumbnailUrl: string) => void;
  libraryAccessible?: boolean;
  /** Enters the map mode — owned by HomeMapSection, which controls the CV/map layer switch. */
  onEnterMap?: () => void;
  /** Scrolls to the library section — owned by HomeClient, which knows about the sibling's DOM id. */
  onScrollToLibrary?: () => void;
  /** Current number of CVs already stored — drives the at-cap block below. */
  cvCount?: number;
}

export interface UploadSectionHandle {
  /** Opens the native file picker as if the CV icon had been clicked — lets
   * LibrarySection's "Ajouter un CV" button share this component's upload
   * and animation pipeline instead of running its own. Silently no-ops while
   * an upload/animation is already in flight (`animState !== "idle"`), same
   * as the icon's own onClick. */
  openPicker: () => void;
}

const UploadSection = forwardRef<UploadSectionHandle, Props>(function UploadSection(
  { onUploadComplete, onAnimationComplete, libraryAccessible = false, onEnterMap, onScrollToLibrary, cvCount = 0 },
  ref,
) {
  const [animState, setAnimState]       = useState<AnimState>("idle");
  const [isDragging, setIsDragging]     = useState(false);
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [capRejected, setCapRejected]   = useState(false);
  const [rejectTick, setRejectTick]     = useState(0);
  const fileInputRef                    = useRef<HTMLInputElement>(null);
  const pendingRevokeRef                = useRef<string | null>(null);
  const capRejectedTimerRef             = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { instance }                    = useMsal();
  const isAuthenticated                 = useIsAuthenticated();
  const mousePosRef                     = useRef<{ x: number; y: number } | null>(null);
  const clickFlashRef                   = useRef<number>(0);
  const atCap                           = cvCount >= UNLOCKED_CV_SLOTS;

  const rejectAdd = useCallback(() => {
    setCapRejected(true);
    setRejectTick((n) => n + 1); // OrbitAnimation restarts its icon shake burst on every increment
    if (capRejectedTimerRef.current) clearTimeout(capRejectedTimerRef.current);
    capRejectedTimerRef.current = setTimeout(() => setCapRejected(false), 1800);
  }, []);

  useEffect(() => {
    return () => {
      if (capRejectedTimerRef.current) clearTimeout(capRejectedTimerRef.current);
    };
  }, []);

  const handleFile = useCallback(
    (file: File): void => {
      // Checked before the auth redirect (unlike handleClick below): a drop can
      // deliver a file without any preceding click, so this is the only
      // gate a dropped file is guaranteed to pass through.
      if (atCap) { rejectAdd(); return; }
      if (file.type !== "application/pdf") return;
      if (file.size > MAX_PDF_BYTES) return;
      if (!isAuthenticated) {
        void instance.loginRedirect(loginRequest);
        return;
      }
      const objectUrl = URL.createObjectURL(file);
      pendingRevokeRef.current = objectUrl; // revoked in handleThumbnailReady after pdfjs reads it
      setThumbnailUrl(objectUrl);
      setAnimState("uploaded");
      const formData = new FormData();
      formData.append("file", file);
      // Upload runs in background — done state driven by onThumbnailReady, not the network.
      // No .finally() revoke here: pdfjs must read the URL first (race condition fix).
      apiClient
        .post<{ cv_id: string }>("/cv/upload", formData)
        .then((res) => {
          posthog.capture("cv_uploaded", { cv_id: res.data.cv_id });
          onUploadComplete?.(res.data.cv_id);
        })
        .catch(() => { /* silent — library card shows regardless */ });
    },
    [atCap, rejectAdd, isAuthenticated, instance, onUploadComplete],
  );

  const handleThumbnailReady = useCallback(() => {
    // URL revocation is deferred to handleDoneComplete so the parent can
    // use it as an optimistic thumbnail in the library.
    setAnimState("done");
  }, []);

  const handleDoneComplete = useCallback(() => {
    if (pendingRevokeRef.current) {
      onAnimationComplete?.(pendingRevokeRef.current);
      pendingRevokeRef.current = null; // ownership transferred to parent
    }
    setAnimState("idle");
    setThumbnailUrl(null);
  }, [onAnimationComplete]);

  const handleClick = useCallback((e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    if (Math.abs(x - cx) > 28 || Math.abs(y - cy) > 34) return;
    if (animState === "idle") {
      if (!isAuthenticated) {
        void instance.loginRedirect(loginRequest);
        return;
      }
      if (atCap) { rejectAdd(); return; }
      clickFlashRef.current = 1.0;
      fileInputRef.current?.click();
    }
  }, [animState, isAuthenticated, instance, atCap, rejectAdd]);

  useImperativeHandle(ref, () => ({
    openPicker: () => {
      if (animState !== "idle") return;
      if (atCap) { rejectAdd(); return; }
      fileInputRef.current?.click();
    },
  }), [animState, atCap, rejectAdd]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  // No <section> root here: HomeMapSection owns the h-dvh/snap-start section
  // and layers this component (CV layer) with the commune map behind it.
  return (
    <div className="absolute inset-0">
      <OrbitAnimation
        state={animState}
        thumbnailUrl={thumbnailUrl}
        onThumbnailReady={handleThumbnailReady}
        onDoneComplete={handleDoneComplete}
        mousePosRef={mousePosRef}
        clickFlashRef={clickFlashRef}
        rejected={capRejected}
        rejectTick={rejectTick}
      />

      <div
        onClick={handleClick}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const y = e.clientY - rect.top;
          mousePosRef.current = { x, y };
          const overIcon = Math.abs(x - rect.width / 2) < 28 && Math.abs(y - rect.height / 2) < 34;
          e.currentTarget.style.cursor = overIcon ? "pointer" : "default";
        }}
        onMouseLeave={() => { mousePosRef.current = null; }}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={cn("absolute inset-0", isDragging && "ring-1 ring-subtle")}
        aria-label="Importer un CV"
      />

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        className="sr-only"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFile(f); e.target.value = ""; }}
      />

      {animState === "idle" && (
        <p className={cn(
          "pointer-events-none absolute bottom-[88px] left-0 right-0 text-center text-xs",
          capRejected ? "text-destructive" : "text-hint",
        )}>
          {capRejected ? "Tous vos emplacements sont occupés" : "Déposez votre CV (PDF) · ou cliquez pour parcourir"}
        </p>
      )}

      {/* Gated like the map mode itself (HomeMapSection): the zone is tied
          to the profile, which requires being signed in. */}
      {/* Hidden on coarse pointers: HomeMapSection shows a tappable "Carte"
          pill at the same spot there — the scroll hint would double it.
          Hidden below md too: the mobile bar covers that area and swipe
          navigation is disabled there anyway. */}
      {isAuthenticated && (
        <ScrollHint
          direction="up"
          label="CARTE"
          ariaLabel="Afficher la carte"
          onClick={onEnterMap}
          className="absolute top-[18px] left-1/2 -translate-x-1/2 max-md:hidden [@media(any-pointer:coarse)]:hidden"
        />
      )}

      {/* Scroll hint — meaningless below md where swipe navigation is off. */}
      {libraryAccessible && (
        <ScrollHint
          direction="down"
          label="BIBLIOTHÈQUE"
          ariaLabel="Aller à la bibliothèque"
          onClick={onScrollToLibrary}
          className="absolute bottom-[18px] left-1/2 -translate-x-1/2 max-md:hidden"
        />
      )}
    </div>
  );
});

export default UploadSection;
