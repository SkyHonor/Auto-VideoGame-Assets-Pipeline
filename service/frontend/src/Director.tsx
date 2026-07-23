import { useEffect, useState } from "react";
import { api, downloadPackageZip, ImageAsset, Package, Review } from "./api";
import { AuthedImage, Modal, StatusBadge, Toast } from "./components";

const FILTERS = [
  { value: "pending_review", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "", label: "All" },
];

export default function Director() {
  const [filter, setFilter] = useState("pending_review");
  const [packages, setPackages] = useState<Package[]>([]);
  const [selected, setSelected] = useState<Package | null>(null);
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [comment, setComment] = useState("");
  const [toast, setToast] = useState<{ m: string; k: "error" | "success" } | null>(null);
  const [lightbox, setLightbox] = useState<ImageAsset | null>(null);
  const [busy, setBusy] = useState(false);

  const notify = (m: string, k: "error" | "success" = "error") => setToast({ m, k });

  const load = async () => {
    try {
      setPackages(await api.listPackages(filter || undefined));
    } catch (e: any) {
      notify(e.message);
    }
  };

  useEffect(() => {
    load();
    setSelected(null);
  }, [filter]);

  const open = async (p: Package) => {
    setSelected(p);
    setComment("");
    try {
      const [imgs, revs] = await Promise.all([
        api.listImages(p.id),
        api.listReviews(p.id),
      ]);
      setImages(imgs);
      setReviews(revs);
    } catch (e: any) {
      notify(e.message);
    }
  };

  const decide = async (decision: "approve" | "reject") => {
    if (!selected) return;
    if (decision === "reject" && !comment.trim()) {
      notify("Add a note explaining the rejection");
      return;
    }
    setBusy(true);
    try {
      const p = await api.review(selected.id, decision, comment);
      setSelected(p);
      await load();
      setReviews(await api.listReviews(p.id));
      notify(decision === "approve" ? "Package approved" : "Package rejected", "success");
    } catch (e: any) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };

  const download = async () => {
    if (!selected) return;
    try {
      await downloadPackageZip(selected.id, selected.name);
    } catch (e: any) {
      notify(e.message);
    }
  };

  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="sidebar-head">
          <h3>Review queue</h3>
        </div>
        <div className="filter-tabs">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              className={`tab ${filter === f.value ? "active" : ""}`}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <div className="pkg-list">
          {packages.length === 0 && <p className="muted">Nothing here yet.</p>}
          {packages.map((p) => (
            <button
              key={p.id}
              className={`pkg-item ${selected?.id === p.id ? "active" : ""}`}
              onClick={() => open(p)}
            >
              <div className="pkg-item-top">
                <span className="pkg-name">{p.name}</span>
                <StatusBadge status={p.status} />
              </div>
              <div className="pkg-item-sub">
                by {p.owner_username} · {p.image_count} images
              </div>
            </button>
          ))}
        </div>
      </aside>

      <section className="content">
        {!selected ? (
          <div className="empty-state">
            <div className="empty-mark">✓</div>
            <h2>Select a package to review</h2>
            <p className="muted">
              Approve on-brand asset packages or send them back with notes.
            </p>
          </div>
        ) : (
          <>
            <div className="content-head">
              <div>
                <h2>
                  {selected.name} <StatusBadge status={selected.status} />
                </h2>
                <p className="muted">
                  by {selected.owner_username} · {selected.image_count} images
                  {selected.description ? ` · ${selected.description}` : ""}
                </p>
              </div>
              <div className="head-actions">
                {selected.status === "approved" && (
                  <button className="btn btn-success" onClick={download}>
                    ⬇ Download
                  </button>
                )}
              </div>
            </div>

            {selected.status === "pending_review" && (
              <div className="card review-panel">
                <label className="field">
                  <span>Review note (required to reject)</span>
                  <textarea
                    rows={2}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="Feedback for the artist…"
                  />
                </label>
                <div className="review-actions">
                  <button
                    className="btn btn-danger"
                    disabled={busy}
                    onClick={() => decide("reject")}
                  >
                    ✕ Reject
                  </button>
                  <button
                    className="btn btn-success"
                    disabled={busy}
                    onClick={() => decide("approve")}
                  >
                    ✓ Approve
                  </button>
                </div>
              </div>
            )}

            {reviews.length > 0 && (
              <div className="history">
                <div className="history-title">
                  Review history · current version v{selected.version}
                </div>
                {reviews.map((r) => (
                  <div key={r.id} className={`history-item ${r.decision}`}>
                    <b>
                      v{r.package_version}{" "}
                      {r.decision === "approve" ? "Approved" : "Rejected"}
                    </b>{" "}
                    by {r.art_director_username}
                    {r.comment && <span> — {r.comment}</span>}
                    <span className="muted">
                      {" "}
                      · {new Date(r.created_at).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div className="gallery-head">
              <h3>
                Assets <span className="count">{images.length}</span>
              </h3>
            </div>
            <div className="gallery">
              {images.map((img) => (
                <figure
                  key={img.id}
                  className="tile"
                  onClick={() => setLightbox(img)}
                >
                  <AuthedImage url={img.url} className="tile-img" />
                  <figcaption>#{img.seed}</figcaption>
                </figure>
              ))}
            </div>
          </>
        )}
      </section>

      {lightbox && (
        <Modal title={lightbox.filename} onClose={() => setLightbox(null)}>
          <div className="lightbox">
            <AuthedImage url={lightbox.url} className="lightbox-img" />
            <dl className="meta">
              <dt>LLM prompt expansion</dt>
              <dd>{lightbox.expanded_prompt ? "On" : "Off"}</dd>
              <dt>Automatic quality check</dt>
              <dd>
                {lightbox.qa_status === "skipped"
                  ? "Off"
                  : `On — ${
                      lightbox.qa_status === "passed" ? "✓ passed" : "✕ rejected"
                    }`}
                {lightbox.qa_status !== "skipped" && lightbox.qa_reason
                  ? ` (${lightbox.qa_reason})`
                  : ""}
              </dd>
              {lightbox.qa_status !== "skipped" &&
                lightbox.clip_score != null && (
                  <>
                    <dt>Prompt-match score</dt>
                    <dd>{lightbox.clip_score.toFixed(3)}</dd>
                  </>
                )}
              {lightbox.qa_status !== "skipped" &&
                lightbox.lpips_diversity != null && (
                  <>
                    <dt>Batch diversity</dt>
                    <dd>{lightbox.lpips_diversity.toFixed(3)}</dd>
                  </>
                )}
              <dt>Prompt</dt>
              <dd>{lightbox.prompt}</dd>
              {lightbox.expanded_prompt && (
                <>
                  <dt>Prompt added by LLM</dt>
                  <dd>{lightbox.expanded_prompt}</dd>
                </>
              )}
              <dt>Negative prompt</dt>

              <dd>{lightbox.negative_prompt || "—"}</dd>
              <dt>Seed</dt>
              <dd>{lightbox.seed}</dd>
              <dt>Size</dt>
              <dd>
                {lightbox.width}×{lightbox.height}
              </dd>
              <dt>Workflow / LoRA</dt>
              <dd>{lightbox.workflow_type}</dd>
              <dt>Sampler</dt>
              <dd>
                {lightbox.params?.sampler_name ?? "—"} ·{" "}
                {lightbox.params?.scheduler ?? "—"}
              </dd>
              <dt>Steps / CFG</dt>
              <dd>
                {lightbox.params?.steps ?? "—"} steps · CFG{" "}
                {lightbox.params?.cfg ?? "—"}
              </dd>
              <dt>Denoise</dt>
              <dd>{lightbox.params?.denoise ?? "—"}</dd>
              <dt>LoRA strength</dt>
              <dd>{lightbox.params?.style_lora_strength ?? "—"}</dd>
              <dt>Quality prefix</dt>
              <dd>{lightbox.params?.positive_prefix ?? "—"}</dd>
              <dt>File size</dt>
              <dd>{(lightbox.size_bytes / 1024).toFixed(1)} KB</dd>
              <dt>Created</dt>
              <dd>{new Date(lightbox.created_at).toLocaleString()}</dd>
              <dt>Asset ID</dt>
              <dd>{lightbox.id}</dd>
            </dl>
          </div>
        </Modal>
      )}
      {toast && (
        <Toast message={toast.m} kind={toast.k} onClose={() => setToast(null)} />
      )}
    </div>
  );
}
