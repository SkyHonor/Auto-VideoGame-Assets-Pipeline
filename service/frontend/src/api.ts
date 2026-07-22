// Thin, typed client for the AssetForge REST API.
export type Role = "executor" | "art-director";
export type PackageStatus =
  | "draft"
  | "generating"
  | "pending_review"
  | "approved"
  | "rejected";
export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface User {
  id: string;
  username: string;
  full_name: string;
  role: Role;
}
export interface Token extends User {
  access_token: string;
  token_type: string;
}
export interface Package {
  id: string;
  name: string;
  description: string;
  owner_username: string;
  status: PackageStatus;
  image_count: number;
  cover_image_id: string | null;
  version: number;
  review_comment: string | null;
  reviewed_by: string | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  reviewed_at: string | null;
}
export interface ImageAsset {
  id: string;
  package_id: string;
  job_id: string;
  filename: string;
  prompt: string;
  negative_prompt: string;
  expanded_prompt: string | null;
  seed: number;
  width: number;
  height: number;
  workflow_type: string;
  size_bytes: number;
  params: Record<string, any>;
  created_at: string;
  url: string;
}
export interface Job {
  id: string;
  package_id: string;
  prompt: string;
  expanded_prompt: string | null;
  llm_expand: boolean;
  batch_size: number;
  params: Record<string, any>;
  status: JobStatus;
  error: string | null;
  image_ids: string[];
  created_at: string;
}
export interface GenParams {
  workflow_type: string;
  width: number;
  height: number;
  steps: number;
  cfg: number;
  sampler_name: string;
  scheduler: string;
  denoise: number;
  seed: number | null;
  style_lora_strength: number;
  positive_prefix: string;
  negative_prompt: string;
}
export interface Review {
  id: string;
  package_id: string;
  art_director_username: string;
  decision: "approve" | "reject";
  comment: string;
  package_version: number;
  created_at: string;
}

const BASE = "/api/v1";
const TOKEN_KEY = "assetforge_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) =>
  t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY);

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as any) };
  const tk = getToken();
  if (tk) headers["Authorization"] = `Bearer ${tk}`;
  if (opts.body) headers["Content-Type"] = "application/json";
  const res = await fetch(`${BASE}${path}`, { ...opts, headers });
  if (res.status === 401) setToken(null);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const text = await res.text();
      if (text) msg = (JSON.parse(text).detail as string) || text || msg;
    } catch {}
    throw new Error(msg);
  }
  // 204 No Content (e.g. DELETE) or an empty body: nothing to parse.
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  return (ct.includes("application/json") ? JSON.parse(text) : (text as any)) as T;
}

export const api = {
  login: (username: string, password: string) =>
    req<Token>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  me: () => req<User>("/auth/me"),
  listPackages: (status?: string) =>
    req<Package[]>(`/packages${status ? `?status=${status}` : ""}`),
  getPackage: (id: string) => req<Package>(`/packages/${id}`),
  createPackage: (name: string, description: string) =>
    req<Package>("/packages", {
      method: "POST",
      body: JSON.stringify({ name, description }),
    }),
  listImages: (id: string) => req<ImageAsset[]>(`/packages/${id}/images`),
  generate: (id: string, body: any) =>
    req<Job>(`/packages/${id}/generate`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getJob: (id: string) => req<Job>(`/jobs/${id}`),
  submit: (id: string) => req<Package>(`/packages/${id}/submit`, { method: "POST" }),
  review: (id: string, decision: string, comment: string) =>
    req<Package>(`/packages/${id}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, comment }),
    }),
  listReviews: (id: string) => req<Review[]>(`/packages/${id}/reviews`),
  deletePackage: (id: string) =>
    req<void>(`/packages/${id}`, { method: "DELETE" }),
  deleteImage: (id: string) => req<void>(`/images/${id}`, { method: "DELETE" }),
  regenerateImage: (id: string) =>
    req<Job>(`/images/${id}/regenerate`, { method: "POST" }),
  downloadUrl: (id: string) => `${BASE}/packages/${id}/download`,
};

// Authenticated binary fetch -> object URL (used for <img> and downloads).
export async function fetchBlobUrl(url: string): Promise<string> {
  const tk = getToken();
  const res = await fetch(url, {
    headers: tk ? { Authorization: `Bearer ${tk}` } : {},
  });
  if (!res.ok) throw new Error("image load failed");
  return URL.createObjectURL(await res.blob());
}

export async function downloadPackageZip(id: string, name: string) {
  const tk = getToken();
  const res = await fetch(api.downloadUrl(id), {
    headers: tk ? { Authorization: `Bearer ${tk}` } : {},
  });
  if (!res.ok) throw new Error("download failed");
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${name.replace(/\s+/g, "_")}.zip`;
  a.click();
  URL.revokeObjectURL(a.href);
}
