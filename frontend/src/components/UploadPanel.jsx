import { useEffect, useRef, useState } from "react";

const MAX_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = ["image/jpeg", "image/png"];
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const SHRINK_ABOVE_BYTES = 4 * 1024 * 1024; // phone photos are often close to (or over) the 5 MB limit
const SHRINK_MAX_SIDE = 2200;

/** Re-encode a very large photo as a smaller JPEG in the browser. Falls back to the original on any problem. */
async function shrinkIfLarge(file) {
  if (file.size <= SHRINK_ABOVE_BYTES) return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, SHRINK_MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close?.();
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
    if (!blob || blob.size >= file.size) return file;
    return new File([blob], file.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" });
  } catch {
    return file;
  }
}

// Phones and tablets get a "Take a photo" button that opens the camera directly.
const hasTouchScreen = typeof window !== "undefined" && window.matchMedia?.("(pointer: coarse)").matches;

export default function UploadPanel({ t, loading, error, onSubmit, onFileChange }) {
  const [email, setEmail] = useState("");
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState(null);
  const inputRef = useRef(null);
  const cameraRef = useRef(null);

  // Let the parent know about the selected file so it can show a preview next to the result.
  useEffect(() => {
    onFileChange(file);
  }, [file, onFileChange]);

  async function chooseFile(picked) {
    if (!picked) return;
    if (!ALLOWED_TYPES.includes(picked.type)) {
      setFile(null);
      setLocalError("LOCAL_TYPE");
      return;
    }
    const candidate = await shrinkIfLarge(picked);
    if (!ALLOWED_TYPES.includes(candidate.type)) {
      setFile(null);
      setLocalError("LOCAL_TYPE");
      return;
    }
    if (candidate.size > MAX_BYTES) {
      setFile(null);
      setLocalError("LOCAL_SIZE");
      return;
    }
    setLocalError(null);
    setFile(candidate);
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files?.[0]);
  }

  function handleSubmit(event) {
    event.preventDefault();
    if (!EMAIL_PATTERN.test(email.trim())) {
      setLocalError("LOCAL_EMAIL");
      return;
    }
    if (!file) {
      setLocalError("LOCAL_NO_FILE");
      return;
    }
    setLocalError(null);
    onSubmit({ email: email.trim(), file });
  }

  const shownError = localError ? t.errors[localError] : error;

  return (
    <section className="card" aria-labelledby="verify-title">
      <h2 id="verify-title" className="card-title">
        {t.verifyTitle}
      </h2>

      <form onSubmit={handleSubmit} noValidate>
        <label className="field-label" htmlFor="email">
          {t.email}
        </label>
        <input
          id="email"
          type="email"
          className="input"
          value={email}
          placeholder={t.emailPlaceholder}
          autoComplete="email"
          disabled={loading}
          onChange={(event) => setEmail(event.target.value)}
        />

        <span className="field-label" id="document-label">
          {t.document}
        </span>
        <div
          className={`dropzone${dragging ? " dragging" : ""}${file ? " has-file" : ""}`}
          role="button"
          tabIndex={0}
          aria-labelledby="document-label"
          onClick={() => !loading && inputRef.current?.click()}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              inputRef.current?.click();
            }
          }}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
        >
          <span className="drop-icon" aria-hidden="true">
            ↑
          </span>
          {file ? (
            <>
              <strong className="file-name">{file.name}</strong>
              <span className="muted">{t.change}</span>
            </>
          ) : (
            <>
              <span>{t.dropHint}</span>
              <span className="muted small">{t.dropFormats}</span>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg"
            hidden
            onChange={(event) => chooseFile(event.target.files?.[0])}
          />
        </div>

        {hasTouchScreen && (
          <>
            <button
              type="button"
              className="button button-secondary button-camera"
              disabled={loading}
              onClick={() => cameraRef.current?.click()}
            >
              📷 {t.takePhoto}
            </button>
            <input
              ref={cameraRef}
              type="file"
              accept="image/png,image/jpeg"
              capture="environment"
              hidden
              onChange={(event) => chooseFile(event.target.files?.[0])}
            />
          </>
        )}

        {shownError && (
          <p className="alert" role="alert">
            {shownError}
          </p>
        )}

        <button type="submit" className="button" disabled={loading}>
          {loading && <span className="spinner" aria-hidden="true" />}
          {loading ? t.processing : t.process}
        </button>
      </form>
    </section>
  );
}
