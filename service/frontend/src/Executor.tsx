import { useEffect, useRef, useState } from "react";
import {
  api,
  downloadPackageZip,
  GenParams,
  ImageAsset,
  Job,
  Package,
  Review,
} from "./api";
import { AuthedImage, Modal, Spinner, StatusBadge, Toast } from "./components";

const SAMPLERS = [
  "euler",
  "euler_ancestral",
  "dpmpp_2m",
  "dpmpp_2m_sde",
  "dpmpp_sde",
  "ddim",
  "uni_pc",
];
const SCHEDULERS = ["normal", "karras", "exponential", "sgm_uniform", "simple"];
const WORKFLOWS = [
  { value: "character", label: "Character  ·  @sltn" },
  { value: "props", label: "Props / Icons  ·  @spll_icn" },
];

const DEFAULT_PARAMS: GenParams = {
  workflow_type: "character",
  width: 1024,
  height: 1024,
  steps: 12,
  cfg: 2.0,
  sampler_name: "euler",
  scheduler: "simple",
  denoise: 1.0,
  seed: null,
  style_lora_strength: 0.85,
  positive_prefix: "masterpiece, best quality, highly detailed",
  negative_prompt:
    "worst quality, low quality, blurry, jpeg artifacts, lowres, bad anatomy, extra limbs, watermark, signature, text",
};

