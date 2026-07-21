import { useEffect, useState, type ReactNode } from "react";
import { fetchBlobUrl, PackageStatus } from "./api";


// Loads a MinIO-backed image with the auth header via an object URL.
export function AuthedImage({
  url,
  alt,
  className,
  onClick,
}: {
  url: string;
  alt?: string;
  className?: string;
  onClick?: () => void;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let revoked: string | null = null;
    let active = true;
    fetchBlobUrl(url)
      .then((u) => {
        if (active) {
          revoked = u;
          setSrc(u);
        }
      })
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [url]);

  if (failed) return <div className={`img-fallback ${className || ""}`}>⚠︎</div>;
  if (!src) return <div className={`img-skeleton ${className || ""}`} />;
  return (
    <img src={src} alt={alt || ""} className={className} onClick={onClick} />
  );
}

const STATUS_LABEL: Record<PackageStatus, string> = {
  draft: "Draft",
  generating: "Generating",
  pending_review: "Pending review",
  approved: "Approved",
  rejected: "Rejected",
};

export function StatusBadge({ status }: { status: PackageStatus }) {
  return <span className={`badge badge-${status}`}>{STATUS_LABEL[status]}</span>;
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      {label && <span>{label}</span>}
    </div>
  );
}

export function Toast({
  message,
  kind,
  onClose,
}: {
  message: string;
  kind: "error" | "success";
  onClose: () => void;
}) {
  useEffect(() => {
    const t = setTimeout(onClose, 4000);
    return () => clearTimeout(t);
  }, [message]);
  return <div className={`toast toast-${kind}`}>{message}</div>;
}

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;

}) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose}>
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
