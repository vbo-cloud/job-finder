"use client";

import { useCallback, useRef, useState } from "react";
import { useIsAuthenticated, useMsal } from "@azure/msal-react";

import apiClient from "@/lib/api/client";
import { loginRequest } from "@/lib/auth/msalConfig";
import { cn } from "@/lib/utils";

import AuthButton from "./AuthButton";
import OrbitAnimation from "./OrbitAnimation";

type AnimState = "idle" | "uploaded" | "done";

const MAX_PDF_BYTES = 10 * 1024 * 1024;

interface Props {
  onReadyForLibrary?: (dataUrl?: string | null) => void;
}

export default function UploadSection({ onReadyForLibrary }: Props) {
  const [animState, setAnimState]       = useState<AnimState>("idle");
  const [isDragging, setIsDragging]     = useState(false);
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const fileInputRef                    = useRef<HTMLInputElement>(null);
  const pendingFilenameRef              = useRef<string>("");
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
      pendingFilenameRef.current = file.name;
      const objectUrl = URL.createObjectURL(file);
      pendingRevokeRef.current = objectUrl; // revoked in handleThumbnailReady after pdfjs reads it
      setThumbnailUrl(objectUrl);
      setAnimState("uploaded");
      const formData = new FormData();
      formData.append("file", file);
      // Upload runs in background — done state driven by onThumbnailReady, not the network.
      // No .finally() revoke here: pdfjs must read the URL first (race condition fix).
      apiClient
        .post<void>("/cv/upload", formData)
        .catch(() => { /* silent — library card shows regardless */ });
    },
    [isAuthenticated, instance],
  );

  const handleThumbnailReady = useCallback((dataUrl: string | null) => {
    // pdfjs has finished reading the objectUrl — safe to revoke now
    if (pendingRevokeRef.current) {
      URL.revokeObjectURL(pendingRevokeRef.current);
      pendingRevokeRef.current = null;
    }
    setAnimState("done");
    onReadyForLibrary?.(dataUrl);
  }, [onReadyForLibrary]);

  const handleDoneComplete = useCallback(() => {
    setAnimState("idle");
    setThumbnailUrl(null);
  }, []);

  const handleClick = useCallback((e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const cx = rect.width / 2;
    const cy = rect.height / 2;
    if (Math.abs(x - cx) > 28 || Math.abs(y - cy) > 34) return;
    if (animState === "idle") {
      clickFlashRef.current = 1.0;
      fileInputRef.current?.click();
    }
  }, [animState]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  return (
    <section className="relative h-dvh snap-start overflow-hidden bg-[#0a0a0f]">
      <OrbitAnimation
        state={animState}
        thumbnailUrl={thumbnailUrl}
        onThumbnailReady={handleThumbnailReady}
        onDoneComplete={handleDoneComplete}
        mousePosRef={mousePosRef}
        clickFlashRef={clickFlashRef}
      />

      <div className="absolute right-3 top-2 z-10">
        <AuthButton />
      </div>

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
        className={cn("absolute inset-0", isDragging && "ring-1 ring-white/10")}
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
        <p className="pointer-events-none absolute bottom-[88px] left-0 right-0 text-center text-xs text-white/25">
          Déposez votre CV (PDF) · ou cliquez pour parcourir
        </p>
      )}

      <div className="pointer-events-none absolute bottom-9 left-1/2 flex -translate-x-1/2 flex-col items-center gap-1">
        <span className="text-[9px] tracking-widest text-white/20">BIBLIOTHÈQUE</span>
        <span className="animate-bounce text-sm text-white/25">⌄</span>
      </div>
    </section>
  );
}
