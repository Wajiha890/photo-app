const API = "http://127.0.0.1:5000";

const Auth = {
  save(token, role, username) {
    localStorage.setItem("px_token", token);
    localStorage.setItem("px_role", role);
    localStorage.setItem("px_user", username);
  },
  token()    { return localStorage.getItem("px_token") || ""; },
  role()     { return localStorage.getItem("px_role")  || ""; },
  username() { return localStorage.getItem("px_user")  || ""; },
  loggedIn() { return !!localStorage.getItem("px_token"); },
  logout() {
    localStorage.removeItem("px_token");
    localStorage.removeItem("px_role");
    localStorage.removeItem("px_user");
    window.location.href = "login.html";
  },
  headers() {
    return {
      "Content-Type": "application/json",
      "Authorization": "Bearer " + this.token()
    };
  }
};

// ── apiFetch (used in login, signup, creator, gallery) ──
async function apiFetch(path, options = {}) {
  try {
    const res  = await fetch(API + path, options);
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, data };
  } catch(e) {
    return { ok: false, status: 0, data: { message: "Cannot reach server. Is backend running on port 5000?" } };
  }
}

// ── alias so both names work ──
const api = apiFetch;

// ── Toast ──
function toast(msg, type = "info") {
  let c = document.getElementById("toast-container");
  if (!c) {
    c = document.createElement("div");
    c.id = "toast-container";
    document.body.appendChild(c);
  }
  const el = document.createElement("div");
  el.className = "toast " + (type === "success" ? "success" : type === "error" ? "error" : "info");
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

// ── Format date ──
function fmtDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("en-GB", { day:"numeric", month:"short", year:"numeric" });
}

// ── Escape HTML ──
function esc(s) {
  if (!s) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}