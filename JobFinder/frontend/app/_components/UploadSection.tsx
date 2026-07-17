"use client";

import { useCallback, useRef, useState } from "react";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";

import apiClient from "@/lib/api/client";
import { loginRequest } from "@/lib/auth/msalConfig";
import { cn } from "@/lib/utils";

import OrbitAnimation from "./OrbitAnimation";

type AnimState = "idle" | "uploaded" | "done";

const MAX_PDF_BYTES = 10 * 1024 * 1024;

interface Props {
  onUploadComplete?: (cvId: string) => void;
  onAnimationComplete?: (thumbnailUrl: string) => void;
  libraryAccessible?: boolean;
}

export default function UploadSection({ onUploadComplete, onAnimationComplete, libraryAccessible = false }: Props) {
  const [animState, setAnimState]       = useState<AnimState>("idle");
  const [isDragging, setIsDragging]     = useState(false);
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const fileInputRef                    = useRef<HTMLInputElement>(null);
  const pendingRevokeRef                = useRef<string | null>(null);
  const { instance }                    = useMsal();
  const isAuthenticated                 = useIsAuthenticated();
  const mousePosRef                     = useRef<{ x: number; y: number } | null>(null);
  const clickFlashRef                   = useRef<number>(0);

  const handleFile = useCallback(
    (file: File): void => {
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
        .then((res) => { onUploadComplete?.(res.data.cv_id); })
        .catch(() => { /* silent — library card shows regardless */ });
    },
    [isAuthenticated, instance, onUploadComplete],
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
      clickFlashRef.current = 1.0;
      fileInputRef.current?.click();
    }
  }, [animState, isAuthenticated, instance]);

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
        <p className="pointer-events-none absolute bottom-[88px] left-0 right-0 text-center text-xs text-hint">
          Déposez votre CV (PDF) · ou cliquez pour parcourir
        </p>
      )}

      {/* Gated like the map mode itself (HomeMapSection): the zone is tied
          to the profile, which requires being signed in. */}
      {/* Hidden on coarse pointers: HomeMapSection shows a tappable "Carte"
          pill at the same spot there — the scroll hint would double it. */}
      {isAuthenticated && (
        <div className="pointer-events-none absolute top-[18px] left-1/2 flex -translate-x-1/2 flex-col items-center gap-1 [@media(any-pointer:coarse)]:hidden">
          <span aria-hidden="true" className="animate-bounce text-sm text-hint">⌃</span>
          <span className="text-[9px] tracking-widest text-label">CARTE</span>
        </div>
      )}

      {libraryAccessible && (
        <div className="pointer-events-none absolute bottom-[18px] left-1/2 flex -translate-x-1/2 flex-col items-center gap-1">
          <span className="text-[9px] tracking-widest text-label">BIBLIOTHÈQUE</span>
          <span aria-hidden="true" className="animate-bounce text-sm text-hint">⌄</span>
        </div>
      )}
    </div>
  );
}
