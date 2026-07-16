import os
import re
import uuid
import socket
import shutil
import hashlib
import mimetypes
import threading
import time
import json
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict

import tkinter as tk
from tkinter import messagebox, filedialog, ttk

from flask import (
    Flask, render_template_string, request,
    send_from_directory, redirect, url_for,
    session, jsonify, abort
)
from werkzeug.utils import secure_filename

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.urandom(32)  # Secure random session key

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHARED_DIR   = os.path.join(ROOT_DIR, "data", "network_vault")
ALLOWED_EXT  = {
    # Images
    'png','jpg','jpeg','gif','webp','bmp','svg','ico','tiff','avif',
    # Video
    'mp4','webm','mov','avi','mkv','m4v','ogv','flv',
    # Audio
    'mp3','wav','ogg','flac','aac','m4a','opus','wma',
    # Docs & misc
    'pdf','txt','md','doc','docx','xls','xlsx','ppt','pptx',
    'zip','tar','gz','7z','rar','json','csv','xml','html','css','js','py',
}
MAX_FILE_SIZE = 512 * 1024 * 1024  # 512 MB
MAX_FILES_PER_UPLOAD = 20

# Rate-limiting store  { ip: [timestamp, ...] }
_rate_store: dict[str, list] = defaultdict(list)
_rate_lock  = threading.Lock()

# Login-attempt tracking  { ip: (count, lockout_until) }
_login_attempts: dict[str, tuple] = {}
_attempts_lock  = threading.Lock()

ACCESS_PASSWORD  = "AirShare@2025"
SESSION_LIFETIME = timedelta(hours=4)

os.makedirs(SHARED_DIR, exist_ok=True)

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def get_ip():
    return request.remote_addr or "unknown"

