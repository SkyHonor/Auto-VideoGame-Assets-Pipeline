import { useEffect, useState } from "react";
import { api, getToken, setToken, User } from "./api";
import { Spinner } from "./components";
import Executor from "./Executor";
import Director from "./Director";

const DEMO = [
  {
    role: "Executor",
    username: "artist",
    password: "artist123",
    desc: "Write prompts & generate assets",
  },
  {
    role: "Art Director",
    username: "director",
    password: "director123",
    desc: "Review & approve packages",
  },
];

function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [username, setU] = useState("artist");
  const [password, setP] = useState("artist123");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async (e: any) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const t = await api.login(username, password);
      setToken(t.access_token);
      onLogin(await api.me());
    } catch (ex: any) {
      setErr(ex.message || "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login">
      <div className="login-brand">
        <div className="brand-mark">◈</div>
        <h1>AssetForge</h1>
        <p className="brand-tag">On-prem generative studio for game art</p>
        <ul className="brand-feats">
          <li>⚡ Batch generation on a local ComfyUI cluster</li>
          <li>🧠 Optional LLM prompt expansion</li>
          <li>🗂 MinIO-backed asset library with metadata</li>
          <li>✅ Art-director review &amp; delivery workflow</li>
        </ul>
      </div>
      <div className="login-panel">
        <form className="card login-card" onSubmit={submit}>
          <h2>Sign in</h2>
          <label className="field">
            <span>Username</span>
            <input value={username} onChange={(e) => setU(e.target.value)} autoFocus />
          </label>
          <label className="field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setP(e.target.value)}
            />
          </label>
          {err && <div className="form-error">{err}</div>}
          <button className="btn btn-primary btn-block" disabled={busy}>
            {busy ? "Signing in…" : "Enter studio"}
          </button>
          <div className="demo-accounts">
            <span className="demo-title">Demo accounts (click to fill)</span>
            {DEMO.map((d) => (
              <button
                type="button"
                key={d.username}
                className="demo-chip"
                onClick={() => {
                  setU(d.username);
                  setP(d.password);
                }}
              >
                <b>{d.role}</b>
                <small>{d.desc}</small>
              </button>
            ))}
          </div>
        </form>
      </div>
    </div>
  );
}

function TopBar({ user, onLogout }: { user: User; onLogout: () => void }) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <span className="brand-mark small">◈</span> AssetForge
      </div>
      <div className="topbar-right">
        <span className={`role-pill role-${user.role}`}>
          {user.role === "executor" ? "Executor" : "Art Director"}
        </span>
        <span className="topbar-user">{user.full_name || user.username}</span>
        <button className="btn btn-ghost" onClick={onLogout}>
          Log out
        </button>
      </div>
    </header>
  );
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (getToken()) {
      api
        .me()
        .then(setUser)
        .catch(() => setToken(null))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const logout = () => {
    setToken(null);
    setUser(null);
  };

  if (loading)
    return (
      <div className="app-loading">
        <Spinner label="Loading studio…" />
      </div>
    );
  if (!user) return <Login onLogin={setUser} />;

  return (
    <div className="app">
      <TopBar user={user} onLogout={logout} />
      <main className="app-main">
        {user.role === "executor" ? <Executor /> : <Director />}
      </main>
    </div>
  );
}