export default function Executor() {
  const [packages, setPackages] = useState<Package[]>([]);
  const [selected, setSelected] = useState<Package | null>(null);
  const [images, setImages] = useState<ImageAsset[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [toast, setToast] = useState<{ m: string; k: "error" | "success" } | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [lightbox, setLightbox] = useState<ImageAsset | null>(null);
  const [imgBusy, setImgBusy] = useState(false);

  const [rejected, setRejected] = useState<ImageAsset[]>([]);
  const [showRejected, setShowRejected] = useState(false);

  const [prompt, setPrompt] = useState("");
  const [batch, setBatch] = useState(4);
  const [llm, setLlm] = useState(false);
  const [qa, setQa] = useState(false);
  const [params, setParams] = useState<GenParams>(DEFAULT_PARAMS);

  const [job, setJob] = useState<Job | null>(null);
  const pollRef = useRef<number | null>(null);

  const notify = (m: string, k: "error" | "success" = "error") => setToast({ m, k });
  const setP = (patch: Partial<GenParams>) =>
    setParams((prev) => ({ ...prev, ...patch }));

  const loadPackages = async () => {
    try {
      setPackages(await api.listPackages());
    } catch (e: any) {
      notify(e.message);
    }
  };

  useEffect(() => {
    loadPackages();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  // Split the full asset list (include_failed) into the visible gallery and
  // the QA-rejected bucket the executor can review separately.
  const applyImages = (all: ImageAsset[]) => {
    setImages(all.filter((i) => i.qa_status !== "failed"));
    setRejected(all.filter((i) => i.qa_status === "failed"));
  };

  const openPackage = async (p: Package) => {
    setSelected(p);
    setShowRejected(false);
    try {
      const [imgs, revs] = await Promise.all([
        api.listImages(p.id, true),
        api.listReviews(p.id),
      ]);
      applyImages(imgs);
      setReviews(revs);
    } catch (e: any) {
      notify(e.message);
    }
  };

  const refreshSelected = async () => {
    if (!selected) return;
    const p = await api.getPackage(selected.id);
    setSelected(p);
    const [imgs, revs] = await Promise.all([
      api.listImages(p.id, true),
      api.listReviews(p.id),
    ]);
    applyImages(imgs);
    setReviews(revs);
    setPackages((prev) => prev.map((x) => (x.id === p.id ? p : x)));
  };

  const restoreAsset = async (img: ImageAsset) => {
    try {
      const restored = await api.restoreImage(img.id);
      // Move it out of the rejected bucket into the visible gallery.
      setRejected((prev) => prev.filter((x) => x.id !== img.id));
      setImages((prev) => [restored, ...prev]);
      setSelected((prev) =>
        prev ? { ...prev, image_count: prev.image_count + 1 } : prev
      );
      setPackages((prev) =>
        prev.map((p) =>
          p.id === img.package_id
            ? { ...p, image_count: p.image_count + 1 }
            : p
        )
      );
      setLightbox(null);
      notify("Asset added back to the package", "success");
    } catch (e: any) {
      notify(e.message);
    }
  };


  const deleteAsset = async (img: ImageAsset) => {
    if (!confirm("Delete this asset from the package?")) return;
    // Optimistic UI: drop it from the grid, counters and cover immediately.
    const prevImages = images;
    const prevSelected = selected;
    const prevPackages = packages;
    setLightbox(null);
    setImages((prev) => prev.filter((x) => x.id !== img.id));
    setSelected((prev) =>
      prev ? { ...prev, image_count: Math.max(0, prev.image_count - 1) } : prev
    );
    setPackages((prev) =>
      prev.map((p) =>
        p.id === img.package_id
          ? { ...p, image_count: Math.max(0, p.image_count - 1) }
          : p
      )
    );
    try {
      await api.deleteImage(img.id);
      notify("Asset deleted", "success");
    } catch (e: any) {
      // Roll back on failure.
      setImages(prevImages);
      setSelected(prevSelected);
      setPackages(prevPackages);
      notify(e.message);
    }
  };

  const regenerateAsset = async (img: ImageAsset) => {
    setImgBusy(true);
    try {
      const j = await api.regenerateImage(img.id);
      setLightbox(null);
      setJob(j);
      startPolling(j.id);
      setSelected((prev) => (prev ? { ...prev, status: "generating" } : prev));
      notify("Re-rolling this asset…", "success");
    } catch (e: any) {
      notify(e.message);
    } finally {
      setImgBusy(false);
    }
  };

  const deletePackage = async () => {
    if (!selected) return;
    if (!confirm(`Delete package "${selected.name}" and all its assets?`)) return;
    // Optimistic UI: remove it from the sidebar and clear the view at once.
    const prevPackages = packages;
    const prevSelected = selected;
    const id = selected.id;
    setPackages((prev) => prev.filter((p) => p.id !== id));
    setSelected(null);
    setImages([]);
    setReviews([]);
    try {
      await api.deletePackage(id);
      notify("Package deleted", "success");
    } catch (e: any) {
      // Roll back on failure.
      setPackages(prevPackages);
      setSelected(prevSelected);
      notify(e.message);
    }
  };

  const createPackage = async (name: string, desc: string) => {
    try {
      const p = await api.createPackage(name, desc);
      setShowCreate(false);
      await loadPackages();
      openPackage(p);
      notify("Package created", "success");
    } catch (e: any) {
      notify(e.message);
    }
  };

  const startPolling = (jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const j = await api.getJob(jobId);
        setJob(j);
        if (j.status === "completed" || j.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          if (j.status === "completed") {
            await refreshSelected();
            notify("Generation complete", "success");
          } else {
            notify(j.error || "Generation failed");
          }
          setTimeout(() => setJob(null), 1200);
        }
      } catch {
        /* keep polling on transient errors */
      }
    }, 1500);
  };

  const generate = async () => {
    if (!selected) return;
    if (!prompt.trim()) {
      notify("Enter a prompt first");
      return;
    }
    try {
      const j = await api.generate(selected.id, {
        prompt,
        batch_size: batch,
        llm_expand: llm,
        qa_check: qa,
        params,
      });

      setJob(j);
      startPolling(j.id);
      setSelected({ ...selected, status: "generating" });
    } catch (e: any) {
      notify(e.message);
    }
  };

  const submit = async () => {
    if (!selected) return;
    try {
      const p = await api.submit(selected.id);
      setSelected(p);
      setPackages((prev) => prev.map((x) => (x.id === p.id ? p : x)));
      notify("Sent to the art director for review", "success");
    } catch (e: any) {
      notify(e.message);
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

  const busyGen = job && (job.status === "pending" || job.status === "running");
  const canSubmit =
    selected &&
    (selected.status === "draft" || selected.status === "rejected") &&
    selected.image_count > 0;
  const locked =
    selected &&
    (selected.status === "pending_review" || selected.status === "approved");

  return (
    <div className="workspace">
      <aside className="sidebar">
        <div className="sidebar-head">
          <h3>My packages</h3>
          <button className="btn btn-primary btn-sm" onClick={() => setShowCreate(true)}>
            + New
          </button>
        </div>
        <div className="pkg-list">
          {packages.length === 0 && (
            <p className="muted">No packages yet. Create one to start generating.</p>
          )}
          {packages.map((p) => (
            <button
              key={p.id}
              className={`pkg-item ${selected?.id === p.id ? "active" : ""}`}
              onClick={() => openPackage(p)}
            >
              <div className="pkg-item-top">
                <span className="pkg-name">{p.name}</span>
                <StatusBadge status={p.status} />
              </div>
              <div className="pkg-item-sub">{p.image_count} images</div>
            </button>
          ))}
        </div>
      </aside>

      <section className="content">
        {!selected ? (
          <div className="empty-state">
            <div className="empty-mark">◈</div>
            <h2>Select or create a package</h2>
            <p className="muted">
              Packages group generated assets for review and delivery.
            </p>
          </div>
        ) : (
          <>
            <div className="content-head">
              <div>
                <h2>
                  {selected.name} <StatusBadge status={selected.status} />
                </h2>
                {selected.description && (
                  <p className="muted">{selected.description}</p>
                )}
              </div>
              <div className="head-actions">
                {selected.status === "approved" && (
                  <button className="btn btn-success" onClick={download}>
                    ⬇ Download
                  </button>
                )}
                {canSubmit && (
                  <button className="btn btn-primary" onClick={submit}>
                    Send for review
                  </button>
                )}
                {selected.status !== "pending_review" && (
                  <button className="btn btn-danger" onClick={deletePackage}>
                    🗑 Delete package
                  </button>
                )}
              </div>
            </div>

            {selected.status === "rejected" && selected.review_comment && (
              <div className="notice notice-reject">
                <b>Rejected by {selected.reviewed_by}:</b> {selected.review_comment}
              </div>
            )}
            {selected.status === "pending_review" && (
              <div className="notice notice-pending">
                Awaiting art-director review — editing is locked.
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

            {!locked && (
              <div className="card gen-panel">
                <div className="gen-main">
                  <label className="field">
                    <span>Prompt</span>
                    <textarea
                      rows={3}
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="e.g. a stylized goblin warrior holding a rusty axe"
                    />
                  </label>
                  <label className="field">
                    <span>Quality prefix (prepended to prompt)</span>
                    <input
                      value={params.positive_prefix}
                      onChange={(e) => setP({ positive_prefix: e.target.value })}
                    />
                  </label>
                  <label className="field">
                    <span>Negative prompt</span>
                    <textarea
                      rows={2}
                      value={params.negative_prompt}
                      onChange={(e) => setP({ negative_prompt: e.target.value })}
                    />
                  </label>
                </div>

                <div className="gen-params">
                  <label className="field">
                    <span>Workflow / Style LoRA</span>
                    <select
                      value={params.workflow_type}
                      onChange={(e) => setP({ workflow_type: e.target.value })}
                    >
                      {WORKFLOWS.map((w) => (
                        <option key={w.value} value={w.value}>
                          {w.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="field-row">
                    <label className="field">
                      <span>Width</span>
                      <input
                        type="number"
                        min={256}
                        max={2048}
                        step={64}
                        value={params.width}
                        onChange={(e) => setP({ width: +e.target.value })}
                      />
                    </label>
                    <label className="field">
                      <span>Height</span>
                      <input
                        type="number"
                        min={256}
                        max={2048}
                        step={64}
                        value={params.height}
                        onChange={(e) => setP({ height: +e.target.value })}
                      />
                    </label>
                  </div>

                  <div className="field-row">
                    <label className="field">
                      <span>Steps: {params.steps}</span>
                      <input
                        type="range"
                        min={5}
                        max={60}
                        value={params.steps}
                        onChange={(e) => setP({ steps: +e.target.value })}
                      />
                    </label>
                    <label className="field">
                      <span>CFG: {params.cfg}</span>
                      <input
                        type="range"
                        min={1}
                        max={12}
                        step={0.5}
                        value={params.cfg}
                        onChange={(e) => setP({ cfg: +e.target.value })}
                      />
                    </label>
                  </div>

                  <div className="field-row">
                    <label className="field">
                      <span>Sampler</span>
                      <select
                        value={params.sampler_name}
                        onChange={(e) => setP({ sampler_name: e.target.value })}
                      >
                        {SAMPLERS.map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Scheduler</span>
                      <select
                        value={params.scheduler}
                        onChange={(e) => setP({ scheduler: e.target.value })}
                      >
                        {SCHEDULERS.map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </label>
                  </div>

                  <div className="field-row">
                    <label className="field">
                      <span>Batch size: {batch}</span>
                      <input
                        type="range"
                        min={1}
                        max={16}
                        value={batch}
                        onChange={(e) => setBatch(+e.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>LoRA strength: {params.style_lora_strength}</span>
                      <input
                        type="range"
                        min={0}
                        max={1.5}
                        step={0.05}
                        value={params.style_lora_strength}
                        onChange={(e) =>
                          setP({ style_lora_strength: +e.target.value })
                        }
                      />
                    </label>
                  </div>

                  <div className="field-row">
                    <label className="field">
                      <span>Seed (blank = random)</span>
                      <input
                        type="number"
                        value={params.seed ?? ""}
                        placeholder="random"
                        onChange={(e) =>
                          setP({
                            seed: e.target.value === "" ? null : +e.target.value,
                          })
                        }
                      />
                    </label>
                    <label className="toggle">
                      <input
                        type="checkbox"
                        checked={llm}
                        onChange={(e) => setLlm(e.target.checked)}
                      />
                      <span>LLM prompt expansion</span>
                    </label>
                  </div>

                  <div className="field-row">
                    <label className="toggle" title="Score every image with CLIP (prompt match) and, for batches of 4+, LPIPS (drop near-duplicates). Rejected images are kept but hidden below.">
                      <input
                        type="checkbox"
                        checked={qa}
                        onChange={(e) => setQa(e.target.checked)}
                      />
                      <span>Auto quality check (CLIP + LPIPS)</span>
                    </label>
                  </div>
                </div>


                <div className="gen-actions">
                  <button
                    className="btn btn-primary btn-lg"
                    onClick={generate}
                    disabled={!!busyGen}
                  >
                    {busyGen
                      ? `Generating… (${job?.status})`
                      : `✨ Generate ${batch > 1 ? `${batch} images` : "image"}`}
                  </button>
                </div>
              </div>
            )}

            <div className="gallery-head">
              <h3>
                Assets <span className="count">{images.length}</span>
              </h3>
            </div>
            {busyGen && <Spinner label="Workers are rendering your batch…" />}
            {images.length === 0 && !busyGen ? (
              <p className="muted">No assets yet — generate your first batch above.</p>
            ) : (
              <div className="gallery">
                {images.map((img) => (
                  <figure
                    key={img.id}
                    className="tile"
                    onClick={() => setLightbox(img)}
                  >
                    <AuthedImage url={img.url} className="tile-img" />
                    {img.qa_status === "passed" &&
                      img.clip_score != null && (
                        <span
                          className="qa-badge qa-pass"
                          title="Passed automatic QA"
                        >
                          ✓ QA {img.clip_score.toFixed(2)}
                        </span>
                      )}
                    <figcaption>#{img.seed}</figcaption>
                  </figure>
                ))}
              </div>
            )}

            {rejected.length > 0 && !locked && (
              <div className="rejected-section">
                <button
                  className="rejected-toggle"
                  onClick={() => setShowRejected((v) => !v)}
                >
                  {showRejected ? "▾" : "▸"} QA-rejected{" "}
                  <span className="count">{rejected.length}</span>
                  <span className="muted">
                    {" "}
                    · hidden from the package — review & add back if needed
                  </span>
                </button>
                {showRejected && (
                  <div className="gallery">
                    {rejected.map((img) => (
                      <figure
                        key={img.id}
                        className="tile tile-rejected"
                        onClick={() => setLightbox(img)}
                      >
                        <AuthedImage url={img.url} className="tile-img" />
                        <span
                          className="qa-badge qa-fail"
                          title={img.qa_reason || "Rejected by QA"}
                        >
                          ✕ QA
                        </span>
                        <figcaption>{img.qa_reason || "rejected"}</figcaption>
                      </figure>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>

        )}
      </section>

      {showCreate && (
        <CreatePackageModal
          onClose={() => setShowCreate(false)}
          onCreate={createPackage}
        />
      )}
      {lightbox && (
        <Modal title={lightbox.filename} onClose={() => setLightbox(null)}>
          <div className="lightbox">
            <AuthedImage url={lightbox.url} className="lightbox-img" />
            <dl className="meta">
              <dt>Prompt</dt>
              <dd>{lightbox.prompt}</dd>
              {lightbox.expanded_prompt && (
                <>
                  <dt>Expanded</dt>
                  <dd>{lightbox.expanded_prompt}</dd>
                </>
              )}
              <dt>Seed</dt>
              <dd>{lightbox.seed}</dd>
              <dt>Size</dt>
              <dd>
                {lightbox.width}×{lightbox.height}
              </dd>
              <dt>Workflow</dt>
              <dd>{lightbox.workflow_type}</dd>
              {lightbox.qa_status !== "skipped" && (
                <>
                  <dt>QA verdict</dt>
                  <dd>
                    {lightbox.qa_status === "passed" ? "✓ Passed" : "✕ Rejected"}
                    {lightbox.qa_reason ? ` — ${lightbox.qa_reason}` : ""}
                  </dd>
                  {lightbox.clip_score != null && (
                    <>
                      <dt>CLIP score</dt>
                      <dd>{lightbox.clip_score.toFixed(3)}</dd>
                    </>
                  )}
                  {lightbox.lpips_diversity != null && (
                    <>
                      <dt>LPIPS diversity</dt>
                      <dd>{lightbox.lpips_diversity.toFixed(3)}</dd>
                    </>
                  )}
                </>
              )}
            </dl>
            {!locked && (
              <div className="lightbox-actions">
                {lightbox.qa_status === "failed" && (
                  <button
                    className="btn btn-success"
                    disabled={imgBusy}
                    onClick={() => restoreAsset(lightbox)}
                  >
                    ＋ Add to package
                  </button>
                )}
                <button
                  className="btn btn-secondary"
                  disabled={imgBusy}
                  onClick={() => regenerateAsset(lightbox)}
                >
                  ♻ Regenerate
                </button>
                <button
                  className="btn btn-danger"
                  disabled={imgBusy}
                  onClick={() => deleteAsset(lightbox)}
                >
                  🗑 Delete asset
                </button>
              </div>
            )}

          </div>
        </Modal>
      )}
      {toast && (
        <Toast message={toast.m} kind={toast.k} onClose={() => setToast(null)} />
      )}
    </div>
  );
}

function CreatePackageModal({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (name: string, desc: string) => void;
}) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  return (
    <Modal title="New package" onClose={onClose}>
      <div className="form">
        <label className="field">
          <span>Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            placeholder="Goblin enemy set"
          />
        </label>
        <label className="field">
          <span>Description</span>
          <textarea rows={3} value={desc} onChange={(e) => setDesc(e.target.value)} />
        </label>
        <button
          className="btn btn-primary btn-block"
          disabled={!name.trim()}
          onClick={() => onCreate(name, desc)}
        >
          Create package
        </button>
      </div>
    </Modal>
  );
}