def rate_limit(max_req: int = 30, window: int = 60):
    """Decorator – allows max_req requests per window seconds per IP."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = get_ip()
            now = time.time()
            with _rate_lock:
                _rate_store[ip] = [t for t in _rate_store[ip] if now - t < window]
                if len(_rate_store[ip]) >= max_req:
                    return jsonify(error="Rate limit exceeded"), 429
                _rate_store[ip].append(now)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("authed"):
            return redirect(url_for("index"))
        # Session lifetime
        login_time = session.get("login_time")
        if login_time and datetime.utcnow() - datetime.fromisoformat(login_time) > SESSION_LIFETIME:
            session.clear()
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapper

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def human_size(n: int) -> str:
    for unit in ('B','KB','MB','GB'):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"

def file_category(filename: str) -> str:
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext in {'png','jpg','jpeg','gif','webp','bmp','svg','ico','tiff','avif'}: return 'image'
    if ext in {'mp4','webm','mov','avi','mkv','m4v','ogv','flv'}:               return 'video'
    if ext in {'mp3','wav','ogg','flac','aac','m4a','opus','wma'}:              return 'audio'
    if ext == 'pdf': return 'pdf'
    return 'file'

def vault_files():
    files = []
    for name in sorted(os.listdir(SHARED_DIR)):
        path = os.path.join(SHARED_DIR, name)
        if os.path.isfile(path):
            stat = os.stat(path)
            files.append({
                "name": name,
                "size": human_size(stat.st_size),
                "category": file_category(name),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%b %d, %H:%M"),
            })
    return files

# ─────────────────────────────────────────────
#  HTML TEMPLATE
# ─────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AirShare Pro</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;1,9..40,300&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#08090d;
  --surface:#0f1117;
  --surface2:#161820;
  --border:#1e2030;
  --accent:#5b7cfa;
  --accent2:#a78bfa;
  --green:#34d399;
  --red:#f87171;
  --amber:#fbbf24;
  --text:#e2e8f0;
  --muted:#64748b;
  --font-display:'Syne',sans-serif;
  --font-body:'DM Sans',sans-serif;
  --radius:14px;
  --glow:0 0 40px rgba(91,124,250,.18);
}
html{scroll-behavior:smooth}
body{
  font-family:var(--font-body);
  background:var(--bg);
  color:var(--text);
  min-height:100vh;
  overflow-x:hidden;
}

/* ── Noise grain overlay ── */
body::before{
  content:'';
  position:fixed;inset:0;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.04'/%3E%3C/svg%3E");
  pointer-events:none;z-index:0;
}

/* ── Radial glow bg ── */
.bg-glow{
  position:fixed;
  width:700px;height:700px;
  border-radius:50%;
  background:radial-gradient(circle,rgba(91,124,250,.07) 0%,transparent 70%);
  pointer-events:none;z-index:0;
  top:-200px;left:-200px;
}
.bg-glow2{
  position:fixed;
  width:500px;height:500px;
  border-radius:50%;
  background:radial-gradient(circle,rgba(167,139,250,.06) 0%,transparent 70%);
  pointer-events:none;z-index:0;
  bottom:-100px;right:-100px;
}

.wrap{
  position:relative;z-index:1;
  max-width:1100px;
  margin:0 auto;
  padding:0 24px 80px;
}

/* ── NAV ── */
nav{
  display:flex;align-items:center;justify-content:space-between;
  padding:20px 0 28px;
  border-bottom:1px solid var(--border);
  margin-bottom:40px;
}
.logo{
  font-family:var(--font-display);
  font-weight:800;font-size:1.35rem;
  letter-spacing:-.5px;
  background:linear-gradient(135deg,#fff 0%,var(--accent2) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  display:flex;align-items:center;gap:10px;
}
.logo-dot{
  width:8px;height:8px;border-radius:50%;
  background:var(--green);
  box-shadow:0 0 10px var(--green);
  -webkit-text-fill-color:initial;
  flex-shrink:0;
}
.nav-info{font-size:.82rem;color:var(--muted);display:flex;gap:16px;align-items:center}
.badge{
  padding:4px 10px;border-radius:20px;
  border:1px solid var(--border);
  font-size:.75rem;color:var(--muted);
  background:var(--surface);
}
.badge.online{border-color:rgba(52,211,153,.3);color:var(--green)}

/* ── LOGIN ── */
.login-wrap{
  display:flex;align-items:center;justify-content:center;
  min-height:80vh;
}
.login-card{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:22px;
  padding:48px 44px;
  width:100%;max-width:420px;
  box-shadow:var(--glow);
  animation:fadeUp .5s ease both;
}
.login-card h2{
  font-family:var(--font-display);
  font-weight:700;font-size:1.7rem;
  margin-bottom:6px;
}
.login-card p{color:var(--muted);margin-bottom:32px;font-size:.9rem}
.field{margin-bottom:18px}
.field label{display:block;font-size:.8rem;color:var(--muted);margin-bottom:6px;letter-spacing:.5px;text-transform:uppercase}
.field input{
  width:100%;padding:13px 16px;
  background:var(--surface2);
  border:1px solid var(--border);
  border-radius:10px;
  color:var(--text);
  font-family:var(--font-body);font-size:.95rem;
  transition:border-color .2s,box-shadow .2s;
  outline:none;
}
.field input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(91,124,250,.15)}
.error-msg{color:var(--red);font-size:.82rem;margin-top:8px;display:flex;gap:6px;align-items:center}

.btn{
  display:inline-flex;align-items:center;justify-content:center;gap:8px;
  padding:13px 24px;border-radius:10px;font-weight:600;
  font-family:var(--font-body);font-size:.9rem;cursor:pointer;
  border:none;transition:all .2s;text-decoration:none;
}
.btn-primary{
  background:linear-gradient(135deg,var(--accent),var(--accent2));
  color:#fff;width:100%;
  box-shadow:0 4px 20px rgba(91,124,250,.3);
}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 6px 26px rgba(91,124,250,.45)}
.btn-primary:active{transform:none}
.btn-sm{padding:8px 14px;font-size:.8rem}
.btn-ghost{background:var(--surface2);color:var(--text);border:1px solid var(--border)}
.btn-ghost:hover{border-color:var(--accent);color:var(--accent)}
.btn-danger{background:rgba(248,113,113,.12);color:var(--red);border:1px solid rgba(248,113,113,.25)}
.btn-danger:hover{background:rgba(248,113,113,.22)}

/* ── STATS ROW ── */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:36px}
.stat-card{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius);
  padding:20px 22px;
}
.stat-card .val{
  font-family:var(--font-display);
  font-weight:700;font-size:1.8rem;
  background:linear-gradient(135deg,#fff,var(--accent2));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.stat-card .lbl{color:var(--muted);font-size:.8rem;margin-top:4px}

/* ── UPLOAD ZONE ── */
.upload-section{
  background:var(--surface);
  border:2px dashed var(--border);
  border-radius:22px;
  overflow:hidden;
  margin-bottom:36px;
  transition:border-color .25s,box-shadow .25s;
}
.upload-section.drag-over{
  border-color:var(--accent);
  box-shadow:var(--glow);
}
/* The clickable drop target — input is scoped only here */
.drop-target{
  padding:36px 32px 28px;
  text-align:center;
  cursor:pointer;
  position:relative;
  background:transparent;
  transition:background .2s;
}
.drop-target:hover{ background:rgba(91,124,250,.04); }
.drop-target input[type=file]{
  position:absolute;inset:0;opacity:0;cursor:pointer;
  width:100%;height:100%;
}
.upload-icon{font-size:2.5rem;margin-bottom:12px;display:block;pointer-events:none}
.drop-target h3{
  font-family:var(--font-display);font-size:1.15rem;font-weight:700;margin-bottom:6px;pointer-events:none;
}
.drop-target p{color:var(--muted);font-size:.85rem;pointer-events:none}

/* Queue + actions live BELOW the input — safe from interception */
.upload-lower{
  border-top:1px solid var(--border);
  padding:18px 24px;
  display:none;
}
.upload-lower.show{ display:block; }
.file-queue{
  display:flex;flex-wrap:wrap;gap:8px;
  justify-content:flex-start;margin-bottom:16px;
}
.file-chip{
  background:var(--surface2);border:1px solid var(--border);
  border-radius:8px;padding:6px 12px;font-size:.78rem;
  display:flex;align-items:center;gap:6px;max-width:220px;
}
.file-chip span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.file-chip .rm{
  cursor:pointer;color:var(--red);font-size:.9rem;flex-shrink:0;
  /* make sure clicks on ✕ reach it, not the file input */
  position:relative;z-index:10;
}
.upload-actions{display:flex;gap:12px;flex-wrap:wrap}
.progress-bar{
  height:4px;border-radius:2px;background:var(--border);
  margin-top:14px;overflow:hidden;display:none;
}
.progress-bar .fill{
  height:100%;
  background:linear-gradient(90deg,var(--accent),var(--accent2));
  transition:width .3s;width:0;
}

/* ── FILTERS ── */
.filter-row{
  display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:24px;
}
.filter-row input{
  background:var(--surface);border:1px solid var(--border);
  border-radius:8px;padding:9px 14px;color:var(--text);
  font-family:var(--font-body);font-size:.88rem;outline:none;
  transition:border-color .2s;flex:1;min-width:200px;
}
.filter-row input:focus{border-color:var(--accent)}
.filter-btn{
  padding:9px 16px;border-radius:8px;font-size:.8rem;font-weight:500;
  cursor:pointer;border:1px solid var(--border);
  background:var(--surface);color:var(--muted);transition:all .2s;font-family:var(--font-body);
}
.filter-btn.active,.filter-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}

/* ── FILE GRID ── */
.grid{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(240px,1fr));
  gap:20px;
}
.card{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--radius);
  overflow:hidden;
  transition:transform .25s,box-shadow .25s,border-color .25s;
  animation:fadeUp .35s ease both;
}
.card:hover{
  transform:translateY(-4px);
  box-shadow:0 20px 40px rgba(0,0,0,.35);
  border-color:rgba(91,124,250,.35);
}
.preview{
  width:100%;height:180px;object-fit:cover;
  background:var(--surface2);display:block;
}
.preview-icon{
  width:100%;height:180px;
  display:flex;align-items:center;justify-content:center;
  font-size:3rem;background:var(--surface2);
  position:relative;
}
.preview-icon::after{
  content:'';position:absolute;inset:0;
  background:linear-gradient(180deg,transparent 50%,rgba(0,0,0,.5));
}
.cat-badge{
  position:absolute;top:10px;right:10px;z-index:2;
  background:rgba(0,0,0,.55);backdrop-filter:blur(8px);
  border-radius:6px;padding:3px 8px;font-size:.7rem;color:#fff;border:1px solid rgba(255,255,255,.1);
}
.info{padding:14px 16px}
.file-name{
  font-weight:600;font-size:.88rem;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  margin-bottom:4px;
}
.file-meta{color:var(--muted);font-size:.75rem;margin-bottom:12px;display:flex;gap:10px}
.card-actions{display:flex;gap:8px}
.card-actions a{flex:1;text-align:center}

/* ── EMPTY ── */
.empty{
  text-align:center;padding:80px 20px;color:var(--muted);
  grid-column:1/-1;
}
.empty p{font-size:1rem;margin-top:10px}

/* ── TOAST ── */
#toast-wrap{position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:10px}
.toast{
  background:var(--surface2);border:1px solid var(--border);
  border-radius:12px;padding:14px 18px;
  display:flex;gap:10px;align-items:center;
  box-shadow:0 10px 30px rgba(0,0,0,.4);
  font-size:.88rem;
  animation:slideIn .3s ease;
  max-width:320px;
}
.toast.success{border-color:rgba(52,211,153,.3)}
.toast.error{border-color:rgba(248,113,113,.3)}

/* ── MODAL ── */
.modal-overlay{
  position:fixed;inset:0;background:rgba(0,0,0,.8);
  backdrop-filter:blur(6px);z-index:1000;
  display:flex;align-items:center;justify-content:center;
  animation:fadeIn .2s ease;
}
.modal-overlay.hidden{display:none}
.modal{
  background:var(--surface);border:1px solid var(--border);
  border-radius:20px;padding:0;overflow:hidden;
  max-width:90vw;max-height:90vh;
  box-shadow:0 40px 80px rgba(0,0,0,.6);
}
.modal-header{
  padding:18px 24px;border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;
}
.modal-header h3{font-family:var(--font-display);font-weight:700}
.modal-close{
  background:none;border:none;color:var(--muted);
  font-size:1.4rem;cursor:pointer;
  padding:4px 8px;border-radius:6px;
  transition:color .2s;
}
.modal-close:hover{color:var(--text)}
.modal-body{padding:24px;overflow-y:auto;max-height:70vh}
.modal-body img,.modal-body video,.modal-body audio{
  max-width:100%;border-radius:10px;display:block;margin:0 auto;
}
.modal-body audio{margin-top:40px}

/* ── ANIMATIONS ── */
@keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
@keyframes slideIn{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:none}}

/* ── DELETE confirm ── */
.del-confirm{
  display:none;
  background:rgba(0,0,0,.7);backdrop-filter:blur(4px);
  position:fixed;inset:0;z-index:2000;
  align-items:center;justify-content:center;
}
.del-confirm.show{display:flex}
.del-box{
  background:var(--surface2);border:1px solid var(--border);
  border-radius:16px;padding:32px;text-align:center;max-width:380px;
}
.del-box h3{font-family:var(--font-display);margin-bottom:10px}
.del-box p{color:var(--muted);font-size:.88rem;margin-bottom:24px}
.del-actions{display:flex;gap:12px;justify-content:center}

/* Responsive */
@media(max-width:600px){
  .grid{grid-template-columns:1fr 1fr}
  .stats{grid-template-columns:1fr 1fr}
  .login-card{padding:30px 22px}
}
@media(max-width:420px){
  .grid{grid-template-columns:1fr}
}
</style>
</head>
<body>
<div class="bg-glow"></div>
<div class="bg-glow2"></div>
<div class="wrap">

{% if not authed %}
<!-- ═══ LOGIN ═══ -->
<div class="login-wrap">
<div class="login-card">
  <div class="logo" style="margin-bottom:28px">
    <span class="logo-dot"></span>AirShare Pro
  </div>
  <h2>Vault Access</h2>
  <p>Enter your passphrase to unlock the file vault.</p>
  {% if error %}
  <div class="error-msg">⚠ {{ error }}</div>
  {% endif %}
  <form method="post" action="/login">
    <div class="field">
      <label>Passphrase</label>
      <input type="password" name="pw" placeholder="••••••••••••" autofocus required>
    </div>
    <button type="submit" class="btn btn-primary">Unlock Vault →</button>
  </form>
</div>
</div>

{% else %}
<!-- ═══ MAIN APP ═══ -->
<nav>
  <div class="logo"><span class="logo-dot"></span>AirShare Pro</div>
  <div class="nav-info">
    <span class="badge online">● Online</span>
    <span class="badge">{{ hostname }}</span>
    <a href="/logout" class="btn btn-sm btn-ghost">Sign out</a>
  </div>
</nav>

<!-- Stats -->
<div class="stats">
  <div class="stat-card">
    <div class="val">{{ files|length }}</div>
    <div class="lbl">Files in Vault</div>
  </div>
  <div class="stat-card">
    <div class="val">{{ images }}</div>
    <div class="lbl">Images</div>
  </div>
  <div class="stat-card">
    <div class="val">{{ videos }}</div>
    <div class="lbl">Videos</div>
  </div>
  <div class="stat-card">
    <div class="val">{{ audios }}</div>
    <div class="lbl">Audio Files</div>
  </div>
</div>

<!-- Upload Zone -->
<div class="upload-section" id="dropZone">
  <!-- Drop / click area: input is scoped ONLY here -->
  <div class="drop-target" id="dropTarget">
    <input type="file" id="fileInput" multiple>
    <span class="upload-icon">⬆️</span>
    <h3>Drop files here, or click to browse</h3>
    <p>Images · Video · Audio · Documents — up to {{ max_size }} per batch</p>
  </div>
  <!-- Queue + buttons sit OUTSIDE the file input — no interception -->
  <div class="upload-lower" id="uploadLower">
    <div class="file-queue" id="fileQueue"></div>
    <div class="upload-actions">
      <button class="btn btn-primary" id="uploadBtn">⬆ Upload Files</button>
      <button class="btn btn-ghost" id="clearBtn">✕ Clear All</button>
    </div>
    <div class="progress-bar" id="progressBar"><div class="fill" id="progressFill"></div></div>
  </div>
</div>

<!-- Filter Row -->
<div class="filter-row">
  <input type="text" id="searchInput" placeholder="🔍  Search files…">
  <button class="filter-btn active" data-cat="all">All</button>
  <button class="filter-btn" data-cat="image">🖼 Images</button>
  <button class="filter-btn" data-cat="video">🎬 Video</button>
  <button class="filter-btn" data-cat="audio">🎵 Audio</button>
  <button class="filter-btn" data-cat="file">📄 Docs</button>
</div>

<!-- Grid -->
<div class="grid" id="fileGrid">
{% for f in files %}
<div class="card" data-cat="{{ f.category }}" data-name="{{ f.name|lower }}">
  <div class="preview-icon" style="position:relative">
    {% if f.category == 'image' %}
      <img src="/download/{{ f.name }}" class="preview" loading="lazy" alt="{{ f.name }}"
           onclick="openPreview('image','{{ f.name }}')" style="cursor:zoom-in">
    {% elif f.category == 'video' %}
      <video class="preview" muted playsinline preload="metadata"
             onclick="openPreview('video','{{ f.name }}')" style="cursor:pointer">
        <source src="/download/{{ f.name }}">
      </video>
    {% elif f.category == 'audio' %}
      <span style="font-size:3.5rem">🎵</span>
    {% elif f.category == 'pdf' %}
      <span style="font-size:3.5rem">📋</span>
    {% else %}
      <span style="font-size:3.5rem">📄</span>
    {% endif %}
    <span class="cat-badge">{{ f.category }}</span>
  </div>
  <div class="info">
    <div class="file-name" title="{{ f.name }}">{{ f.name }}</div>
    <div class="file-meta"><span>{{ f.size }}</span><span>{{ f.modified }}</span></div>
    <div class="card-actions">
      {% if f.category in ['image','video','audio'] %}
      <a class="btn btn-sm btn-ghost" href="#" onclick="openPreview('{{ f.category }}','{{ f.name }}');return false">👁 Preview</a>
      {% endif %}
      <a class="btn btn-sm btn-primary" href="/download/{{ f.name }}" download>⬇ Download</a>
      <button class="btn btn-sm btn-danger" onclick="confirmDelete('{{ f.name }}')">🗑</button>
    </div>
  </div>
</div>
{% else %}
<div class="empty">
  <span style="font-size:3rem">🗂</span>
  <p>The vault is empty. Upload something!</p>
</div>
{% endfor %}
</div>

<!-- Preview Modal -->
<div class="modal-overlay hidden" id="previewModal">
  <div class="modal" style="min-width:min(700px,90vw)">
    <div class="modal-header">
      <h3 id="previewTitle">Preview</h3>
      <button class="modal-close" onclick="closeModal()">✕</button>
    </div>
    <div class="modal-body" id="previewBody"></div>
  </div>
</div>

<!-- Delete Confirm -->
<div class="del-confirm" id="delConfirm">
  <div class="del-box">
    <h3>Delete File?</h3>
    <p id="delFilename">This action cannot be undone.</p>
    <div class="del-actions">
      <button class="btn btn-ghost" onclick="closeDelete()">Cancel</button>
      <button class="btn btn-danger" id="delConfirmBtn">Delete</button>
    </div>
  </div>
</div>

{% endif %}
</div><!-- /wrap -->

<!-- Toast Container -->
<div id="toast-wrap"></div>

<script>
// ── Toast ──
function toast(msg, type='success'){
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${type==='success'?'✓':'✕'}</span><span>${msg}</span>`;
  document.getElementById('toast-wrap').appendChild(el);
  setTimeout(()=>el.remove(), 3500);
}

// ── Drop Zone ──
const dropZone   = document.getElementById('dropZone');
const dropTarget = document.getElementById('dropTarget');
const fileInput  = document.getElementById('fileInput');
const fileQueue  = document.getElementById('fileQueue');
const uploadLower= document.getElementById('uploadLower');
const progressBar  = document.getElementById('progressBar');
const progressFill = document.getElementById('progressFill');
let selectedFiles = [];

if(dropZone){
  // Drag over the whole section highlights the border
  ['dragenter','dragover'].forEach(e=>
    dropZone.addEventListener(e, ev=>{ev.preventDefault();dropZone.classList.add('drag-over')})
  );
  ['dragleave','drop'].forEach(e=>
    dropZone.addEventListener(e, ev=>{ev.preventDefault();dropZone.classList.remove('drag-over')})
  );
  // Drop anywhere on the section picks up files
  dropZone.addEventListener('drop', ev=>{
    addFiles([...ev.dataTransfer.files]);
  });
  // File input change (from clicking the drop-target area)
  fileInput.addEventListener('change',()=>{
    addFiles([...fileInput.files]);
    // Reset so same file can be re-added after removal
    fileInput.value='';
  });
}

function addFiles(files){
  files.forEach(f=>{
    if(!selectedFiles.find(x=>x.name===f.name && x.size===f.size))
      selectedFiles.push(f);
  });
  renderQueue();
}

function renderQueue(){
  fileQueue.innerHTML='';
  selectedFiles.forEach((f,i)=>{
    const chip=document.createElement('div');
    chip.className='file-chip';
    chip.innerHTML=`<span>${emoji(f.name)} ${f.name}</span><span class="rm" onclick="removeFile(${i})">✕</span>`;
    fileQueue.appendChild(chip);
  });
  // Show/hide the lower panel (buttons live here, safe from input interception)
  uploadLower.classList.toggle('show', selectedFiles.length > 0);
}

function removeFile(i){ selectedFiles.splice(i,1); renderQueue(); }

function emoji(name){
  const ext=name.split('.').pop().toLowerCase();
  if(['png','jpg','jpeg','gif','webp','bmp','svg'].includes(ext)) return '🖼';
  if(['mp4','webm','mov','avi','mkv'].includes(ext)) return '🎬';
  if(['mp3','wav','ogg','flac','aac','m4a'].includes(ext)) return '🎵';
  if(ext==='pdf') return '📋';
  return '📄';
}

document.getElementById('uploadBtn')?.addEventListener('click', async()=>{
  if(!selectedFiles.length) return;
  const fd = new FormData();
  selectedFiles.forEach(f=>fd.append('files', f));

  progressBar.style.display='block';
  progressFill.style.width='0%';

  const xhr = new XMLHttpRequest();
  xhr.upload.addEventListener('progress', e=>{
    if(e.lengthComputable)
      progressFill.style.width = Math.round(e.loaded/e.total*100)+'%';
  });
  xhr.open('POST','/upload');
  xhr.onload=()=>{
    if(xhr.status===200){
      toast('Files uploaded!'); setTimeout(()=>location.reload(),800);
    } else {
      toast(JSON.parse(xhr.responseText).error || 'Upload failed','error');
      progressBar.style.display='none';
    }
  };
  xhr.onerror=()=>{toast('Network error','error');progressBar.style.display='none'};
  xhr.send(fd);
});

document.getElementById('clearBtn')?.addEventListener('click',()=>{
  selectedFiles=[];renderQueue();fileInput.value='';
  progressBar.style.display='none';progressFill.style.width='0%';
});

// ── Filters ──
const filterBtns = document.querySelectorAll('.filter-btn');
const cards      = document.querySelectorAll('.card');
const searchInput= document.getElementById('searchInput');
let activeCat='all';

filterBtns.forEach(btn=>{
  btn.addEventListener('click',()=>{
    filterBtns.forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    activeCat = btn.dataset.cat;
    applyFilter();
  });
});
searchInput?.addEventListener('input', applyFilter);

function applyFilter(){
  const q = (searchInput?.value||'').toLowerCase();
  cards.forEach(c=>{
    const catMatch = activeCat==='all' || c.dataset.cat===activeCat;
    const nameMatch= !q || c.dataset.name.includes(q);
    c.style.display = catMatch && nameMatch ? '' : 'none';
  });
}

// ── Preview Modal ──
function openPreview(type, name){
  const modal = document.getElementById('previewModal');
  const body  = document.getElementById('previewBody');
  const title = document.getElementById('previewTitle');
  title.textContent = name;
  const url = `/download/${encodeURIComponent(name)}`;
  if(type==='image')
    body.innerHTML=`<img src="${url}" alt="${name}" style="max-height:75vh">`;
  else if(type==='video')
    body.innerHTML=`<video controls autoplay style="max-height:75vh;max-width:100%"><source src="${url}"></video>`;
  else if(type==='audio')
    body.innerHTML=`<div style="padding:40px 0;text-align:center"><span style="font-size:5rem">🎵</span><p style="margin:20px 0 10px;font-family:'Syne',sans-serif;font-weight:700">${name}</p><audio controls autoplay style="width:100%;margin-top:20px"><source src="${url}"></audio></div>`;
  modal.classList.remove('hidden');
}
function closeModal(){
  document.getElementById('previewModal').classList.add('hidden');
  document.getElementById('previewBody').innerHTML='';
}
document.getElementById('previewModal')?.addEventListener('click', e=>{
  if(e.target.id==='previewModal') closeModal();
});

// ── Delete ──
let deleteTarget='';
function confirmDelete(name){
  deleteTarget=name;
  document.getElementById('delFilename').textContent=`"${name}" will be permanently deleted.`;
  document.getElementById('delConfirm').classList.add('show');
}
function closeDelete(){ document.getElementById('delConfirm').classList.remove('show'); deleteTarget=''; }
document.getElementById('delConfirmBtn')?.addEventListener('click', async()=>{
  if(!deleteTarget) return;
  const res = await fetch(`/delete/${encodeURIComponent(deleteTarget)}`,{method:'POST'});
  const data = await res.json();
  if(data.ok){ toast('File deleted'); setTimeout(()=>location.reload(),600); }
  else toast(data.error||'Delete failed','error');
  closeDelete();
});

// Keyboard close
document.addEventListener('keydown', e=>{ if(e.key==='Escape'){ closeModal(); closeDelete(); }});

// Video hover play
document.querySelectorAll('video.preview').forEach(v=>{
  v.addEventListener('mouseenter',()=>v.play().catch(()=>{}));
  v.addEventListener('mouseleave',()=>{v.pause();v.currentTime=0});
});
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

def render(template=HTML, **kwargs):
    files   = vault_files()
    cats    = [f["category"] for f in files]
    return render_template_string(
        template,
        files    = files,
        authed   = session.get("authed", False),
        hostname = socket.gethostname(),
        error    = kwargs.get("error", ""),
        images   = cats.count("image"),
        videos   = cats.count("video"),
        audios   = cats.count("audio"),
        max_size = human_size(MAX_FILE_SIZE),
    )

@app.route('/')
def index():
    return render()

@app.route('/login', methods=['POST'])
@rate_limit(max_req=10, window=60)
def login():
    ip = get_ip()
    with _attempts_lock:
        count, lockout = _login_attempts.get(ip, (0, 0))
        if time.time() < lockout:
            remaining = int(lockout - time.time())
            return render(error=f"Too many attempts. Try again in {remaining}s.")
        if count >= 10:
            _login_attempts[ip] = (count, time.time() + 300)  # 5-min lockout
            return render(error="Locked out for 5 minutes after too many failures.")

    pw = request.form.get('pw', '')
    if hash_password(pw) == hash_password(ACCESS_PASSWORD):
        with _attempts_lock:
            _login_attempts[ip] = (0, 0)
        session['authed'] = True
        session['login_time'] = datetime.utcnow().isoformat()
        session.permanent = True
        app.permanent_session_lifetime = SESSION_LIFETIME
        return redirect(url_for('index'))
    else:
        with _attempts_lock:
            _login_attempts[ip] = (count + 1, 0)
        return render(error="Incorrect passphrase.")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
@login_required
@rate_limit(max_req=20, window=60)
def upload():
    uploaded_files = request.files.getlist('files')
    if not uploaded_files:
        return jsonify(error="No files received"), 400
    if len(uploaded_files) > MAX_FILES_PER_UPLOAD:
        return jsonify(error=f"Max {MAX_FILES_PER_UPLOAD} files per upload"), 400

    saved = []
    for f in uploaded_files:
        if not f or f.filename == '':
            continue
        if not allowed_file(f.filename):
            return jsonify(error=f"File type not allowed: {f.filename}"), 400

        # Read to check size (stream to disk safely)
        safe_name = secure_filename(f.filename)
        # Avoid collisions
        dest = os.path.join(SHARED_DIR, safe_name)
        if os.path.exists(dest):
            base, ext = os.path.splitext(safe_name)
            safe_name = f"{base}_{uuid.uuid4().hex[:6]}{ext}"
            dest = os.path.join(SHARED_DIR, safe_name)

        f.save(dest)
        # Size check after save
        if os.path.getsize(dest) > MAX_FILE_SIZE:
            os.remove(dest)
            return jsonify(error=f"{safe_name} exceeds max size limit"), 400
        saved.append(safe_name)

    return jsonify(ok=True, saved=saved)

@app.route('/download/<path:filename>')
@login_required
def download(filename):
    # Prevent path traversal
    safe = secure_filename(filename)
    return send_from_directory(os.path.abspath(SHARED_DIR), safe, as_attachment=False)

@app.route('/delete/<path:filename>', methods=['POST'])
@login_required
def delete_file(filename):
    safe = secure_filename(filename)
    path = os.path.join(SHARED_DIR, safe)
    if not os.path.isfile(path):
        return jsonify(error="File not found"), 404
    os.remove(path)
    return jsonify(ok=True)

def run_server():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

# ─────────────────────────────────────────────
#  DESKTOP GUI
# ─────────────────────────────────────────────
class AppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AirShare Pro")
        self.root.geometry("520x620")
        self.root.configure(bg="#08090d")
        self.root.resizable(False, False)
        self._server_running = False
        self._build_ui()

    def _build_ui(self):
        root = self.root

        # Header
        hdr = tk.Frame(root, bg="#0f1117", height=70)
        hdr.pack(fill="x")
        tk.Label(hdr, text="✈  AirShare Pro", bg="#0f1117", fg="white",
                 font=("Segoe UI", 16, "bold")).pack(pady=18)

        # Card
        card = tk.Frame(root, bg="#0f1117", padx=24, pady=24)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        # Password
        self._label(card, "Access Passphrase")
        self.pw_var = tk.StringVar(value=ACCESS_PASSWORD)
        self.pw_entry = tk.Entry(card, textvariable=self.pw_var, font=("Segoe UI", 11),
                                 bg="#161820", fg="white", insertbackground="white",
                                 relief="flat", bd=8, show="•")
        self.pw_entry.pack(fill="x", pady=(4, 14))

        pw_frame = tk.Frame(card, bg="#0f1117")
        pw_frame.pack(fill="x", pady=(0, 18))
        tk.Checkbutton(pw_frame, text="Show passphrase", bg="#0f1117", fg="#64748b",
                       selectcolor="#0f1117", activebackground="#0f1117",
                       command=self._toggle_pw, font=("Segoe UI", 9)).pack(anchor="w")

        # Max file size
        self._label(card, "Max File Size")
        self.size_var = tk.StringVar(value="512")
        size_frame = tk.Frame(card, bg="#0f1117")
        size_frame.pack(fill="x", pady=(4, 18))
        tk.Entry(size_frame, textvariable=self.size_var, font=("Segoe UI", 11),
                 bg="#161820", fg="white", insertbackground="white",
                 relief="flat", bd=8, width=8).pack(side="left")
        tk.Label(size_frame, text=" MB", bg="#0f1117", fg="#64748b",
                 font=("Segoe UI", 10)).pack(side="left")

        # File selection
        self._label(card, "Shared Files")
        btn_browse = tk.Button(card, text="📁  Add Files to Vault",
                               command=self.select_files,
                               bg="#1e2030", fg="white", relief="flat",
                               font=("Segoe UI", 10), pady=10, bd=0,
                               activebackground="#2a2d42", activeforeground="white",
                               cursor="hand2")
        btn_browse.pack(fill="x", pady=(4, 6))

        self.file_label = tk.Label(card, text="Vault is empty",
                                   bg="#0f1117", fg="#64748b", font=("Segoe UI", 9))
        self.file_label.pack(pady=(0, 18))

        # Start button
        self.btn_start = tk.Button(card, text="▶  START SERVER",
                                   command=self.start_service,
                                   bg="#5b7cfa", fg="white", relief="flat",
                                   font=("Segoe UI", 11, "bold"), pady=14, bd=0,
                                   activebackground="#4a6af0", activeforeground="white",
                                   cursor="hand2")
        self.btn_start.pack(fill="x", pady=(0, 16))

        # Status
        self.status_var = tk.StringVar(value="● Offline")
        self.status_lbl = tk.Label(card, textvariable=self.status_var,
                                   bg="#161820", fg="#64748b",
                                   font=("Segoe UI", 9), pady=12, padx=12,
                                   relief="flat")
        self.status_lbl.pack(fill="x")

        # Clear vault
        tk.Button(card, text="🗑  Clear Vault",
                  command=self.clear_vault,
                  bg="#0f1117", fg="#64748b", relief="flat",
                  font=("Segoe UI", 9), pady=6, bd=0,
                  activebackground="#0f1117", activeforeground="#f87171",
                  cursor="hand2").pack(pady=(12, 0))

    def _label(self, parent, text):
        tk.Label(parent, text=text.upper(), bg="#0f1117", fg="#64748b",
                 font=("Segoe UI", 8), anchor="w").pack(fill="x")

    def _toggle_pw(self):
        self.pw_entry.config(show="" if self.pw_entry.cget("show") == "•" else "•")

    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Select Files for Vault",
            filetypes=[("All Files", "*.*"),
                       ("Images", "*.png *.jpg *.jpeg *.gif *.webp"),
                       ("Videos", "*.mp4 *.mov *.webm *.avi"),
                       ("Audio", "*.mp3 *.wav *.ogg *.flac *.aac")])
        if files:
            for f in files:
                name = secure_filename(os.path.basename(f))
                shutil.copy(f, os.path.join(SHARED_DIR, name))
            self._refresh_label()
            messagebox.showinfo("AirShare Pro", f"Added {len(files)} file(s) to vault.")

    def _refresh_label(self):
        count = len(os.listdir(SHARED_DIR))
        self.file_label.config(text=f"{count} file(s) in vault",
                               fg="white" if count else "#64748b")

    def clear_vault(self):
        if messagebox.askyesno("Clear Vault", "Remove all files from the vault?"):
            for f in os.listdir(SHARED_DIR):
                os.remove(os.path.join(SHARED_DIR, f))
            self._refresh_label()

    def start_service(self):
        global ACCESS_PASSWORD, MAX_FILE_SIZE
        if self._server_running:
            return

        pw = self.pw_var.get().strip()
        if len(pw) < 4:
            messagebox.showerror("Error", "Passphrase must be at least 4 characters.")
            return

        try:
            mb = int(self.size_var.get())
            MAX_FILE_SIZE = mb * 1024 * 1024
        except ValueError:
            messagebox.showerror("Error", "Max file size must be a number (MB).")
            return

        ACCESS_PASSWORD = pw
        self._server_running = True

        t = threading.Thread(target=run_server, daemon=True)
        t.start()

        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = "127.0.0.1"

        url = f"http://{ip}:5000"
        self.status_var.set(f"● ONLINE  —  {url}")
        self.status_lbl.config(fg="#34d399", bg="#0a1f15")
        self.btn_start.config(state="disabled", text="✓  Server Running", bg="#1a2e1a")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # Clean vault on launch (optional – comment out to persist files)
    for f in os.listdir(SHARED_DIR):
        fp = os.path.join(SHARED_DIR, f)
        if os.path.isfile(fp):
            os.remove(fp)

    root = tk.Tk()
    gui  = AppGUI(root)
    root.mainloop()