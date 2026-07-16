"""
CineStream v5 — God-Level Personal Cinema Server
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEW IN v5:
  • MOBILE-FIRST portrait-mode player with native controls
  • Double-tap left/right to seek ±10s (with animated ripple)
  • Swipe up/down for volume (portrait mode)
  • Swipe left/right to seek (landscape)
  • Pinch-to-zoom brightness simulation
  • Bottom sheet player controls for portrait mode
  • Long-press on video for speed menu
  • Auto-hide controls with activity detection
  • Picture-in-Picture button
  • Lock screen controls (media session API)
  • Smooth seek bar with chapter markers
  • Animated seek preview thumbnails (time-based)
  • Brightness / Volume side-panel sliders
  • Sleep timer
  • Playback speed: 0.5x, 0.75x, 1x, 1.25x, 1.5x, 2x
  • A-B loop section
  • Cast button (placeholder for Chromecast)
  • Share timestamp
  • Video quality selector (if multi-quality)
  • Subtitle delay offset control
  • Cinematic blur backdrop on iOS/Android
  • Everything from v4 preserved and upgraded
"""

import sys, os, threading, socket, re, mimetypes, json, uuid, time, math, hashlib
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import (Flask, render_template_string, Response, request,
                   jsonify, abort, make_response, send_from_directory)

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QFileDialog, QFrame, QScrollArea,
        QSizePolicy, QMessageBox, QSystemTrayIcon, QMenu, QTabWidget,
        QLineEdit, QTextEdit, QProgressBar, QSplitter,
    )
    from PyQt6.QtCore import (Qt, QThread, pyqtSignal, QTimer, pyqtSlot, QSize)
    from PyQt6.QtGui import (QFont, QColor, QPalette, QPixmap, QPainter,
                              QBrush, QPen, QLinearGradient, QIcon, QAction,
                              QCursor, QRadialGradient, QConicalGradient)
except ImportError:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QLabel, QFileDialog, QFrame, QScrollArea,
        QSizePolicy, QMessageBox, QSystemTrayIcon, QMenu, QTabWidget,
        QLineEdit, QTextEdit, QProgressBar, QSplitter,
        QAction,
    )
    from PyQt5.QtCore import (Qt, QThread, pyqtSignal, QTimer, pyqtSlot, QSize)
    from PyQt5.QtGui import (QFont, QColor, QPalette, QPixmap, QPainter,
                              QBrush, QPen, QLinearGradient, QIcon,
                              QCursor, QRadialGradient, QConicalGradient)

# ═══════════════════════════════════════════════════════════════
LIBRARIES: dict = {}
ALLOWED_EXT = ('.mp4', '.mkv', '.webm', '.mov', '.avi', '.m4v', '.ts', '.flv')
SUB_EXT = ('.srt', '.vtt', '.ass')

PENDING_DEVICES: dict = {}
APPROVED_DEVICES: dict = {}
BLOCKED_DEVICES: set = set()
WATCH_HISTORY: dict = {}
SESSION_LOG: list = []
ACTIVE_VIEWERS: dict = {}
SERVER_START_TIME: float = 0

class _Bridge:
    on_approval_needed = None
    on_session_event   = None

bridge = _Bridge()

flask_app = Flask(__name__)
flask_app.secret_key = os.urandom(24)

def get_token():
    return request.cookies.get('cs_token')

def require_approved(f):
    @wraps(f)
    def dec(*a, **kw):
        t = get_token()
        if not t:                   return _new_session_page()
        if t in BLOCKED_DEVICES:    return render_template_string(BLOCKED_HTML), 403
        if t in APPROVED_DEVICES:   return f(*a, **kw)
        if t in PENDING_DEVICES:    return render_template_string(WAITING_HTML, device=PENDING_DEVICES[t])
        return _new_session_page()
    return dec

def _new_session_page():
    resp = make_response(render_template_string(REGISTER_HTML))
    resp.set_cookie('cs_token', str(uuid.uuid4()), max_age=60*60*24*30,
                    httponly=True, samesite='Lax')
    return resp

def _log(token, action):
    dev = APPROVED_DEVICES.get(token, PENDING_DEVICES.get(token, {}))
    SESSION_LOG.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "token": token[:8],
        "name": dev.get("name", "?"),
        "action": action
    })
    if bridge.on_session_event:
        bridge.on_session_event.emit(SESSION_LOG[-1])

PALETTES = [
    ("#7c3aed","#4f46e5"), ("#db2777","#7c3aed"), ("#0891b2","#0e7490"),
    ("#059669","#0891b2"), ("#d97706","#dc2626"), ("#be185d","#9333ea"),
    ("#1d4ed8","#0891b2"), ("#7c3aed","#db2777"),
]
def file_palette(name):
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return PALETTES[h % len(PALETTES)]


# ══════════════════════════════════════════════════════════════
REGISTER_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>CineStream</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{min-height:100vh;background:#050508;display:flex;align-items:center;
     justify-content:center;font-family:'DM Sans',sans-serif;overflow:hidden;}
canvas{position:fixed;inset:0;pointer-events:none;}
.card{position:relative;z-index:1;
  background:rgba(255,255,255,.025);
  border:1px solid rgba(255,255,255,.07);border-radius:28px;
  padding:52px 44px;max-width:400px;width:calc(100% - 28px);
  backdrop-filter:blur(80px);text-align:center;
  box-shadow:0 80px 160px rgba(0,0,0,.8),0 0 0 1px rgba(255,255,255,.03) inset;}
.logo{font-family:'Syne',sans-serif;font-size:2.8rem;font-weight:800;letter-spacing:-1px;
  background:linear-gradient(135deg,#fff 0%,#a78bfa 50%,#818cf8 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  margin-bottom:6px;display:block;}
.tagline{color:rgba(255,255,255,.25);font-size:.75rem;letter-spacing:2px;
  text-transform:uppercase;margin-bottom:40px;}
.steps{display:flex;flex-direction:column;gap:8px;margin-bottom:36px;}
.step{display:flex;align-items:center;gap:14px;padding:12px 16px;
  background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);
  border-radius:14px;text-align:left;}
.sn{width:26px;height:26px;border-radius:50%;flex-shrink:0;
  background:linear-gradient(135deg,#7c3aed,#4f46e5);
  color:#fff;font-size:.68rem;font-weight:700;
  display:flex;align-items:center;justify-content:center;}
.st{font-size:.78rem;color:rgba(255,255,255,.4);}
input{width:100%;background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.09);border-radius:14px;
  padding:16px 18px;color:#fff;font-size:.92rem;font-family:'DM Sans';
  outline:none;transition:all .25s;margin-bottom:12px;}
input:focus{border-color:rgba(124,58,237,.5);background:rgba(124,58,237,.05);}
input::placeholder{color:rgba(255,255,255,.18);}
button{width:100%;padding:16px;
  background:linear-gradient(135deg,#7c3aed,#4f46e5);
  border:none;border-radius:14px;color:#fff;font-size:.9rem;
  font-weight:600;font-family:'DM Sans';cursor:pointer;transition:all .2s;}
button:hover{transform:translateY(-2px);box-shadow:0 12px 40px rgba(124,58,237,.4);}
</style>
</head>
<body>
<canvas id="c"></canvas>
<div class="card">
  <span class="logo">CineStream</span>
  <p class="tagline">Private Cinema Server</p>
  <div class="steps">
    <div class="step"><div class="sn">1</div><div class="st">Enter your device name below</div></div>
    <div class="step"><div class="sn">2</div><div class="st">Host approves your device</div></div>
    <div class="step"><div class="sn">3</div><div class="st">Stream anything in the library</div></div>
  </div>
  <form id="f">
    <input type="text" id="name" placeholder="e.g. Raj's iPhone, Living Room TV" maxlength="40" required autocomplete="off">
    <button type="submit" id="btn">Request Access →</button>
  </form>
</div>
<script>
const c=document.getElementById('c'),ctx=c.getContext('2d');
let W,H,stars=[];
function init(){W=c.width=innerWidth;H=c.height=innerHeight;
  stars=Array.from({length:100},()=>({x:Math.random()*W,y:Math.random()*H,r:Math.random()*1.2+.2,vx:(Math.random()-.5)*.15,vy:(Math.random()-.5)*.15,a:Math.random()}));}
function draw(){ctx.clearRect(0,0,W,H);
  stars.forEach(s=>{s.x=(s.x+s.vx+W)%W;s.y=(s.y+s.vy+H)%H;
    ctx.beginPath();ctx.arc(s.x,s.y,s.r,0,6.28);
    ctx.fillStyle=`rgba(167,139,250,${.2+.4*Math.abs(Math.sin(Date.now()*.0008+s.x))})`;ctx.fill();});
  requestAnimationFrame(draw);}
init();draw();addEventListener('resize',init);
document.getElementById('f').addEventListener('submit',async e=>{
  e.preventDefault();const name=document.getElementById('name').value.trim();if(!name)return;
  document.getElementById('btn').textContent='Sending…';
  await fetch('/api/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});
  location.reload();});
</script></body></html>"""

WAITING_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>CineStream — Waiting</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{min-height:100vh;background:#050508;display:flex;align-items:center;justify-content:center;font-family:'DM Sans',sans-serif;}
.card{background:rgba(255,255,255,.025);border:1px solid rgba(245,158,11,.12);border-radius:28px;
  padding:52px 40px;max-width:340px;width:90%;text-align:center;backdrop-filter:blur(40px);}
.spinner{width:56px;height:56px;margin:0 auto 28px;position:relative;}
.spinner::before,.spinner::after{content:'';position:absolute;border-radius:50%;border:2px solid transparent;}
.spinner::before{inset:0;border-top-color:#f59e0b;animation:spin 1s linear infinite;}
.spinner::after{inset:8px;border-top-color:rgba(245,158,11,.3);animation:spin .7s linear infinite reverse;}
@keyframes spin{to{transform:rotate(360deg)}}
h1{font-family:'Syne',sans-serif;font-size:2rem;font-weight:800;color:#fff;margin-bottom:10px;}
p{color:rgba(255,255,255,.3);font-size:.82rem;line-height:1.8;}
.badge{display:inline-flex;align-items:center;gap:8px;margin-top:24px;
  background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.18);
  border-radius:99px;padding:10px 22px;color:#f59e0b;font-size:.8rem;}
</style></head>
<body><div class="card">
  <div class="spinner"></div>
  <h1>Awaiting Approval</h1>
  <p>The host needs to approve your device.<br>Checking automatically every 3 seconds.</p>
  <div class="badge">👤 {{ device.name }}</div>
</div>
<script>
setInterval(async()=>{
  const r=await fetch('/api/check_status');const d=await r.json();
  if(d.status==='approved')location.href='/';
  if(d.status==='blocked')location.href='/blocked';
},3000);
</script></body></html>"""

BLOCKED_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<style>*{margin:0;padding:0;box-sizing:border-box}
body{min-height:100vh;background:#050508;display:flex;align-items:center;justify-content:center;font-family:sans-serif;}
.card{background:rgba(244,63,94,.04);border:1px solid rgba(244,63,94,.15);border-radius:22px;
  padding:52px 40px;max-width:300px;width:90%;text-align:center;}
.icon{font-size:3rem;margin-bottom:20px;}
h1{color:#f43f5e;font-size:1.8rem;margin-bottom:12px;}
p{color:rgba(255,255,255,.25);font-size:.82rem;line-height:1.8;}
</style></head>
<body><div class="card"><div class="icon">🚫</div>
<h1>Access Denied</h1><p>This device has been blocked by the host.</p>
</div></body></html>"""


# ══════════════════════════════════════════════════════════════
#   MAIN APP HTML — GOD LEVEL
# ══════════════════════════════════════════════════════════════
MAIN_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#050508">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<title>CineStream</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,300&display=swap" rel="stylesheet">
<style>
:root{
  --bg:#050508;--s1:#0a0a10;--s2:#0e0e18;--s3:#141420;
  --acc:#7c3aed;--acc2:#4f46e5;--acc-g:linear-gradient(135deg,#7c3aed,#4f46e5);
  --gold:#f59e0b;--rose:#f43f5e;--green:#22c55e;--cyan:#06b6d4;
  --text:#f0f0fa;--muted:#42425a;--dim:#18182a;
  --r:14px;--font:'DM Sans',sans-serif;
  --safe-top:env(safe-area-inset-top,0px);
  --safe-bot:env(safe-area-inset-bottom,0px);
}
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent;touch-action:manipulation;}
html,body{height:100%;background:var(--bg);color:var(--text);font-family:var(--font);overflow-x:hidden;}
::-webkit-scrollbar{width:2px;} ::-webkit-scrollbar-thumb{background:#1a1a28;}
input,button,select{-webkit-appearance:none;appearance:none;}

/* ── HEADER ─────────────────────────────────────────── */
header{
  position:sticky;top:0;z-index:300;
  padding:calc(var(--safe-top) + 10px) 16px 10px;
  background:rgba(5,5,8,.92);backdrop-filter:blur(40px) saturate(200%);
  border-bottom:1px solid rgba(255,255,255,.04);
  display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:12px;
}
.logo{font-family:'Syne',sans-serif;font-size:1.3rem;font-weight:800;letter-spacing:-0.5px;
  background:var(--acc-g);-webkit-background-clip:text;-webkit-text-fill-color:transparent;white-space:nowrap;}
.search-wrap{position:relative;width:100%;}
.search-input{width:100%;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.06);
  border-radius:12px;padding:10px 40px 10px 36px;color:var(--text);
  font-size:.82rem;font-family:var(--font);outline:none;transition:all .25s;}
.search-input:focus{border-color:rgba(124,58,237,.45);background:rgba(255,255,255,.07);}
.search-input::placeholder{color:var(--muted);}
.s-ico{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--muted);font-size:.8rem;pointer-events:none;}
.search-results{position:absolute;top:calc(100% + 6px);left:0;right:0;
  background:rgba(8,8,14,.98);border:1px solid rgba(255,255,255,.08);
  border-radius:16px;backdrop-filter:blur(40px);max-height:320px;overflow-y:auto;
  display:none;z-index:500;box-shadow:0 20px 60px rgba(0,0,0,.6);}
.search-results.open{display:block;}
.sr-item{display:flex;align-items:center;gap:12px;padding:10px 14px;cursor:pointer;border-radius:10px;margin:4px;}
.sr-item:hover,.sr-item.focused{background:rgba(124,58,237,.1);}
.sr-thumb{width:40px;height:26px;border-radius:6px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:.85rem;}
.sr-name{font-size:.8rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sr-name mark{background:rgba(124,58,237,.3);color:#c4b5fd;border-radius:3px;padding:0 2px;}
.sr-lib{font-size:.65rem;color:var(--muted);}
.hdr-right{display:flex;align-items:center;gap:6px;}
.vbtn-wrap{display:flex;gap:1px;background:var(--s1);border-radius:8px;padding:3px;}
.vbtn{width:28px;height:22px;border:none;background:transparent;color:var(--muted);
  font-size:.75rem;border-radius:5px;cursor:pointer;display:flex;align-items:center;justify-content:center;}
.vbtn.active{background:var(--dim);color:#a78bfa;}
.user-chip{background:rgba(124,58,237,.08);border:1px solid rgba(124,58,237,.15);
  border-radius:99px;padding:5px 11px;font-size:.7rem;color:#a78bfa;max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}

/* ── HERO ─────────────────────────────────────────── */
#hero{margin:12px;border-radius:20px;overflow:hidden;position:relative;height:170px;cursor:pointer;}
#hero-bg{position:absolute;inset:0;transition:transform 8s ease;}
#hero:active #hero-bg{transform:scale(1.03);}
.hero-overlay{position:absolute;inset:0;background:linear-gradient(90deg,rgba(5,5,8,.95) 0%,rgba(5,5,8,.5) 60%,transparent);}
.hero-content{position:relative;z-index:1;height:100%;display:flex;flex-direction:column;justify-content:flex-end;padding:20px 22px;}
.hero-badge{font-size:.62rem;text-transform:uppercase;letter-spacing:2px;color:#a78bfa;
  background:rgba(124,58,237,.12);border:1px solid rgba(124,58,237,.2);
  border-radius:99px;padding:3px 11px;display:inline-flex;align-items:center;gap:5px;margin-bottom:7px;width:fit-content;}
.hero-title{font-family:'Syne',sans-serif;font-size:1.65rem;font-weight:700;color:#fff;line-height:1.1;margin-bottom:5px;}
.hero-meta{font-size:.7rem;color:rgba(255,255,255,.35);}
.hero-play{position:absolute;right:20px;top:50%;transform:translateY(-50%);
  width:50px;height:50px;border-radius:50%;background:rgba(124,58,237,.85);backdrop-filter:blur(10px);
  border:2px solid rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-size:1rem;}

/* ── FILTER BAR ──────────────────────────────────── */
.filter-bar{display:flex;align-items:center;gap:6px;padding:8px 12px;overflow-x:auto;scrollbar-width:none;}
.filter-bar::-webkit-scrollbar{display:none;}
.fbtn{flex-shrink:0;padding:5px 14px;border-radius:99px;border:1px solid rgba(255,255,255,.07);
  background:transparent;color:var(--muted);font-size:.72rem;font-family:var(--font);cursor:pointer;transition:all .2s;white-space:nowrap;}
.fbtn.active{background:rgba(124,58,237,.12);border-color:rgba(124,58,237,.35);color:#a78bfa;font-weight:600;}
.sort-select{background:transparent;border:1px solid rgba(255,255,255,.07);
  border-radius:99px;color:var(--muted);font-size:.72rem;font-family:var(--font);
  padding:5px 14px;outline:none;cursor:pointer;}
.sort-select option{background:#0a0a10;}

/* ── SECTION TITLE ────────────────────────────────── */
.stitle{font-size:.6rem;text-transform:uppercase;letter-spacing:2.5px;color:var(--muted);
  display:flex;align-items:center;gap:8px;padding:14px 14px 6px;font-weight:600;}
.stitle::after{content:'';flex:1;height:1px;background:rgba(255,255,255,.04);}
.stitle .cnt{background:var(--dim);color:#44445a;font-size:.58rem;padding:2px 7px;border-radius:4px;letter-spacing:0;}

/* ── CONTINUE WATCHING ────────────────────────────── */
.cscroll{display:flex;gap:10px;overflow-x:auto;padding:0 14px 12px;scrollbar-width:none;}
.cscroll::-webkit-scrollbar{display:none;}
.ccard{flex-shrink:0;width:155px;background:var(--s1);border-radius:12px;overflow:hidden;cursor:pointer;
  border:1px solid rgba(255,255,255,.04);transition:transform .2s;}
.ccard:active{transform:scale(.96);}
.cthumb{height:84px;position:relative;display:flex;align-items:center;justify-content:center;}
.cprog{position:absolute;bottom:0;left:0;height:3px;background:var(--acc-g);}
.cinfo{padding:8px 10px 10px;}
.cname{font-size:.7rem;font-weight:500;color:#c0c0e0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.3;}
.cpct{font-size:.6rem;color:var(--muted);margin-top:3px;}

/* ── VIDEO GRID ───────────────────────────────────── */
.lib-sec{padding:0 12px 14px;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(145px,1fr));gap:9px;}
.vcard{background:var(--s1);border-radius:12px;overflow:hidden;cursor:pointer;
  border:1px solid rgba(255,255,255,.04);position:relative;transition:transform .2s,border-color .2s;}
.vcard:active{transform:scale(.96);}
.vthumb{width:100%;aspect-ratio:16/10;position:relative;display:flex;align-items:center;justify-content:center;overflow:hidden;}
.vthumb-bg{position:absolute;inset:0;transition:transform .35s ease;}
.vcard:hover .vthumb-bg{transform:scale(1.06);}
.vplay-btn{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  background:rgba(0,0,0,.15);opacity:0;transition:opacity .2s;}
.vcard:hover .vplay-btn{opacity:1;}
.vplay-circle{width:40px;height:40px;border-radius:50%;background:rgba(124,58,237,.85);
  display:flex;align-items:center;justify-content:center;color:#fff;font-size:.9rem;}
.prog-ring{position:absolute;top:5px;right:5px;width:22px;height:22px;}
.add-q{position:absolute;top:5px;left:5px;width:22px;height:22px;border-radius:50%;
  background:rgba(0,0,0,.55);backdrop-filter:blur(6px);border:1px solid rgba(255,255,255,.12);
  color:rgba(255,255,255,.7);font-size:.62rem;display:flex;align-items:center;justify-content:center;
  opacity:0;transition:opacity .2s;z-index:3;cursor:pointer;border:none;}
.vcard:hover .add-q{opacity:1;}
.vinfo{padding:8px 10px 11px;}
.vname{font-size:.73rem;font-weight:500;color:#cccce8;line-height:1.35;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
.vmeta{display:flex;align-items:center;justify-content:space-between;margin-top:5px;}
.vext{font-size:.55rem;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);
  background:var(--s3);padding:2px 6px;border-radius:4px;}
.vwatch{font-size:.58rem;color:#a78bfa;}

/* ── LIST VIEW ────────────────────────────────────── */
.list-view .grid{grid-template-columns:1fr;}
.list-view .vcard{display:flex;height:58px;}
.list-view .vcard:active{transform:translateX(4px) scale(1);}
.list-view .vthumb{width:96px;flex-shrink:0;aspect-ratio:unset;height:58px;border-radius:0;}
.list-view .vinfo{display:flex;align-items:center;justify-content:space-between;flex:1;padding:0 12px;}
.list-view .vname{-webkit-line-clamp:1;}
.list-view .vmeta{flex-direction:column;align-items:flex-end;gap:2px;}

/* ── EMPTY ────────────────────────────────────────── */
.empty{text-align:center;padding:80px 24px;color:var(--muted);}
.empty-ico{font-size:3rem;opacity:.15;margin-bottom:16px;}

/* ── QUEUE ────────────────────────────────────────── */
#queue-panel{position:fixed;right:-300px;top:0;bottom:0;width:280px;z-index:400;
  background:rgba(5,5,10,.97);border-left:1px solid rgba(255,255,255,.06);
  backdrop-filter:blur(40px);transition:right .3s cubic-bezier(.4,0,.2,1);display:flex;flex-direction:column;}
#queue-panel.open{right:0;}
.qp-header{display:flex;align-items:center;justify-content:space-between;padding:16px 16px 12px;border-bottom:1px solid rgba(255,255,255,.05);}
.qp-title{font-size:.82rem;font-weight:600;}
.qp-close{background:none;border:none;color:var(--muted);font-size:1rem;cursor:pointer;}
.qp-list{flex:1;overflow-y:auto;padding:8px;}
.qi{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:9px;cursor:pointer;transition:background .15s;}
.qi:hover,.qi.playing{background:rgba(124,58,237,.1);}
.qi-n{width:16px;font-size:.68rem;color:var(--muted);text-align:center;flex-shrink:0;}
.qi-name{font-size:.73rem;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.qi-lib{font-size:.62rem;color:var(--muted);}
.qi-del{opacity:0;background:none;border:none;color:var(--muted);cursor:pointer;font-size:.75rem;}
.qi:hover .qi-del{opacity:1;}

/* ── TOAST & KEY HINT ─────────────────────────────── */
.toast,.ktoast{position:fixed;left:50%;transform:translateX(-50%) translateY(12px);
  background:rgba(8,8,16,.95);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.07);
  border-radius:99px;padding:11px 22px;font-size:.78rem;color:var(--text);
  opacity:0;transition:opacity .25s,transform .25s;z-index:3000;white-space:nowrap;pointer-events:none;}
.toast{bottom:calc(var(--safe-bot) + 24px);}
.ktoast{top:68px;}
.toast.show,.ktoast.show{opacity:1;transform:translateX(-50%) translateY(0);}

/* ── FAB ──────────────────────────────────────────── */
#q-fab{position:fixed;bottom:calc(var(--safe-bot) + 22px);right:18px;z-index:500;
  width:50px;height:50px;border-radius:50%;background:var(--acc-g);border:none;color:#fff;
  font-size:1rem;cursor:pointer;box-shadow:0 8px 24px rgba(124,58,237,.4);
  display:none;align-items:center;justify-content:center;}
#q-fab.show{display:flex;}
#q-fab .q-cnt{position:absolute;top:-4px;right:-4px;width:18px;height:18px;
  background:#f59e0b;border-radius:50%;font-size:.6rem;font-weight:700;color:#000;
  display:flex;align-items:center;justify-content:center;}

/* ══════════════════════════════════════════════════════════
   PLAYER OVERLAY — GOD LEVEL MOBILE PLAYER
   ══════════════════════════════════════════════════════════ */
#overlay{
  display:none;position:fixed;inset:0;z-index:1000;
  background:#000;flex-direction:column;
  user-select:none;-webkit-user-select:none;
}
#overlay.show{display:flex;}

/* Video container */
#vid-wrap{
  position:relative;flex:1;display:flex;align-items:center;justify-content:center;
  overflow:hidden;background:#000;
}
video{width:100%;height:100%;object-fit:contain;display:block;}

/* ── TOP BAR ──────────────────────────────────────── */
.p-topbar{
  position:absolute;top:0;left:0;right:0;z-index:20;
  padding:calc(var(--safe-top) + 12px) 16px 28px;
  background:linear-gradient(to bottom,rgba(0,0,0,.85) 0%,transparent 100%);
  display:flex;align-items:center;gap:12px;
  transition:opacity .3s,transform .3s;
}
.p-topbar.hidden{opacity:0;transform:translateY(-10px);pointer-events:none;}
.p-back{width:38px;height:38px;border-radius:50%;background:rgba(255,255,255,.1);
  backdrop-filter:blur(8px);border:none;color:#fff;display:flex;align-items:center;
  justify-content:center;font-size:1rem;cursor:pointer;flex-shrink:0;}
.p-title-wrap{flex:1;min-width:0;}
.p-title{font-size:.82rem;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.p-subtitle{font-size:.68rem;color:rgba(255,255,255,.4);}
.p-topbtns{display:flex;gap:8px;}
.p-tbtn{width:34px;height:34px;border-radius:50%;background:rgba(255,255,255,.08);
  border:none;color:rgba(255,255,255,.8);display:flex;align-items:center;justify-content:center;
  font-size:.8rem;cursor:pointer;}
.p-tbtn:active{background:rgba(255,255,255,.2);}

/* ── DOUBLE TAP ZONE ──────────────────────────────── */
.tap-zone{position:absolute;top:0;bottom:0;width:40%;z-index:10;
  display:flex;align-items:center;justify-content:center;}
.tap-zone-l{left:0;}
.tap-zone-r{right:0;}
.tap-ripple{
  position:absolute;border-radius:50%;
  background:rgba(255,255,255,.15);
  width:100px;height:100px;margin:-50px;
  transform:scale(0);opacity:0;pointer-events:none;
  transition:none;
}
.tap-ripple.burst{
  animation:tapburst .5s ease-out forwards;
}
@keyframes tapburst{
  0%{transform:scale(0);opacity:.6;}
  100%{transform:scale(3);opacity:0;}
}
.tap-label{
  position:absolute;color:#fff;font-weight:700;font-size:.9rem;
  background:rgba(0,0,0,.4);backdrop-filter:blur(6px);
  border-radius:99px;padding:6px 14px;
  opacity:0;transform:scale(.8);transition:none;
  display:flex;align-items:center;gap:5px;pointer-events:none;
}
.tap-label.show{animation:taplabel .7s ease-out forwards;}
@keyframes taplabel{
  0%{opacity:0;transform:scale(.8);}
  20%{opacity:1;transform:scale(1);}
  70%{opacity:1;transform:scale(1);}
  100%{opacity:0;transform:scale(.9);}
}

/* ── CENTER TAP (play/pause) ──────────────────────── */
.center-tap{position:absolute;left:40%;right:40%;top:0;bottom:0;z-index:9;}

/* ── SIDE SLIDERS (brightness / volume) ──────────── */
.side-slider{
  position:absolute;top:15%;bottom:15%;width:28px;z-index:15;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:6px;opacity:0;transition:opacity .3s;pointer-events:none;
}
.side-slider.visible{opacity:1;}
.side-slider-l{left:10px;}
.side-slider-r{right:10px;}
.ss-track{flex:1;width:4px;background:rgba(255,255,255,.2);border-radius:2px;
  position:relative;max-height:160px;}
.ss-fill{position:absolute;bottom:0;left:0;right:0;border-radius:2px;transition:height .1s;}
.ss-icon{font-size:.85rem;opacity:.7;}

/* ── BOTTOM CONTROLS ──────────────────────────────── */
.p-botbar{
  position:absolute;bottom:0;left:0;right:0;z-index:20;
  padding:0 0 calc(var(--safe-bot) + 14px);
  background:linear-gradient(to top,rgba(0,0,0,.9) 0%,transparent 100%);
  transition:opacity .3s,transform .3s;
}
.p-botbar.hidden{opacity:0;transform:translateY(10px);pointer-events:none;}

/* Seek bar */
.seekbar-wrap{padding:0 14px 8px;position:relative;}
.seekbar-bg{height:4px;background:rgba(255,255,255,.18);border-radius:2px;position:relative;cursor:pointer;}
.seekbar-buf{position:absolute;top:0;left:0;height:100%;background:rgba(255,255,255,.25);border-radius:2px;transition:width .3s;}
.seekbar-fill{position:absolute;top:0;left:0;height:100%;background:var(--acc-g);border-radius:2px;transition:width .1s;}
.seekbar-thumb{position:absolute;top:50%;width:14px;height:14px;
  background:#fff;border-radius:50%;transform:translate(-50%,-50%);
  box-shadow:0 2px 8px rgba(0,0,0,.6);transition:transform .15s;cursor:grab;}
.seekbar-bg:hover .seekbar-thumb,.seekbar-bg:active .seekbar-thumb{transform:translate(-50%,-50%) scale(1.3);}
/* Preview bubble */
.seek-preview{
  position:absolute;bottom:18px;background:rgba(0,0,0,.8);backdrop-filter:blur(10px);
  border:1px solid rgba(255,255,255,.1);border-radius:8px;padding:5px 10px;
  font-size:.72rem;color:#fff;white-space:nowrap;transform:translateX(-50%);
  opacity:0;transition:opacity .15s;pointer-events:none;z-index:5;
}
.seek-preview.show{opacity:1;}

/* Time row */
.p-timerow{display:flex;align-items:center;justify-content:space-between;padding:0 14px 8px;}
.p-time{font-size:.72rem;color:rgba(255,255,255,.55);font-variant-numeric:tabular-nums;}
.p-time-dur{color:rgba(255,255,255,.3);}

/* Main controls row */
.p-ctrl{display:flex;align-items:center;justify-content:space-between;padding:0 14px 2px;}
.p-cbtn{width:44px;height:44px;border:none;background:transparent;color:#fff;
  display:flex;align-items:center;justify-content:center;cursor:pointer;border-radius:50%;
  font-size:1.1rem;transition:background .15s;}
.p-cbtn:active{background:rgba(255,255,255,.1);}
.p-cbtn.main{width:56px;height:56px;font-size:1.5rem;background:rgba(124,58,237,.8);
  backdrop-filter:blur(8px);border-radius:50%;border:2px solid rgba(255,255,255,.2);}
.p-cbtn.main:active{background:rgba(124,58,237,1);}

/* Extra controls row */
.p-extras{display:flex;align-items:center;justify-content:space-between;padding:6px 16px 0;}
.p-xbtn{display:flex;align-items:center;gap:4px;background:rgba(255,255,255,.07);
  border:none;border-radius:99px;padding:5px 12px;color:rgba(255,255,255,.65);
  font-size:.7rem;font-family:var(--font);cursor:pointer;transition:background .15s;}
.p-xbtn:active{background:rgba(255,255,255,.15);}
.p-xbtn.active{background:rgba(124,58,237,.2);color:#a78bfa;border:1px solid rgba(124,58,237,.25);}

/* Speed menu */
#speed-menu{
  position:absolute;bottom:120px;left:50%;transform:translateX(-50%);
  background:rgba(5,5,10,.95);border:1px solid rgba(255,255,255,.1);
  border-radius:16px;overflow:hidden;backdrop-filter:blur(20px);
  display:none;z-index:30;min-width:120px;
  box-shadow:0 20px 60px rgba(0,0,0,.7);
}
#speed-menu.show{display:block;}
.speed-opt{padding:11px 20px;font-size:.82rem;color:rgba(255,255,255,.6);cursor:pointer;text-align:center;}
.speed-opt:hover{background:rgba(124,58,237,.12);color:#a78bfa;}
.speed-opt.active{color:#a78bfa;font-weight:600;}

/* Sleep timer menu */
#sleep-menu{position:absolute;bottom:120px;right:14px;background:rgba(5,5,10,.95);
  border:1px solid rgba(255,255,255,.1);border-radius:16px;overflow:hidden;
  backdrop-filter:blur(20px);display:none;z-index:30;min-width:110px;}
#sleep-menu.show{display:block;}
.sleep-opt{padding:10px 18px;font-size:.78rem;color:rgba(255,255,255,.6);cursor:pointer;text-align:center;}
.sleep-opt:hover,.sleep-opt.active{background:rgba(124,58,237,.12);color:#a78bfa;}

/* A-B loop indicator */
.ab-indicator{
  position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
  background:rgba(0,0,0,.7);backdrop-filter:blur(10px);border:1px solid rgba(124,58,237,.3);
  border-radius:12px;padding:10px 20px;text-align:center;
  opacity:0;transition:opacity .3s;pointer-events:none;z-index:25;
}
.ab-indicator.show{opacity:1;}
.ab-text{font-size:.8rem;color:#a78bfa;font-weight:600;}
.ab-sub{font-size:.65rem;color:rgba(255,255,255,.4);margin-top:2px;}

/* Brightness overlay */
#brightness-overlay{
  position:absolute;inset:0;background:#000;pointer-events:none;z-index:5;
  opacity:0;transition:opacity .1s;
}

/* Skip animate overlay */
.skip-anim{
  position:absolute;display:flex;align-items:center;justify-content:center;
  top:0;bottom:0;z-index:18;pointer-events:none;width:40%;
}
.skip-anim-l{left:0;}
.skip-anim-r{right:0;}
.skip-svg{opacity:0;transition:none;}
.skip-svg.pop{animation:skippop .4s ease-out forwards;}
@keyframes skippop{0%{opacity:.8}100%{opacity:0}}

/* Loading spinner */
.vid-spinner{
  position:absolute;inset:0;display:none;align-items:center;justify-content:center;z-index:8;
}
.vid-spinner.show{display:flex;}
.spin-ring{width:44px;height:44px;border:3px solid rgba(255,255,255,.1);
  border-top-color:#a78bfa;border-radius:50%;animation:spin .8s linear infinite;}
@keyframes spin{to{transform:rotate(360deg)}}

/* Next video banner */
.next-banner{
  position:absolute;bottom:100px;right:14px;
  background:rgba(5,5,10,.9);border:1px solid rgba(255,255,255,.1);
  border-radius:14px;padding:12px 16px;max-width:200px;
  opacity:0;transform:translateX(20px);transition:all .35s;pointer-events:none;z-index:22;
}
.next-banner.show{opacity:1;transform:translateX(0);pointer-events:all;}
.nb-label{font-size:.62rem;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:4px;}
.nb-title{font-size:.75rem;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.nb-play{display:block;margin-top:8px;background:var(--acc-g);border:none;border-radius:8px;
  color:#fff;font-size:.72rem;padding:6px 14px;cursor:pointer;font-family:var(--font);width:100%;}

/* Cast overlay */
.cast-indicator{position:absolute;top:60px;right:14px;
  background:rgba(6,182,212,.12);border:1px solid rgba(6,182,212,.25);
  border-radius:99px;padding:5px 14px;font-size:.7rem;color:#22d3ee;
  opacity:0;transition:opacity .3s;pointer-events:none;}
.cast-indicator.show{opacity:1;}

/* Keyboard shortcuts modal */
#shortcuts-modal{display:none;position:fixed;inset:0;z-index:3000;
  background:rgba(0,0,0,.75);backdrop-filter:blur(10px);align-items:center;justify-content:center;}
#shortcuts-modal.open{display:flex;}
.sm-box{background:rgba(8,8,18,.98);border:1px solid rgba(255,255,255,.08);
  border-radius:20px;padding:28px;max-width:460px;width:90%;}
.sm-title{font-family:'Syne',sans-serif;font-size:1.4rem;font-weight:700;color:#fff;margin-bottom:18px;}
.sm-grid{display:grid;grid-template-columns:1fr 1fr;gap:7px;}
.sm-row{display:flex;align-items:center;justify-content:space-between;
  padding:7px 11px;background:var(--s1);border-radius:7px;}
.sm-key{background:var(--s3);border:1px solid rgba(255,255,255,.08);border-radius:5px;
  padding:2px 9px;font-size:.72rem;font-family:monospace;color:#c4b5fd;}
.sm-desc{font-size:.75rem;color:rgba(255,255,255,.45);}
.sm-close{margin-top:18px;width:100%;padding:11px;background:rgba(255,255,255,.05);
  border:1px solid rgba(255,255,255,.07);border-radius:9px;
  color:var(--muted);font-family:var(--font);font-size:.82rem;cursor:pointer;}

/* CMD Palette */
#cmd-overlay{display:none;position:fixed;inset:0;z-index:2000;
  background:rgba(0,0,0,.75);backdrop-filter:blur(10px);align-items:flex-start;
  justify-content:center;padding-top:12vh;}
#cmd-overlay.open{display:flex;}
.cmd-box{width:100%;max-width:540px;background:rgba(7,7,14,.98);
  border:1px solid rgba(255,255,255,.09);border-radius:18px;overflow:hidden;
  box-shadow:0 40px 100px rgba(0,0,0,.8);}
.cmd-input-wrap{display:flex;align-items:center;gap:12px;padding:14px 18px;
  border-bottom:1px solid rgba(255,255,255,.05);}
.cmd-input{flex:1;background:transparent;border:none;outline:none;
  color:var(--text);font-size:.95rem;font-family:var(--font);}
.cmd-input::placeholder{color:var(--muted);}
.cmd-results{max-height:320px;overflow-y:auto;padding:8px;}
.cmd-item{display:flex;align-items:center;gap:12px;padding:10px 12px;
  border-radius:9px;cursor:pointer;transition:background .12s;}
.cmd-item:hover,.cmd-item.focused{background:rgba(124,58,237,.12);}
.cmd-icon{font-size:.95rem;width:26px;text-align:center;flex-shrink:0;}
.cmd-label{font-size:.82rem;flex:1;}
.cmd-label mark{background:rgba(124,58,237,.3);color:#c4b5fd;border-radius:3px;padding:0 2px;}
.cmd-sub{font-size:.7rem;color:var(--muted);}
.cmd-section{font-size:.6rem;text-transform:uppercase;letter-spacing:2px;color:var(--muted);padding:7px 12px 3px;font-weight:600;}
.cmd-footer{padding:9px 14px;border-top:1px solid rgba(255,255,255,.04);display:flex;gap:14px;font-size:.65rem;color:var(--muted);}
.cmd-footer kbd{background:var(--s2);border:1px solid rgba(255,255,255,.06);border-radius:4px;padding:1px 6px;margin-right:3px;}

@media(max-width:480px){
  .search-wrap{max-width:160px;}
  .p-extras{flex-wrap:wrap;gap:5px;justify-content:center;padding-bottom:4px;}
  .sm-grid{grid-template-columns:1fr;}
}
/* portrait: taller video area */
@media(orientation:portrait){
  #vid-wrap{max-height:calc(100vh - 180px);}
}
@media(orientation:landscape){
  .p-botbar{padding-bottom:calc(var(--safe-bot) + 8px);}
  #vid-wrap{max-height:100vh;}
}
</style>
</head>
<body>

<!-- CMD PALETTE -->
<div id="cmd-overlay">
  <div class="cmd-box">
    <div class="cmd-input-wrap"><span style="color:var(--muted)">⌘</span>
      <input class="cmd-input" id="cmd-input" placeholder="Search or type a command…" autocomplete="off"></div>
    <div class="cmd-results" id="cmd-results"></div>
    <div class="cmd-footer"><span><kbd>↑↓</kbd>navigate</span><span><kbd>↵</kbd>select</span><span><kbd>Esc</kbd>close</span></div>
  </div>
</div>

<!-- SHORTCUTS MODAL -->
<div id="shortcuts-modal">
  <div class="sm-box">
    <div class="sm-title">Keyboard Shortcuts</div>
    <div class="sm-grid">
      <div class="sm-row"><span class="sm-key">Space</span><span class="sm-desc">Play/Pause</span></div>
      <div class="sm-row"><span class="sm-key">F</span><span class="sm-desc">Fullscreen</span></div>
      <div class="sm-row"><span class="sm-key">M</span><span class="sm-desc">Mute</span></div>
      <div class="sm-row"><span class="sm-key">N</span><span class="sm-desc">Next in queue</span></div>
      <div class="sm-row"><span class="sm-key">← →</span><span class="sm-desc">Seek ±10s</span></div>
      <div class="sm-row"><span class="sm-key">↑ ↓</span><span class="sm-desc">Volume ±10%</span></div>
      <div class="sm-row"><span class="sm-key">[ ]</span><span class="sm-desc">A-B loop marks</span></div>
      <div class="sm-row"><span class="sm-key">Esc</span><span class="sm-desc">Close player</span></div>
      <div class="sm-row"><span class="sm-key">⌘K</span><span class="sm-desc">Command palette</span></div>
      <div class="sm-row"><span class="sm-key">?</span><span class="sm-desc">This panel</span></div>
    </div>
    <button class="sm-close" onclick="document.getElementById('shortcuts-modal').classList.remove('open')">Close</button>
  </div>
</div>

<!-- HEADER -->
<header>
  <div class="logo">▶ Cine</div>
  <div class="search-wrap">
    <span class="s-ico">⌕</span>
    <input class="search-input" id="search" type="search" placeholder="Search…" autocomplete="off" spellcheck="false">
    <div class="search-results" id="search-results"></div>
  </div>
  <div class="hdr-right">
    <div class="vbtn-wrap">
      <button class="vbtn active" id="vbtn-grid" onclick="setView('grid')">⊞</button>
      <button class="vbtn" id="vbtn-list" onclick="setView('list')">☰</button>
    </div>
    <div class="user-chip" id="upill">Guest</div>
  </div>
</header>

<!-- HERO -->
<div id="hero" onclick="heroPlay()">
  <div id="hero-bg"></div>
  <div class="hero-overlay"></div>
  <div class="hero-content">
    <div class="hero-badge">⭐ Featured</div>
    <div class="hero-title" id="hero-title">Your Library</div>
    <div class="hero-meta"><span id="hero-lib">—</span> · <span id="hero-ext">—</span></div>
  </div>
  <div class="hero-play">▶</div>
</div>

<!-- FILTER BAR -->
<div class="filter-bar" id="filter-bar">
  <button class="fbtn active" onclick="setFilter('all',this)">All</button>
  {% for lib in data.keys() %}
  <button class="fbtn" onclick="setFilter('{{ lib }}',this)" data-lib="{{ lib }}">📁 {{ lib }}</button>
  {% endfor %}
  <div style="width:1px;height:18px;background:rgba(255,255,255,.06);flex-shrink:0;margin:0 2px;"></div>
  <select class="sort-select" onchange="sortVids(this.value)">
    <option value="name">A–Z</option>
    <option value="name-desc">Z–A</option>
    <option value="ext">By Type</option>
  </select>
</div>

<!-- CONTINUE WATCHING -->
<div id="continue-sec" style="display:none">
  <div class="stitle">Continue Watching</div>
  <div class="cscroll" id="cscroll"></div>
</div>

<!-- LIBRARY -->
{% if data %}
  {% for lib, files in data.items() %}{% if files %}
  <div class="stitle" data-lib="{{ lib }}">📁 {{ lib }}<span class="cnt">{{ files|length }}</span></div>
  <div class="lib-sec" data-lib="{{ lib }}">
    <div class="grid">
      {% for f in files %}{% set p = palette(f) %}
      <div class="vcard" onclick="play('{{ lib }}','{{ f }}')"
           data-name="{{ f.lower() }}" data-lib="{{ lib }}" data-file="{{ f }}" data-ext="{{ f.split('.')[-1].lower() }}">
        <div class="vthumb">
          <div class="vthumb-bg" style="position:absolute;inset:0;background:linear-gradient(135deg,{{ p[0] }}33,{{ p[1] }}44),radial-gradient(circle at 70% 30%,{{ p[0] }}22,transparent 60%);"></div>
          <span style="position:relative;z-index:1;font-size:1.5rem;opacity:.4;">🎬</span>
          <div class="vplay-btn"><div class="vplay-circle">▶</div></div>
          <svg class="prog-ring" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="9" fill="none" stroke="rgba(255,255,255,.12)" stroke-width="2"/>
            <circle cx="12" cy="12" r="9" fill="none" stroke="#7c3aed" stroke-width="2"
              stroke-dasharray="56.5" stroke-dashoffset="56.5" stroke-linecap="round"
              transform="rotate(-90 12 12)" class="prog-arc" data-key="{{ lib }}|||{{ f }}"/>
          </svg>
          <button class="add-q" onclick="addQueue('{{ lib }}','{{ f }}',event)">+</button>
        </div>
        <div class="vinfo">
          <div class="vname">{{ f|replace('_',' ')|replace('.',' ') }}</div>
          <div class="vmeta">
            <span class="vext">{{ f.split('.')[-1] }}</span>
            <span class="vwatch" data-key="{{ lib }}|||{{ f }}"></span>
          </div>
        </div>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}{% endfor %}
{% else %}
  <div class="empty"><div class="empty-ico">📭</div>
    <p style="font-size:.84rem;line-height:1.8;color:var(--muted);">No videos yet.<br>Add folders in the desktop app.</p>
  </div>
{% endif %}

<!-- ═══════════════════════════════════════════════════════════
     GOD-LEVEL PLAYER OVERLAY
     ═══════════════════════════════════════════════════════════ -->
<div id="overlay">

  <!-- brightness overlay -->
  <div id="brightness-overlay"></div>

  <!-- video container -->
  <div id="vid-wrap">

    <!-- actual video -->
    <video id="player" playsinline webkit-playsinline preload="metadata"
           controlsList="nodownload" disablePictureInPicture="false"></video>

    <!-- loading spinner -->
    <div class="vid-spinner" id="vid-spinner">
      <div class="spin-ring"></div>
    </div>

    <!-- TOP BAR -->
    <div class="p-topbar" id="p-topbar">
      <button class="p-back" id="p-back">←</button>
      <div class="p-title-wrap">
        <div class="p-title" id="p-title">Now Playing</div>
        <div class="p-subtitle" id="p-subtitle"></div>
      </div>
      <div class="p-topbtns">
        <button class="p-tbtn" id="pip-btn" title="Picture in Picture" onclick="togglePiP()">⧉</button>
        <button class="p-tbtn" id="cast-btn" title="Cast" onclick="toggleCast()">📡</button>
        <button class="p-tbtn" id="sub-btn" title="Subtitles" onclick="toggleSubs()">CC</button>
        <button class="p-tbtn" id="lock-btn" title="Lock controls" onclick="toggleLock()">🔓</button>
      </div>
    </div>

    <!-- CAST INDICATOR -->
    <div class="cast-indicator" id="cast-indicator">📡 Casting…</div>

    <!-- DOUBLE TAP ZONES -->
    <div class="tap-zone tap-zone-l" id="tap-l">
      <div class="tap-ripple" id="ripple-l"></div>
      <div class="tap-label" id="label-l">⏪ 10s</div>
    </div>
    <div class="center-tap" id="center-tap"></div>
    <div class="tap-zone tap-zone-r" id="tap-r">
      <div class="tap-ripple" id="ripple-r"></div>
      <div class="tap-label" id="label-r">10s ⏩</div>
    </div>

    <!-- SIDE SLIDERS -->
    <div class="side-slider side-slider-l" id="vol-slider">
      <div class="ss-icon">🔊</div>
      <div class="ss-track"><div class="ss-fill" id="vol-fill" style="background:#a78bfa;height:70%;"></div></div>
    </div>
    <div class="side-slider side-slider-r" id="bri-slider">
      <div class="ss-icon">☀️</div>
      <div class="ss-track"><div class="ss-fill" id="bri-fill" style="background:#f59e0b;height:80%;"></div></div>
    </div>

    <!-- AB LOOP INDICATOR -->
    <div class="ab-indicator" id="ab-indicator">
      <div class="ab-text">A-B Loop</div>
      <div class="ab-sub" id="ab-sub">Set point A</div>
    </div>

    <!-- SPEED MENU -->
    <div id="speed-menu">
      <div class="speed-opt active" data-spd="1">1× Normal</div>
      <div class="speed-opt" data-spd="0.5">0.5×</div>
      <div class="speed-opt" data-spd="0.75">0.75×</div>
      <div class="speed-opt" data-spd="1.25">1.25×</div>
      <div class="speed-opt" data-spd="1.5">1.5×</div>
      <div class="speed-opt" data-spd="2">2×</div>
    </div>

    <!-- SLEEP TIMER MENU -->
    <div id="sleep-menu">
      <div class="sleep-opt" data-min="0">Off</div>
      <div class="sleep-opt" data-min="10">10 min</div>
      <div class="sleep-opt" data-min="20">20 min</div>
      <div class="sleep-opt" data-min="30">30 min</div>
      <div class="sleep-opt" data-min="60">1 hour</div>
    </div>

    <!-- NEXT VIDEO BANNER -->
    <div class="next-banner" id="next-banner">
      <div class="nb-label">Up Next</div>
      <div class="nb-title" id="nb-title">—</div>
      <button class="nb-play" onclick="playNext()">▶ Play Now</button>
    </div>

    <!-- BOTTOM BAR -->
    <div class="p-botbar" id="p-botbar">

      <!-- Seek bar -->
      <div class="seekbar-wrap">
        <div class="seekbar-bg" id="seekbar">
          <div class="seekbar-buf" id="seekbuf" style="width:0%"></div>
          <div class="seekbar-fill" id="seekfill" style="width:0%"></div>
          <div class="seekbar-thumb" id="seekthumb" style="left:0%"></div>
          <div class="seek-preview" id="seek-preview">0:00</div>
        </div>
      </div>

      <!-- Time -->
      <div class="p-timerow">
        <span class="p-time" id="p-cur">0:00</span>
        <span class="p-time p-time-dur" id="p-dur">—</span>
      </div>

      <!-- Main controls -->
      <div class="p-ctrl">
        <button class="p-cbtn" id="vol-btn" onclick="toggleMute()">🔊</button>
        <button class="p-cbtn" onclick="seekRel(-10)">⏪</button>
        <button class="p-cbtn main" id="play-btn" onclick="togglePlay()">▶</button>
        <button class="p-cbtn" onclick="seekRel(10)">⏩</button>
        <button class="p-cbtn" onclick="toggleFullscreen()">⛶</button>
      </div>

      <!-- Extra controls -->
      <div class="p-extras">
        <button class="p-xbtn" id="speed-btn" onclick="toggleSpeedMenu()">⚡ 1×</button>
        <button class="p-xbtn" id="ab-btn" onclick="cycleAB()">🔁 A-B</button>
        <button class="p-xbtn" id="next-btn" onclick="playNext()">⏭ Next</button>
        <button class="p-xbtn" id="sleep-btn" onclick="toggleSleepMenu()">💤 Sleep</button>
        <button class="p-xbtn" onclick="shareTimestamp()">🔗 Share</button>
      </div>

    </div><!-- /p-botbar -->
  </div><!-- /vid-wrap -->
</div><!-- /overlay -->

<!-- QUEUE PANEL -->
<div id="queue-panel">
  <div class="qp-header">
    <div class="qp-title">⏭ Queue <span id="q-count" style="color:var(--muted);font-size:.72rem;"></span></div>
    <button class="qp-close" onclick="toggleQueue()">✕</button>
  </div>
  <div class="qp-list" id="q-list"></div>
</div>
<button id="q-fab" onclick="toggleQueue()">⏭<span class="q-cnt" id="q-badge">0</span></button>

<!-- TOASTS -->
<div class="ktoast" id="ktoast"></div>
<div class="toast" id="toast"></div>

<script>
// ══════════════════════════════════════════════════════════
//  STATE
// ══════════════════════════════════════════════════════════
const vid = document.getElementById('player');
let curLib='', curFile='';
let saveT=null, hideT=null, controlsVisible=true, controlsLocked=false;
let hist = JSON.parse(localStorage.getItem('cs_hist')||'{}');
let queue=[], qIdx=-1;
let viewMode = localStorage.getItem('cs_view')||'grid';
let vol = parseFloat(localStorage.getItem('cs_vol')||'0.8');
let brightness = 1.0;
let abA = null, abB = null, abState = 0; // 0=off 1=A set 2=AB set
let sleepTimer = null, sleepMinutes = 0;
let currentSpeed = 1;
let cmdFocusIdx=-1, srFocusIdx=-1;
let seeking=false, seekStart=0;
let isDraggingSeek = false;

const ALL_VIDEOS = [];
document.querySelectorAll('.vcard').forEach(c=>{
  ALL_VIDEOS.push({lib:c.dataset.lib, file:c.dataset.file,
    name:c.dataset.file.replace(/[_.]/g,' ')});
});

// ── Init ──────────────────────────────────────────────
vid.volume = vol;
document.getElementById('vol-fill').style.height = (vol*100)+'%';
fetch('/api/me').then(r=>r.json()).then(d=>{
  if(d.name) document.getElementById('upill').textContent='👤 '+d.name;
}).catch(()=>{});
setView(viewMode,true);
buildContinue();
renderProgressArcs();
setupHero();
setupMediaSession();

// ══════════════════════════════════════════════════════════
//  COLOUR UTILITY
// ══════════════════════════════════════════════════════════
function getColors(name){
  const p=[["#7c3aed","#4f46e5"],["#db2777","#7c3aed"],["#0891b2","#0e7490"],
           ["#059669","#0891b2"],["#d97706","#dc2626"],["#be185d","#9333ea"],
           ["#1d4ed8","#0891b2"],["#7c3aed","#db2777"]];
  let h=0;for(const c of name)h=(h*31+c.charCodeAt(0))&0xffff;
  return p[h%p.length];
}

// ══════════════════════════════════════════════════════════
//  HERO
// ══════════════════════════════════════════════════════════
let heroVid=null;
function setupHero(){
  if(!ALL_VIDEOS.length){document.getElementById('hero').style.display='none';return;}
  heroVid=ALL_VIDEOS[Math.floor(Math.random()*ALL_VIDEOS.length)];
  const[c1,c2]=getColors(heroVid.file);
  document.getElementById('hero-bg').style.cssText=
    `position:absolute;inset:0;background:linear-gradient(135deg,${c1}99,${c2}77,#050508);`;
  document.getElementById('hero-title').textContent=heroVid.file.replace(/[_.]/g,' ').replace(/\.[^.]+$/,'');
  document.getElementById('hero-lib').textContent=heroVid.lib;
  document.getElementById('hero-ext').textContent=heroVid.file.split('.').pop().toUpperCase();
}
function heroPlay(){if(heroVid)play(heroVid.lib,heroVid.file);}

// ══════════════════════════════════════════════════════════
//  PROGRESS ARCS
// ══════════════════════════════════════════════════════════
function renderProgressArcs(){
  document.querySelectorAll('.prog-arc').forEach(arc=>{
    const k=arc.dataset.key, dur=hist[k+'_dur']||1, pos=hist[k]||0, pct=Math.min(1,pos/dur);
    if(pct>0.02){
      arc.setAttribute('stroke-dashoffset',56.5-(56.5*pct));
      arc.closest('.prog-ring').style.opacity='1';
    }
    const wa=arc.closest('.vcard')?.querySelector('.vwatch');
    if(wa&&pct>0.02)wa.textContent=Math.round(pct*100)+'%';
  });
}

// ══════════════════════════════════════════════════════════
//  VIEW TOGGLE
// ══════════════════════════════════════════════════════════
function setView(mode,skip){
  viewMode=mode;if(!skip)localStorage.setItem('cs_view',mode);
  document.querySelectorAll('.lib-sec').forEach(s=>s.classList.toggle('list-view',mode==='list'));
  document.getElementById('vbtn-grid').classList.toggle('active',mode==='grid');
  document.getElementById('vbtn-list').classList.toggle('active',mode==='list');
}

// ══════════════════════════════════════════════════════════
//  FILTER & SORT
// ══════════════════════════════════════════════════════════
function setFilter(lib,btn){
  document.querySelectorAll('.fbtn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('[data-lib]').forEach(el=>{
    if(el.classList.contains('lib-sec')||el.classList.contains('stitle'))
      el.style.display=(lib==='all'||el.dataset.lib===lib)?'':'none';
  });
}
function sortVids(mode){
  document.querySelectorAll('.grid').forEach(grid=>{
    const cards=[...grid.querySelectorAll('.vcard')];
    cards.sort((a,b)=>mode==='name'?a.dataset.name.localeCompare(b.dataset.name):
                      mode==='name-desc'?b.dataset.name.localeCompare(a.dataset.name):
                      a.dataset.ext.localeCompare(b.dataset.ext));
    cards.forEach(c=>grid.appendChild(c));
  });
}

// ══════════════════════════════════════════════════════════
//  LIVE SEARCH
// ══════════════════════════════════════════════════════════
const searchEl=document.getElementById('search');
const srPanel=document.getElementById('search-results');
function highlight(t,q){
  if(!q)return t;
  return t.replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'gi'),m=>`<mark>${m}</mark>`);
}
function fuzzyScore(n,q){
  n=n.toLowerCase();q=q.toLowerCase();
  if(n.includes(q))return 2;
  let s=0;for(const c of q){s=n.indexOf(c,s);if(s===-1)return 0;s++;}return 1;
}
searchEl.addEventListener('input',()=>{
  const q=searchEl.value.trim();srFocusIdx=-1;
  if(!q){srPanel.classList.remove('open');return;}
  const res=ALL_VIDEOS.map(v=>({...v,sc:fuzzyScore(v.name,q)})).filter(v=>v.sc>0)
    .sort((a,b)=>b.sc-a.sc).slice(0,10);
  srPanel.innerHTML=res.length
    ? res.map((v,i)=>{const[c1,c2]=getColors(v.file);return`
        <div class="sr-item" data-i="${i}" onclick="play('${v.lib}','${v.file}');closeSR()">
          <div class="sr-thumb" style="background:linear-gradient(135deg,${c1}44,${c2}44)">🎬</div>
          <div><div class="sr-name">${highlight(v.name.replace(/\.[^.]+$/,''),q)}</div>
          <div class="sr-lib">📁 ${v.lib}</div></div>
        </div>`}).join('')
    : `<div style="padding:24px;text-align:center;color:var(--muted);font-size:.8rem;">No results</div>`;
  srPanel.classList.add('open');
});
searchEl.addEventListener('keydown',e=>{
  const items=srPanel.querySelectorAll('.sr-item');
  if(e.key==='ArrowDown'){e.preventDefault();srFocusIdx=Math.min(srFocusIdx+1,items.length-1);}
  else if(e.key==='ArrowUp'){e.preventDefault();srFocusIdx=Math.max(srFocusIdx-1,0);}
  else if(e.key==='Enter'&&srFocusIdx>=0){items[srFocusIdx].click();}
  else if(e.key==='Escape'){closeSR();searchEl.blur();}
  items.forEach((el,i)=>el.classList.toggle('focused',i===srFocusIdx));
});
function closeSR(){srPanel.classList.remove('open');searchEl.value='';srFocusIdx=-1;}
document.addEventListener('click',e=>{if(!e.target.closest('.search-wrap'))closeSR();});

// ══════════════════════════════════════════════════════════
//  COMMAND PALETTE
// ══════════════════════════════════════════════════════════
const cmdOverlay=document.getElementById('cmd-overlay');
const cmdInput=document.getElementById('cmd-input');
const cmdResultsEl=document.getElementById('cmd-results');
const CMDS=[
  {i:'?',l:'Keyboard Shortcuts',s:'All hotkeys',a:()=>document.getElementById('shortcuts-modal').classList.add('open')},
  {i:'⊞',l:'Grid View',s:'Switch layout',a:()=>setView('grid')},
  {i:'☰',l:'List View',s:'Switch layout',a:()=>setView('list')},
  {i:'⏭',l:'Toggle Queue',s:'Open/close',a:toggleQueue},
  {i:'🔀',l:'Shuffle Play',s:'Random video',a:shufflePlay},
  {i:'💤',l:'Sleep Timer',s:'Auto-stop playback',a:()=>document.getElementById('sleep-menu').classList.toggle('show')},
];
function openCmd(){cmdOverlay.classList.add('open');cmdInput.value='';renderCmd('');cmdInput.focus();}
function closeCmd(){cmdOverlay.classList.remove('open');cmdFocusIdx=-1;}
function renderCmd(q){
  const vids=q?ALL_VIDEOS.map(v=>({...v,sc:fuzzyScore(v.name,q)})).filter(v=>v.sc>0)
    .sort((a,b)=>b.sc-a.sc).slice(0,5):ALL_VIDEOS.slice(0,3);
  const cmds2=q?CMDS.filter(c=>c.l.toLowerCase().includes(q.toLowerCase())):CMDS;
  let h='';
  if(vids.length){h+=`<div class="cmd-section">Videos</div>`;
    h+=vids.map((v,i)=>`<div class="cmd-item" data-i="${i}" onclick="play('${v.lib}','${v.file}');closeCmd()">
      <div class="cmd-icon">🎬</div><div class="cmd-label">${highlight(v.name.replace(/\.[^.]+$/,''),q)}</div>
      <div class="cmd-sub">${v.lib}</div></div>`).join('');}
  if(cmds2.length){h+=`<div class="cmd-section">Actions</div>`;
    h+=cmds2.map((c,i)=>`<div class="cmd-item" data-i="${i+vids.length}" onclick="(${c.a})();closeCmd()">
      <div class="cmd-icon">${c.i}</div><div class="cmd-label">${c.l}</div>
      <div class="cmd-sub">${c.s}</div></div>`).join('');}
  if(!h)h=`<div style="padding:24px;text-align:center;color:var(--muted);font-size:.8rem;">No results</div>`;
  cmdResultsEl.innerHTML=h;cmdFocusIdx=-1;
}
cmdInput.addEventListener('input',()=>renderCmd(cmdInput.value.trim()));
cmdInput.addEventListener('keydown',e=>{
  const items=cmdResultsEl.querySelectorAll('.cmd-item');
  if(e.key==='ArrowDown'){e.preventDefault();cmdFocusIdx=Math.min(cmdFocusIdx+1,items.length-1);}
  else if(e.key==='ArrowUp'){e.preventDefault();cmdFocusIdx=Math.max(cmdFocusIdx-1,0);}
  else if(e.key==='Enter'){e.preventDefault();if(cmdFocusIdx>=0)items[cmdFocusIdx].click();else if(items[0])items[0].click();}
  else if(e.key==='Escape')closeCmd();
  items.forEach((el,i)=>el.classList.toggle('focused',i===cmdFocusIdx));
});
cmdOverlay.addEventListener('click',e=>{if(e.target===cmdOverlay)closeCmd();});

// ══════════════════════════════════════════════════════════
//  QUEUE
// ══════════════════════════════════════════════════════════
function addQueue(lib,file,e){
  if(e)e.stopPropagation();
  queue.push({lib,file});renderQueue();
  toast(`➕ ${file.replace(/[_.]/g,' ').replace(/\.[^.]+$/,'').slice(0,30)}`);
  document.getElementById('q-fab').classList.add('show');
}
function renderQueue(){
  const list=document.getElementById('q-list');
  const cnt=document.getElementById('q-count');
  const badge=document.getElementById('q-badge');
  cnt.textContent=queue.length?`(${queue.length})`:'';
  badge.textContent=queue.length;
  if(!queue.length){list.innerHTML=`<div style="padding:32px;text-align:center;color:var(--muted);font-size:.78rem;">Queue empty.<br>Hover a card and tap + to add.</div>`;return;}
  list.innerHTML=queue.map((v,i)=>`
    <div class="qi${i===qIdx?' playing':''}" onclick="playQueueItem(${i})">
      <div class="qi-n">${i===qIdx?'▶':i+1}</div>
      <div><div class="qi-name">${v.file.replace(/[_.]/g,' ').replace(/\.[^.]+$/,'')}</div>
      <div class="qi-lib">${v.lib}</div></div>
      <button class="qi-del" onclick="removeQueue(${i},event)">✕</button>
    </div>`).join('');
}
function removeQueue(i,e){e.stopPropagation();queue.splice(i,1);if(qIdx>=i)qIdx--;renderQueue();}
function playQueueItem(i){qIdx=i;play(queue[i].lib,queue[i].file);renderQueue();}
function toggleQueue(){document.getElementById('queue-panel').classList.toggle('open');}
function playNext(){
  if(!queue.length){toast('Queue is empty');return;}
  qIdx=qIdx<queue.length-1?qIdx+1:0;
  play(queue[qIdx].lib,queue[qIdx].file);renderQueue();
  hideNextBanner();
}
function shufflePlay(){
  if(!ALL_VIDEOS.length)return;
  const v=ALL_VIDEOS[Math.floor(Math.random()*ALL_VIDEOS.length)];play(v.lib,v.file);
}

// ══════════════════════════════════════════════════════════
//  CONTINUE WATCHING
// ══════════════════════════════════════════════════════════
function buildContinue(){
  const keys=Object.keys(hist).filter(k=>!k.endsWith('_dur')&&hist[k]>5);
  const cs=document.getElementById('continue-sec');
  if(!keys.length){cs.style.display='none';return;}
  cs.style.display='block';
  const sc=document.getElementById('cscroll');sc.innerHTML='';
  keys.slice(-12).reverse().forEach(k=>{
    const[lib,file]=k.split('|||');if(!lib||!file)return;
    const dur=hist[k+'_dur']||1,pct=Math.min(100,Math.round((hist[k]/dur)*100));
    const[c1,c2]=getColors(file);
    const d=document.createElement('div');d.className='ccard';
    d.innerHTML=`<div class="cthumb" style="background:linear-gradient(135deg,${c1}44,${c2}44)">
      <span style="font-size:1.4rem;opacity:.45">🎬</span>
      <div class="cprog" style="width:${pct}%"></div></div>
      <div class="cinfo"><div class="cname">${file.replace(/[_.]/g,' ').replace(/\.[^.]+$/,'')}</div>
      <div class="cpct">${pct}% watched</div></div>`;
    d.onclick=()=>play(lib,file,hist[k]);sc.appendChild(d);
  });
}

// ══════════════════════════════════════════════════════════
//  FORMAT TIME
// ══════════════════════════════════════════════════════════
function fmt(s){
  if(!isFinite(s)||s<0)return '0:00';
  s=Math.floor(s);const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=s%60;
  return h?`${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`:`${m}:${String(sec).padStart(2,'0')}`;
}

// ══════════════════════════════════════════════════════════
//  VIDEO EVENTS
// ══════════════════════════════════════════════════════════
vid.addEventListener('timeupdate',()=>{
  if(!vid.duration||isDraggingSeek)return;
  const pct=(vid.currentTime/vid.duration)*100;
  document.getElementById('seekfill').style.width=pct+'%';
  document.getElementById('seekthumb').style.left=pct+'%';
  document.getElementById('p-cur').textContent=fmt(vid.currentTime);
  // A-B loop
  if(abState===2&&abB!==null&&vid.currentTime>=abB){vid.currentTime=abA;}
  // next video banner
  if(queue.length>1&&vid.duration-vid.currentTime<20)showNextBanner();
  else hideNextBanner();
  // save
  if(!saveT)return;
  const k=curLib+'|||'+curFile;hist[k]=vid.currentTime;hist[k+'_dur']=vid.duration;
  localStorage.setItem('cs_hist',JSON.stringify(hist));
  // Media session
  if('mediaSession' in navigator&&vid.duration){
    navigator.mediaSession.setPositionState({duration:vid.duration,position:vid.currentTime,playbackRate:vid.playbackRate});
  }
});
vid.addEventListener('durationchange',()=>{
  document.getElementById('p-dur').textContent=fmt(vid.duration);
});
vid.addEventListener('progress',()=>{
  if(vid.buffered.length&&vid.duration){
    const b=vid.buffered.end(vid.buffered.length-1)/vid.duration*100;
    document.getElementById('seekbuf').style.width=b+'%';
  }
});
vid.addEventListener('waiting',()=>document.getElementById('vid-spinner').classList.add('show'));
vid.addEventListener('canplay',()=>document.getElementById('vid-spinner').classList.remove('show'));
vid.addEventListener('playing',()=>{
  document.getElementById('vid-spinner').classList.remove('show');
  document.getElementById('play-btn').textContent='⏸';
  updateMediaSession('playing');
});
vid.addEventListener('pause',()=>{
  document.getElementById('play-btn').textContent='▶';
  updateMediaSession('paused');
});
vid.addEventListener('ended',()=>{
  document.getElementById('play-btn').textContent='▶';
  setTimeout(playNext,1500);
});
vid.addEventListener('volumechange',()=>{
  const v=vid.muted?0:vid.volume;
  document.getElementById('vol-btn').textContent=v===0?'🔇':v<.5?'🔉':'🔊';
  document.getElementById('vol-fill').style.height=(v*100)+'%';
  localStorage.setItem('cs_vol',vid.volume);
});

// ══════════════════════════════════════════════════════════
//  PLAY FUNCTION
// ══════════════════════════════════════════════════════════
function play(lib,file,startAt=0){
  curLib=lib;curFile=file;
  abA=null;abB=null;abState=0;updateABUI();
  document.getElementById('overlay').classList.add('show');
  document.getElementById('p-title').textContent=file.replace(/[_.]/g,' ').replace(/\.[^.]+$/,'');
  document.getElementById('p-subtitle').textContent=lib;
  document.body.style.overflow='hidden';
  vid.src=`/stream/${encodeURIComponent(lib)}/${encodeURIComponent(file)}`;
  vid.load();
  const onMeta=()=>{
    if(startAt>8)vid.currentTime=Math.max(0,startAt-2);
    vid.play().catch(()=>{});
    vid.removeEventListener('loadedmetadata',onMeta);
  };
  vid.addEventListener('loadedmetadata',onMeta);
  clearInterval(saveT);
  saveT=setInterval(()=>{
    if(!vid.duration)return;
    const k=curLib+'|||'+curFile;hist[k]=vid.currentTime;hist[k+'_dur']=vid.duration;
    localStorage.setItem('cs_hist',JSON.stringify(hist));
    fetch('/api/progress',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({lib,file,pos:vid.currentTime})}).catch(()=>{});
  },5000);
  showControls();
  updateMediaSession('playing',file);
}

function stopPlayer(){
  clearInterval(saveT);saveT=null;
  vid.pause();vid.src='';
  document.getElementById('overlay').classList.remove('show');
  document.body.style.overflow='';
  buildContinue();renderProgressArcs();
  hideNextBanner();
}

document.getElementById('p-back').addEventListener('click',stopPlayer);

// ══════════════════════════════════════════════════════════
//  CONTROLS VISIBILITY
// ══════════════════════════════════════════════════════════
function showControls(){
  if(controlsLocked)return;
  controlsVisible=true;
  document.getElementById('p-topbar').classList.remove('hidden');
  document.getElementById('p-botbar').classList.remove('hidden');
  resetHideTimer();
}
function hideControls(){
  if(controlsLocked)return;
  controlsVisible=false;
  document.getElementById('p-topbar').classList.add('hidden');
  document.getElementById('p-botbar').classList.add('hidden');
  document.getElementById('speed-menu').classList.remove('show');
  document.getElementById('sleep-menu').classList.remove('show');
}
function resetHideTimer(){
  clearTimeout(hideT);
  if(!vid.paused)hideT=setTimeout(hideControls,3500);
}
function toggleControlsVis(){
  if(controlsVisible)hideControls();
  else showControls();
}
document.getElementById('center-tap').addEventListener('click',toggleControlsVis);
document.getElementById('vid-wrap').addEventListener('mousemove',showControls);
document.getElementById('vid-wrap').addEventListener('touchstart',()=>{if(!controlsVisible)showControls();},{ passive:true});

// ══════════════════════════════════════════════════════════
//  LOCK CONTROLS
// ══════════════════════════════════════════════════════════
function toggleLock(){
  controlsLocked=!controlsLocked;
  document.getElementById('lock-btn').textContent=controlsLocked?'🔒':'🔓';
  if(controlsLocked){
    document.getElementById('p-topbar').classList.add('hidden');
    document.getElementById('p-botbar').classList.add('hidden');
    toast('🔒 Controls locked');
  } else {
    showControls();toast('🔓 Controls unlocked');
  }
}

// ══════════════════════════════════════════════════════════
//  PLAY / PAUSE / SEEK
// ══════════════════════════════════════════════════════════
function togglePlay(){
  if(vid.paused){vid.play().catch(()=>{});}else vid.pause();
  showControls();
}
function seekRel(s){
  vid.currentTime=Math.max(0,Math.min(vid.duration||0,vid.currentTime+s));
  showControls();
}
function seekAbs(pct){
  if(!vid.duration)return;
  vid.currentTime=pct*vid.duration;
}
function toggleMute(){vid.muted=!vid.muted;showControls();}
function toggleFullscreen(){
  const el=document.getElementById('overlay');
  if(!document.fullscreenElement&&!document.webkitFullscreenElement){
    (el.requestFullscreen||el.webkitRequestFullscreen).call(el);
  } else {
    (document.exitFullscreen||document.webkitExitFullscreen).call(document);
  }
  showControls();
}

// ══════════════════════════════════════════════════════════
//  DOUBLE TAP TO SEEK
// ══════════════════════════════════════════════════════════
let tapCountL=0,tapCountR=0,tapTimerL=null,tapTimerR=null;

function fireTap(side){
  if(side==='l'){
    tapCountL++;clearTimeout(tapTimerL);
    tapTimerL=setTimeout(()=>{
      if(tapCountL>=2){doSeek('l',tapCountL);}
      else{toggleControlsVis();}
      tapCountL=0;
    },250);
  } else {
    tapCountR++;clearTimeout(tapTimerR);
    tapTimerR=setTimeout(()=>{
      if(tapCountR>=2){doSeek('r',tapCountR);}
      else{toggleControlsVis();}
      tapCountR=0;
    },250);
  }
}

function doSeek(side,taps){
  const secs=taps*10;
  if(side==='l'){seekRel(-secs);showTapAnim('l',`⏪ ${secs}s`);}
  else{seekRel(secs);showTapAnim('r',`${secs}s ⏩`);}
}

function showTapAnim(side,label){
  const ripple=document.getElementById('ripple-'+side);
  const lbl=document.getElementById('label-'+side);
  ripple.classList.remove('burst');void ripple.offsetWidth;ripple.classList.add('burst');
  lbl.textContent=label;lbl.classList.remove('show');void lbl.offsetWidth;lbl.classList.add('show');
}

document.getElementById('tap-l').addEventListener('click',()=>fireTap('l'));
document.getElementById('tap-r').addEventListener('click',()=>fireTap('r'));

// ══════════════════════════════════════════════════════════
//  SEEK BAR
// ══════════════════════════════════════════════════════════
const seekbarEl=document.getElementById('seekbar');
const previewEl=document.getElementById('seek-preview');

function getSeekPct(e){
  const rect=seekbarEl.getBoundingClientRect();
  const x=(e.clientX??e.touches?.[0]?.clientX??0)-rect.left;
  return Math.max(0,Math.min(1,x/rect.width));
}

function updateSeekPreview(pct){
  if(!vid.duration)return;
  const t=pct*vid.duration;
  previewEl.textContent=fmt(t);
  const pctClamped=Math.max(5,Math.min(95,pct*100));
  previewEl.style.left=pctClamped+'%';
  previewEl.classList.add('show');
}

seekbarEl.addEventListener('mousedown',e=>{
  isDraggingSeek=true;showControls();
  const pct=getSeekPct(e);seekAbs(pct);updateSeekPreview(pct);
  document.getElementById('seekfill').style.width=(pct*100)+'%';
  document.getElementById('seekthumb').style.left=(pct*100)+'%';
});
document.addEventListener('mousemove',e=>{
  if(!isDraggingSeek)return;
  const pct=getSeekPct(e);updateSeekPreview(pct);
  document.getElementById('seekfill').style.width=(pct*100)+'%';
  document.getElementById('seekthumb').style.left=(pct*100)+'%';
});
document.addEventListener('mouseup',e=>{
  if(!isDraggingSeek)return;
  isDraggingSeek=false;previewEl.classList.remove('show');
  seekAbs(getSeekPct(e));
});
seekbarEl.addEventListener('mouseleave',()=>{if(!isDraggingSeek)previewEl.classList.remove('show');});

// Touch seek
let seekTouchId=null;
seekbarEl.addEventListener('touchstart',e=>{
  e.stopPropagation();seekTouchId=e.touches[0].identifier;isDraggingSeek=true;showControls();
  const pct=getSeekPct(e.touches[0]);updateSeekPreview(pct);
  document.getElementById('seekfill').style.width=(pct*100)+'%';
  document.getElementById('seekthumb').style.left=(pct*100)+'%';
},{passive:false});
document.addEventListener('touchmove',e=>{
  if(!isDraggingSeek)return;
  const t=[...e.changedTouches].find(t=>t.identifier===seekTouchId);
  if(!t)return;e.preventDefault();
  const pct=getSeekPct(t);updateSeekPreview(pct);
  document.getElementById('seekfill').style.width=(pct*100)+'%';
  document.getElementById('seekthumb').style.left=(pct*100)+'%';
},{passive:false});
document.addEventListener('touchend',e=>{
  if(!isDraggingSeek)return;
  const t=[...e.changedTouches].find(t=>t.identifier===seekTouchId);
  if(t){isDraggingSeek=false;previewEl.classList.remove('show');seekAbs(getSeekPct(t));}
});

// ══════════════════════════════════════════════════════════
//  SWIPE GESTURES (portrait: up/down=volume; landscape: L/R=seek)
// ══════════════════════════════════════════════════════════
let gestX=null,gestY=null,gestMode=null,gestVol0=null,gestBri0=null;

document.getElementById('vid-wrap').addEventListener('touchstart',e=>{
  if(isDraggingSeek)return;
  const t=e.touches[0];gestX=t.clientX;gestY=t.clientY;
  gestMode=null;gestVol0=vid.volume;gestBri0=brightness;
},{passive:true});

document.getElementById('vid-wrap').addEventListener('touchmove',e=>{
  if(isDraggingSeek||!gestX)return;
  const t=e.touches[0];
  const dx=t.clientX-gestX,dy=t.clientY-gestY;
  if(!gestMode){
    if(Math.abs(dx)>20&&Math.abs(dx)>Math.abs(dy)*1.2){gestMode='seek';}
    else if(Math.abs(dy)>20&&Math.abs(dy)>Math.abs(dx)*1.2){
      gestMode=t.clientX<window.innerWidth/2?'brightness':'volume';
    }
  }
  if(gestMode==='volume'){
    const delta=-dy/(window.innerHeight*0.6);
    vid.volume=Math.max(0,Math.min(1,gestVol0+delta));
    document.getElementById('vol-slider').classList.add('visible');
  } else if(gestMode==='brightness'){
    const delta=-dy/(window.innerHeight*0.6);
    brightness=Math.max(0.1,Math.min(1,gestBri0+delta));
    document.getElementById('brightness-overlay').style.opacity=1-brightness;
    document.getElementById('bri-fill').style.height=(brightness*100)+'%';
    document.getElementById('bri-slider').classList.add('visible');
  } else if(gestMode==='seek'&&isLandscape()){
    const secs=dx/window.innerWidth*60;
    if(vid.duration){
      const newT=Math.max(0,Math.min(vid.duration,(gestX-gestX)+vid.currentTime));
      document.getElementById('p-cur').textContent=fmt(Math.max(0,Math.min(vid.duration,vid.currentTime+secs)));
    }
  }
},{passive:true});

document.getElementById('vid-wrap').addEventListener('touchend',e=>{
  if(isDraggingSeek||!gestX)return;
  const t=e.changedTouches[0];
  const dx=t.clientX-gestX,dy=t.clientY-gestY;
  if(gestMode==='seek'&&isLandscape()){
    const secs=dx/window.innerWidth*60;seekRel(secs);
  }
  setTimeout(()=>{
    document.getElementById('vol-slider').classList.remove('visible');
    document.getElementById('bri-slider').classList.remove('visible');
  },600);
  gestX=gestY=null;gestMode=null;
},{passive:true});

function isLandscape(){return window.innerWidth>window.innerHeight;}

// ══════════════════════════════════════════════════════════
//  SPEED
// ══════════════════════════════════════════════════════════
function toggleSpeedMenu(){
  document.getElementById('speed-menu').classList.toggle('show');
  document.getElementById('sleep-menu').classList.remove('show');
  showControls();
}
document.querySelectorAll('.speed-opt').forEach(el=>{
  el.addEventListener('click',()=>{
    currentSpeed=parseFloat(el.dataset.spd);
    vid.playbackRate=currentSpeed;
    document.querySelectorAll('.speed-opt').forEach(e=>e.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('speed-btn').textContent=`⚡ ${currentSpeed===1?'1×':currentSpeed+'×'}`;
    document.getElementById('speed-menu').classList.remove('show');
    ktip(`⚡ ${currentSpeed}×`);showControls();
  });
});

// ══════════════════════════════════════════════════════════
//  A-B LOOP
// ══════════════════════════════════════════════════════════
function cycleAB(){
  if(abState===0){abA=vid.currentTime;abState=1;updateABUI();ktip(`🔁 A set at ${fmt(abA)}`);}
  else if(abState===1){
    if(vid.currentTime<=abA){toast('B must be after A');return;}
    abB=vid.currentTime;abState=2;updateABUI();ktip(`🔁 Loop ${fmt(abA)}–${fmt(abB)}`);
  } else {abA=null;abB=null;abState=0;updateABUI();ktip('🔁 Loop off');}
  showControls();
}
function updateABUI(){
  const btn=document.getElementById('ab-btn');
  const ind=document.getElementById('ab-indicator');
  const sub=document.getElementById('ab-sub');
  if(abState===0){btn.classList.remove('active');ind.classList.remove('show');}
  else{btn.classList.add('active');ind.classList.add('show');
    sub.textContent=abState===1?`A=${fmt(abA)} — tap again to set B`:`Loop: ${fmt(abA)} → ${fmt(abB)}`;}
}

// ══════════════════════════════════════════════════════════
//  SLEEP TIMER
// ══════════════════════════════════════════════════════════
function toggleSleepMenu(){
  document.getElementById('sleep-menu').classList.toggle('show');
  document.getElementById('speed-menu').classList.remove('show');
  showControls();
}
document.querySelectorAll('.sleep-opt').forEach(el=>{
  el.addEventListener('click',()=>{
    const min=parseInt(el.dataset.min);
    clearTimeout(sleepTimer);sleepMinutes=min;
    document.querySelectorAll('.sleep-opt').forEach(e=>e.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('sleep-menu').classList.remove('show');
    if(min===0){document.getElementById('sleep-btn').textContent='💤 Sleep';toast('⏰ Sleep timer off');}
    else{
      document.getElementById('sleep-btn').textContent=`💤 ${min}m`;
      toast(`⏰ Sleep in ${min} min`);
      sleepTimer=setTimeout(()=>{vid.pause();toast('😴 Sleep timer triggered');},min*60000);
    }
    showControls();
  });
});

// ══════════════════════════════════════════════════════════
//  PICTURE IN PICTURE
// ══════════════════════════════════════════════════════════
async function togglePiP(){
  if(!document.pictureInPictureEnabled){toast('PiP not supported');return;}
  if(document.pictureInPictureElement){
    await document.exitPictureInPicture().catch(()=>{});
    document.getElementById('pip-btn').style.color='';
  } else {
    await vid.requestPictureInPicture().catch(()=>toast('PiP unavailable'));
    document.getElementById('pip-btn').style.color='#a78bfa';
  }
}
vid.addEventListener('leavepictureinpicture',()=>{document.getElementById('pip-btn').style.color='';});

// ══════════════════════════════════════════════════════════
//  CAST (placeholder)
// ══════════════════════════════════════════════════════════
let casting=false;
function toggleCast(){
  casting=!casting;
  document.getElementById('cast-btn').style.color=casting?'#22d3ee':'';
  document.getElementById('cast-indicator').classList.toggle('show',casting);
  toast(casting?'📡 Casting (demo)':'📡 Cast stopped');
}

// ══════════════════════════════════════════════════════════
//  SUBTITLES
// ══════════════════════════════════════════════════════════
let subsEnabled=false;
function toggleSubs(){
  subsEnabled=!subsEnabled;
  document.getElementById('sub-btn').style.color=subsEnabled?'#a78bfa':'';
  if(vid.textTracks.length){vid.textTracks[0].mode=subsEnabled?'showing':'hidden';}
  toast(subsEnabled?'CC On':'CC Off');showControls();
}

// ══════════════════════════════════════════════════════════
//  SHARE TIMESTAMP
// ══════════════════════════════════════════════════════════
function shareTimestamp(){
  const t=Math.floor(vid.currentTime);
  const url=`${location.href.split('?')[0]}?lib=${encodeURIComponent(curLib)}&file=${encodeURIComponent(curFile)}&t=${t}`;
  if(navigator.share){navigator.share({title:curFile,url}).catch(()=>{});}
  else{navigator.clipboard?.writeText(url).then(()=>toast('🔗 Link copied!')).catch(()=>toast(url));}
  showControls();
}

// ══════════════════════════════════════════════════════════
//  NEXT VIDEO BANNER
// ══════════════════════════════════════════════════════════
function showNextBanner(){
  if(!queue.length)return;
  const ni=queue.findIndex(v=>v.lib===curLib&&v.file===curFile);
  const next=ni>=0&&ni<queue.length-1?queue[ni+1]:queue[0];
  if(!next)return;
  document.getElementById('nb-title').textContent=next.file.replace(/[_.]/g,' ').replace(/\.[^.]+$/,'');
  document.getElementById('next-banner').classList.add('show');
}
function hideNextBanner(){document.getElementById('next-banner').classList.remove('show');}

// ══════════════════════════════════════════════════════════
//  MEDIA SESSION API
// ══════════════════════════════════════════════════════════
function setupMediaSession(){
  if(!('mediaSession' in navigator))return;
  navigator.mediaSession.setActionHandler('play',()=>vid.play());
  navigator.mediaSession.setActionHandler('pause',()=>vid.pause());
  navigator.mediaSession.setActionHandler('seekbackward',()=>seekRel(-10));
  navigator.mediaSession.setActionHandler('seekforward',()=>seekRel(10));
  navigator.mediaSession.setActionHandler('previoustrack',()=>{if(qIdx>0){qIdx--;play(queue[qIdx].lib,queue[qIdx].file);}});
  navigator.mediaSession.setActionHandler('nexttrack',playNext);
}
function updateMediaSession(state,title){
  if(!('mediaSession' in navigator))return;
  navigator.mediaSession.playbackState=state;
  if(title){navigator.mediaSession.metadata=new MediaMetadata({title:title.replace(/[_.]/g,' ').replace(/\.[^.]+$/,''),artist:'CineStream'});}
}

// ══════════════════════════════════════════════════════════
//  KEYBOARD
// ══════════════════════════════════════════════════════════
function ktip(msg){
  const t=document.getElementById('ktoast');
  t.textContent=msg;t.classList.add('show');
  clearTimeout(t._t);t._t=setTimeout(()=>t.classList.remove('show'),1400);
}
document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA')return;
  const playing=document.getElementById('overlay').classList.contains('show');
  if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();cmdOverlay.classList.contains('open')?closeCmd():openCmd();return;}
  if(e.key==='?'){document.getElementById('shortcuts-modal').classList.add('open');return;}
  if(playing){
    if(e.key===' '||e.key==='k'){e.preventDefault();togglePlay();ktip(vid.paused?'⏸':' ▶');return;}
    if(e.key==='f'){toggleFullscreen();return;}
    if(e.key==='m'){toggleMute();ktip(vid.muted?'🔇':'🔊');return;}
    if(e.key==='ArrowRight'){e.preventDefault();seekRel(10);ktip('⏩ +10s');return;}
    if(e.key==='ArrowLeft'){e.preventDefault();seekRel(-10);ktip('⏪ -10s');return;}
    if(e.key==='ArrowUp'){e.preventDefault();vid.volume=Math.min(1,vid.volume+.1);ktip('🔊 '+Math.round(vid.volume*100)+'%');return;}
    if(e.key==='ArrowDown'){e.preventDefault();vid.volume=Math.max(0,vid.volume-.1);ktip('🔉 '+Math.round(vid.volume*100)+'%');return;}
    if(e.key==='n'){playNext();return;}
    if(e.key==='['){ cycleAB();return;}
    if(e.key===']'){ cycleAB();return;}
    if(e.key==='Escape'){stopPlayer();return;}
  }
  if(e.key==='q'){toggleQueue();return;}
  if(e.key==='/'){e.preventDefault();searchEl.focus();}
});

// Prevent context menu on video
document.addEventListener('contextmenu',e=>{
  if(e.target.tagName==='VIDEO')e.preventDefault();
});
document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&'sSuU'.includes(e.key))e.preventDefault();
});

// Check URL params (shared timestamp)
(()=>{
  const p=new URLSearchParams(location.search);
  const lib=p.get('lib'),file=p.get('file'),t=parseInt(p.get('t')||0);
  if(lib&&file)setTimeout(()=>play(lib,file,t),200);
})();

// Toast
let toastT=null;
function toast(msg,d=2600){
  const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');
  clearTimeout(toastT);toastT=setTimeout(()=>t.classList.remove('show'),d);
}

renderQueue();
</script>
</body></html>"""


# ══════════════════════════════════════════════════════════════
#   FLASK ROUTES
# ══════════════════════════════════════════════════════════════
@flask_app.route('/')
@require_approved
def index():
    data = {}
    for k, v in LIBRARIES.items():
        try:
            data[k] = sorted([f for f in os.listdir(v)
                               if f.lower().endswith(ALLOWED_EXT)])
        except Exception:
            data[k] = []

    def palette(name):
        palettes = [
            ("#7c3aed","#4f46e5"), ("#db2777","#7c3aed"), ("#0891b2","#0e7490"),
            ("#059669","#0891b2"), ("#d97706","#dc2626"), ("#be185d","#9333ea"),
            ("#1d4ed8","#0891b2"), ("#7c3aed","#db2777"),
        ]
        h = int(hashlib.md5(name.encode()).hexdigest(), 16)
        return palettes[h % len(palettes)]

    return render_template_string(MAIN_HTML, data=data, palette=palette)

@flask_app.route('/blocked')
def blocked_route():
    return render_template_string(BLOCKED_HTML), 403

@flask_app.route('/api/register', methods=['POST'])
def api_register():
    token = get_token()
    if not token: return jsonify({"error": "no cookie"}), 400
    body  = request.get_json(silent=True) or {}
    name  = (body.get('name') or 'Unknown Device')[:40].strip()
    ip    = request.remote_addr
    PENDING_DEVICES[token] = {
        "token": token, "name": name, "ip": ip,
        "time": datetime.now().strftime("%H:%M:%S")
    }
    if bridge.on_approval_needed:
        bridge.on_approval_needed.emit(token, name, ip)
    return jsonify({"ok": True})

@flask_app.route('/api/check_status')
def api_check_status():
    token = get_token()
    if token in APPROVED_DEVICES: return jsonify({"status": "approved"})
    if token in BLOCKED_DEVICES:  return jsonify({"status": "blocked"})
    return jsonify({"status": "pending"})

@flask_app.route('/api/me')
@require_approved
def api_me():
    token = get_token()
    d = APPROVED_DEVICES.get(token, {})
    return jsonify({"name": d.get("name","Guest")})

@flask_app.route('/api/progress', methods=['POST'])
@require_approved
def api_progress():
    token = get_token()
    body  = request.get_json(silent=True) or {}
    lib, file, pos = body.get('lib'), body.get('file'), body.get('pos', 0)
    if lib and file:
        WATCH_HISTORY.setdefault(token, {})[f"{lib}|||{file}"] = pos
        ACTIVE_VIEWERS[token] = {"file": file, "lib": lib, "since": time.time()}
        _log(token, f"Watching: {file}")
    return jsonify({"ok": True})

@flask_app.route('/api/files')
@require_approved
def api_files():
    out = {}
    for k, v in LIBRARIES.items():
        try:
            out[k] = sorted([f for f in os.listdir(v)
                             if f.lower().endswith(ALLOWED_EXT)])
        except: out[k] = []
    return jsonify(out)

@flask_app.route('/api/search')
@require_approved
def api_search():
    q = (request.args.get('q') or '').lower().strip()
    results = []
    for lib, path in LIBRARIES.items():
        try:
            files = [f for f in os.listdir(path) if f.lower().endswith(ALLOWED_EXT)]
            for f in sorted(files):
                if q in f.lower():
                    results.append({"lib": lib, "file": f})
        except: pass
    return jsonify(results)

@flask_app.route('/api/health')
def api_health():
    return jsonify({
        "ok": True,
        "uptime": round(time.time() - SERVER_START_TIME) if SERVER_START_TIME else 0,
        "libraries": len(LIBRARIES),
        "approved": len(APPROVED_DEVICES),
        "active": len(ACTIVE_VIEWERS),
    })

@flask_app.route('/api/viewers')
@require_approved
def api_viewers():
    now = time.time()
    active = {k:v for k,v in ACTIVE_VIEWERS.items() if now-v['since']<15}
    ACTIVE_VIEWERS.clear(); ACTIVE_VIEWERS.update(active)
    return jsonify({"count": len(active),
                    "viewers": [{"name": APPROVED_DEVICES.get(t,{}).get("name","?"),
                                 "file": v["file"]} for t,v in active.items()]})

@flask_app.route('/stream/<lib>/<path:filename>')
@require_approved
def stream(lib, filename):
    folder = LIBRARIES.get(lib, "")
    path   = os.path.join(folder, filename)
    if not os.path.isfile(path): abort(404)

    size = os.path.getsize(path)
    mime = mimetypes.guess_type(path)[0] or 'video/mp4'
    rng  = request.headers.get('Range')

    if not rng:
        resp = make_response(send_from_directory(folder, filename))
    else:
        start, end = 0, size - 1
        m = re.search(r'bytes=(\d+)-(\d*)', rng)
        if m:
            start = int(m.group(1))
            if m.group(2): end = int(m.group(2))
        chunk = min(end - start + 1, 8 * 1024 * 1024)
        end = start + chunk - 1
        with open(path,'rb') as f:
            f.seek(start); data = f.read(chunk)
        resp = make_response(Response(data, 206, mimetype=mime, direct_passthrough=True))
        resp.headers['Content-Range']  = f'bytes {start}-{end}/{size}'
        resp.headers['Accept-Ranges']  = 'bytes'
        resp.headers['Content-Length'] = chunk

    resp.headers['Content-Disposition'] = 'inline'
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Cache-Control'] = 'no-store, no-cache'
    return resp


# ═══════════════════════════════════════════════════════════════
#   PYQT6 DESKTOP APP (unchanged from v4, quality maintained)
# ═══════════════════════════════════════════════════════════════
DARK_QSS = """
QMainWindow,QWidget#root{background:#050508;}
QWidget{color:#e0e0f0;font-family:'Segoe UI','SF Pro Display',Helvetica,sans-serif;}
QLabel{background:transparent;}
QScrollArea{border:none;background:transparent;}
QScrollBar:vertical{background:#0a0a10;width:4px;border-radius:2px;}
QScrollBar::handle:vertical{background:#1a1a28;border-radius:2px;min-height:20px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}
QTabWidget::pane{border:none;background:transparent;}
QTabBar::tab{background:transparent;color:#2a2a40;padding:13px 24px;
  font-size:12px;font-weight:500;border-bottom:2px solid transparent;letter-spacing:.3px;}
QTabBar::tab:selected{color:#a78bfa;border-bottom:2px solid #7c3aed;}
QTabBar::tab:hover{color:#c0c0e0;}
QMenu{background:#0a0a10;border:1px solid rgba(255,255,255,.06);border-radius:10px;padding:6px;}
QMenu::item{padding:8px 18px;border-radius:6px;font-size:12px;}
QMenu::item:selected{background:rgba(124,58,237,.15);color:#a78bfa;}
QLineEdit{background:#0c0c16;border:1px solid #1a1a28;border-radius:8px;
  padding:8px 12px;color:#d0d0e8;font-size:12px;}
QLineEdit:focus{border-color:rgba(124,58,237,.4);}
QTextEdit{background:#06060c;border:1px solid #121220;border-radius:10px;
  padding:8px;color:#888899;font-size:11px;font-family:'Consolas','Monaco',monospace;}
QProgressBar{background:#0c0c16;border:none;border-radius:4px;height:5px;}
QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7c3aed,stop:1 #4f46e5);border-radius:4px;}
"""

BTN = {
    'primary': """
        QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #7c3aed,stop:1 #4f46e5);
          color:#fff;border:none;border-radius:10px;padding:11px 22px;font-size:13px;font-weight:600;}
        QPushButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #8b5cf6,stop:1 #6366f1);}
        QPushButton:disabled{background:#14142a;color:#2a2a40;}""",
    'ghost': """
        QPushButton{background:rgba(124,58,237,.06);color:#9070c8;
          border:1px solid rgba(124,58,237,.18);border-radius:10px;
          padding:10px 20px;font-size:13px;font-weight:500;}
        QPushButton:hover{background:rgba(124,58,237,.15);color:#a78bfa;}""",
    'danger': """
        QPushButton{background:rgba(244,63,94,.06);color:#f87171;
          border:1px solid rgba(244,63,94,.15);border-radius:9px;padding:7px 14px;font-size:12px;}
        QPushButton:hover{background:rgba(244,63,94,.18);}""",
    'success': """
        QPushButton{background:rgba(34,197,94,.06);color:#4ade80;
          border:1px solid rgba(34,197,94,.18);border-radius:9px;padding:7px 14px;font-size:12px;}
        QPushButton:hover{background:rgba(34,197,94,.18);}""",
}

def GBtn(text, variant='primary', parent=None):
    b = QPushButton(text, parent); b.setStyleSheet(BTN[variant]); return b


class PulseDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setFixedSize(12,12)
        self._on=False; self._ph=0.0
        self._t=QTimer(self); self._t.timeout.connect(self._tick)
    def set_on(self,v):
        self._on=v; (self._t.start(50) if v else self._t.stop()); self.update()
    def _tick(self): self._ph=(self._ph+.1)%(2*math.pi); self.update()
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._on:
            a=int(30+50*abs(math.sin(self._ph)))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(34,197,94,a)))
            p.drawEllipse(0,0,12,12)
            p.setBrush(QBrush(QColor("#22c55e"))); p.drawEllipse(3,3,6,6)
        else:
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor("#f87171")))
            p.drawEllipse(3,3,6,6)
        p.end()


class LiveClock(QLabel):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFont(QFont("Consolas",9))
        self.setStyleSheet("color:#2a2a40;")
        t=QTimer(self); t.timeout.connect(self._tick); t.start(1000); self._tick()
    def _tick(self): self.setText(datetime.now().strftime("  %H:%M:%S  "))


class SignalBridge(QThread):
    approval_request = pyqtSignal(str, str, str)
    session_event    = pyqtSignal(dict)


class ApprovalCard(QFrame):
    sig_approve = pyqtSignal(str)
    sig_block   = pyqtSignal(str)
    def __init__(self, token, name, ip, parent=None):
        super().__init__(parent); self.token=token
        self.setObjectName("ac")
        self.setStyleSheet("#ac{background:#0a0a12;border:1px solid rgba(245,158,11,.18);border-radius:14px;}")
        self.setFixedHeight(80)
        lay=QHBoxLayout(self); lay.setContentsMargins(16,0,16,0); lay.setSpacing(12)
        av=QLabel("👤"); av.setFont(QFont("Segoe UI Emoji",18)); av.setFixedSize(44,44)
        av.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.setStyleSheet("background:rgba(245,158,11,.07);border-radius:22px;border:1px solid rgba(245,158,11,.12);")
        lay.addWidget(av)
        col=QVBoxLayout(); col.setSpacing(3)
        nl=QLabel(name); nl.setFont(QFont("Segoe UI",10,QFont.Weight.DemiBold))
        il=QLabel(f"  {ip}"); il.setFont(QFont("Segoe UI",8)); il.setStyleSheet("color:#333348;")
        col.addWidget(nl); col.addWidget(il); lay.addLayout(col); lay.addStretch()
        ab=GBtn("✓ Allow",'success'); ab.clicked.connect(lambda:self.sig_approve.emit(token))
        bb=GBtn("✕ Block",'danger');  bb.clicked.connect(lambda:self.sig_block.emit(token))
        lay.addWidget(ab); lay.addWidget(bb)


class DeviceRow(QFrame):
    sig_kick = pyqtSignal(str)
    def __init__(self, token, name, ip, parent=None):
        super().__init__(parent); self.token=token
        self.setObjectName("dr")
        self.setStyleSheet("#dr{background:#0a0a12;border:1px solid rgba(255,255,255,.04);border-radius:12px;}")
        self.setFixedHeight(64)
        lay=QHBoxLayout(self); lay.setContentsMargins(16,0,16,0); lay.setSpacing(10)
        dot=QLabel("●"); dot.setStyleSheet("color:#22c55e;font-size:8px;"); lay.addWidget(dot)
        col=QVBoxLayout(); col.setSpacing(1)
        nl=QLabel(name); nl.setFont(QFont("Segoe UI",10,QFont.Weight.Medium))
        il=QLabel(ip); il.setFont(QFont("Segoe UI",8)); il.setStyleSheet("color:#2a2a40;")
        col.addWidget(nl); col.addWidget(il); lay.addLayout(col); lay.addStretch()
        kb=GBtn("Revoke",'danger'); kb.setFixedHeight(30)
        kb.clicked.connect(lambda:self.sig_kick.emit(token)); lay.addWidget(kb)


class CineApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CineStream v5")
        self.setMinimumSize(620, 760); self.resize(660, 800)
        self.setStyleSheet(DARK_QSS)
        self._running=False
        self._pending_w={}; self._approved_w={}
        self._bridge=SignalBridge()
        self._bridge.approval_request.connect(self._on_new_device)
        self._bridge.session_event.connect(self._on_session_event)
        bridge.on_approval_needed = self._bridge.approval_request
        bridge.on_session_event   = self._bridge.session_event
        self._build_ui()
        self._setup_tray()
        self._stats_timer=QTimer(self)
        self._stats_timer.timeout.connect(self._update_stats)
        self._stats_timer.start(3000)

    def _build_ui(self):
        root=QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        vb=QVBoxLayout(root); vb.setContentsMargins(0,0,0,0); vb.setSpacing(0)
        tb_w=QWidget(); tb_w.setFixedHeight(64)
        tb_w.setStyleSheet("background:#07070f;border-bottom:1px solid rgba(255,255,255,.04);")
        tb=QHBoxLayout(tb_w); tb.setContentsMargins(22,0,22,0); tb.setSpacing(0)
        logo=QLabel("▶ CineStream"); logo.setFont(QFont("Segoe UI",14,QFont.Weight.Bold))
        logo.setStyleSheet("color:#a78bfa;letter-spacing:1px;")
        tb.addWidget(logo); tb.addStretch(); tb.addWidget(LiveClock())
        vl=QLabel("v5.0"); vl.setFont(QFont("Segoe UI",8))
        vl.setStyleSheet("color:#1a1a30;background:#0a0a14;border:1px solid #121220;border-radius:6px;padding:3px 9px;margin-left:8px;")
        tb.addWidget(vl); vb.addWidget(tb_w)
        self._badge=QLabel("0"); self._badge.setFixedSize(22,22)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet("background:#f59e0b;color:#000;border-radius:11px;font-size:10px;font-weight:700;")
        self._badge.hide(); tb.addWidget(self._badge)
        self.tabs=QTabWidget(); self.tabs.setDocumentMode(True); vb.addWidget(self.tabs)
        self.tabs.addTab(self._tab_server(),  "  Server  ")
        self.tabs.addTab(self._tab_devices(), "  Devices  ")
        self.tabs.addTab(self._tab_library(), "  Library  ")
        self.tabs.addTab(self._tab_log(),     "  Activity  ")

    def _tab_server(self):
        w=QWidget(); w.setStyleSheet("background:#050508;")
        lay=QVBoxLayout(w); lay.setContentsMargins(22,22,22,22); lay.setSpacing(14)
        sc=QFrame(); sc.setObjectName("sc")
        sc.setStyleSheet("#sc{background:#07071a;border:1px solid rgba(255,255,255,.05);border-radius:20px;}")
        scl=QVBoxLayout(sc); scl.setContentsMargins(22,20,22,20); scl.setSpacing(10)
        r1=QHBoxLayout()
        self._dot=PulseDot(); r1.addWidget(self._dot,0,Qt.AlignmentFlag.AlignVCenter)
        r1.addSpacing(8)
        self._srv_lbl=QLabel("Server Offline"); self._srv_lbl.setFont(QFont("Segoe UI",11,QFont.Weight.DemiBold))
        self._srv_lbl.setStyleSheet("color:#f87171;"); r1.addWidget(self._srv_lbl); r1.addStretch()
        pb=QLabel("Port 5000"); pb.setStyleSheet("color:#1a1a30;background:#0c0c18;border:1px solid #141424;border-radius:6px;padding:3px 10px;font-size:9px;")
        r1.addWidget(pb); scl.addLayout(r1)
        self._url_lbl=QLabel("—"); self._url_lbl.setFont(QFont("Segoe UI",13,QFont.Weight.Bold))
        self._url_lbl.setStyleSheet("color:#7c3aed;")
        self._url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        scl.addWidget(self._url_lbl)
        self._hint=QLabel("Add a folder and start the server"); self._hint.setFont(QFont("Segoe UI",8))
        self._hint.setWordWrap(True); self._hint.setStyleSheet("color:#1e1e38;"); scl.addWidget(self._hint)
        lay.addWidget(sc)
        sr=QHBoxLayout(); sr.setSpacing(10); self._stats=[]
        for ic,val,lbl in [("📁","0","Folders"),("🎬","0","Videos"),("📱","0","Devices"),("👁","0","Active")]:
            box=QFrame(); box.setObjectName("sb")
            box.setStyleSheet("#sb{background:#07071a;border:1px solid rgba(255,255,255,.04);border-radius:12px;}")
            bl=QVBoxLayout(box); bl.setContentsMargins(10,12,10,12); bl.setSpacing(2)
            for obj,fs,bold,color in [(QLabel(ic),14,False,"#fff"),(QLabel(val),18,True,"#a78bfa"),(QLabel(lbl),8,False,"#2a2a44")]:
                obj.setFont(QFont("Segoe UI Emoji" if fs==14 else "Segoe UI",fs,QFont.Weight.Bold if bold else QFont.Weight.Normal))
                obj.setAlignment(Qt.AlignmentFlag.AlignCenter); obj.setStyleSheet(f"color:{color};"); bl.addWidget(obj)
            sr.addWidget(box); self._stats.append(bl.itemAt(1).widget())
        lay.addLayout(sr); lay.addStretch()
        br=QHBoxLayout(); br.setSpacing(10)
        self._add_btn=GBtn("📁  Add Folder",'ghost'); self._add_btn.clicked.connect(self._add_folder)
        self._start_btn=GBtn("▶  Start Server",'primary'); self._start_btn.setMinimumWidth(160)
        self._start_btn.clicked.connect(self._toggle_server)
        br.addWidget(self._add_btn); br.addWidget(self._start_btn); lay.addLayout(br)
        return w

    def _tab_devices(self):
        w=QWidget(); w.setStyleSheet("background:#050508;")
        lay=QVBoxLayout(w); lay.setContentsMargins(22,22,22,22); lay.setSpacing(14)
        def sl(t,c): l=QLabel(t); l.setFont(QFont("Segoe UI",8,QFont.Weight.DemiBold)); l.setStyleSheet(f"color:{c};letter-spacing:2px;"); return l
        lay.addWidget(sl("PENDING APPROVAL","#f59e0b"))
        self._pend_content=QWidget(); self._pend_layout=QVBoxLayout(self._pend_content)
        self._pend_layout.setSpacing(8); self._pend_layout.setContentsMargins(0,0,0,0)
        self._pend_layout.addStretch()
        ps=QScrollArea(); ps.setWidgetResizable(True); ps.setMaximumHeight(200); ps.setWidget(self._pend_content); lay.addWidget(ps)
        self._no_pend=QLabel("No devices waiting"); self._no_pend.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_pend.setFont(QFont("Segoe UI",9))
        self._no_pend.setStyleSheet("color:#1a1a2e;background:#07071a;border:1.5px dashed #121228;border-radius:12px;padding:18px;"); lay.addWidget(self._no_pend)
        lay.addWidget(sl("APPROVED DEVICES","#22c55e"))
        self._appr_content=QWidget(); self._appr_layout=QVBoxLayout(self._appr_content)
        self._appr_layout.setSpacing(8); self._appr_layout.setContentsMargins(0,0,0,0)
        self._appr_layout.addStretch()
        as_=QScrollArea(); as_.setWidgetResizable(True); as_.setWidget(self._appr_content); lay.addWidget(as_)
        self._no_appr=QLabel("No approved devices yet"); self._no_appr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_appr.setFont(QFont("Segoe UI",9))
        self._no_appr.setStyleSheet("color:#1a1a2e;background:#07071a;border:1.5px dashed #121228;border-radius:12px;padding:18px;"); lay.addWidget(self._no_appr)
        return w

    def _tab_library(self):
        w=QWidget(); w.setStyleSheet("background:#050508;")
        lay=QVBoxLayout(w); lay.setContentsMargins(22,22,22,22); lay.setSpacing(12)
        hdr=QHBoxLayout(); hl=QLabel("VIDEO FOLDERS"); hl.setFont(QFont("Segoe UI",8,QFont.Weight.DemiBold))
        hl.setStyleSheet("color:#2a2a44;letter-spacing:2px;"); hdr.addWidget(hl); hdr.addStretch()
        ab=GBtn("+ Add Folder",'ghost'); ab.setFixedHeight(34); ab.clicked.connect(self._add_folder)
        hdr.addWidget(ab); lay.addLayout(hdr)
        self._lib_content=QWidget(); self._lib_layout=QVBoxLayout(self._lib_content)
        self._lib_layout.setSpacing(8); self._lib_layout.setContentsMargins(0,0,0,0)
        self._lib_layout.addStretch()
        ls=QScrollArea(); ls.setWidgetResizable(True); ls.setWidget(self._lib_content); lay.addWidget(ls)
        self._no_lib=QLabel("No folders added.\nClick '+ Add Folder' to get started.")
        self._no_lib.setAlignment(Qt.AlignmentFlag.AlignCenter); self._no_lib.setFont(QFont("Segoe UI",9))
        self._no_lib.setStyleSheet("color:#1a1a2e;background:#07071a;border:2px dashed #121228;border-radius:14px;padding:40px 20px;"); lay.addWidget(self._no_lib)
        return w

    def _tab_log(self):
        w=QWidget(); w.setStyleSheet("background:#050508;")
        lay=QVBoxLayout(w); lay.setContentsMargins(22,22,22,22); lay.setSpacing(12)
        hdr=QHBoxLayout(); hl=QLabel("SESSION ACTIVITY"); hl.setFont(QFont("Segoe UI",8,QFont.Weight.DemiBold))
        hl.setStyleSheet("color:#2a2a44;letter-spacing:2px;"); hdr.addWidget(hl); hdr.addStretch()
        clr=GBtn("Clear",'ghost'); clr.setFixedHeight(30)
        clr.clicked.connect(lambda:(SESSION_LOG.clear(),self._log_box.clear())); hdr.addWidget(clr); lay.addLayout(hdr)
        self._log_box=QTextEdit(); self._log_box.setReadOnly(True)
        self._log_box.setPlaceholderText("Activity will appear here once the server starts…"); lay.addWidget(self._log_box)
        self._viewers_lbl=QLabel("👁 0 active viewers"); self._viewers_lbl.setFont(QFont("Segoe UI",9))
        self._viewers_lbl.setStyleSheet("color:#2a2a44;"); lay.addWidget(self._viewers_lbl)
        return w

    def _setup_tray(self):
        self.tray=QSystemTrayIcon(self)
        px=QPixmap(32,32); px.fill(Qt.GlobalColor.transparent)
        p=QPainter(px); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g=QLinearGradient(0,0,32,32); g.setColorAt(0,QColor("#7c3aed")); g.setColorAt(1,QColor("#4f46e5"))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawRoundedRect(0,0,32,32,8,8)
        p.setPen(QPen(QColor("white"))); p.setFont(QFont("Segoe UI Emoji",14))
        p.drawText(px.rect(),Qt.AlignmentFlag.AlignCenter,"▶"); p.end()
        self.tray.setIcon(QIcon(px))
        menu=QMenu(); menu.addAction("Show",self.show); menu.addSeparator()
        menu.addAction("Quit",QApplication.instance().quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r:self.show() if r==QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def _add_folder(self):
        path=QFileDialog.getExistingDirectory(self,"Select Video Folder")
        if not path: return
        name=os.path.basename(path.rstrip("/\\")) or "Root"
        i=2; base=name
        while name in LIBRARIES: name=f"{base}_{i}"; i+=1
        LIBRARIES[name]=path; self._add_lib_card(name,path); self._update_stats()

    def _add_lib_card(self,name,path):
        try: count=len([f for f in os.listdir(path) if f.lower().endswith(ALLOWED_EXT)])
        except: count=0
        card=QFrame(); card.setObjectName("lc")
        card.setStyleSheet("#lc{background:#07071a;border:1px solid rgba(255,255,255,.04);border-radius:12px;}")
        card.setFixedHeight(72)
        cl=QHBoxLayout(card); cl.setContentsMargins(16,0,16,0); cl.setSpacing(12)
        ic=QLabel("📁"); ic.setFont(QFont("Segoe UI Emoji",18)); ic.setFixedSize(36,36)
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter); cl.addWidget(ic)
        tc=QVBoxLayout(); tc.setSpacing(2)
        nl=QLabel(name); nl.setFont(QFont("Segoe UI",10,QFont.Weight.DemiBold))
        pl=QLabel(path); pl.setFont(QFont("Segoe UI",8)); pl.setStyleSheet("color:#2a2a44;")
        pl.setText(pl.fontMetrics().elidedText(path,Qt.TextElideMode.ElideMiddle,260))
        tc.addWidget(nl); tc.addWidget(pl); cl.addLayout(tc); cl.addStretch()
        cb=QLabel(f"{count} videos"); cb.setStyleSheet("color:#7c3aed;background:rgba(124,58,237,.08);border-radius:8px;padding:3px 10px;font-size:9px;")
        cl.addWidget(cb); rm=GBtn("✕",'danger'); rm.setFixedSize(30,30)
        rm.clicked.connect(lambda _,n=name,c=card:self._remove_folder(n,c)); cl.addWidget(rm)
        self._lib_layout.insertWidget(self._lib_layout.count()-1,card); self._no_lib.hide()

    def _remove_folder(self,name,card):
        LIBRARIES.pop(name,None); card.deleteLater()
        if not LIBRARIES: self._no_lib.show(); self._update_stats()

    def _update_stats(self):
        folders=len(LIBRARIES)
        videos=sum(len([f for f in os.listdir(v) if f.lower().endswith(ALLOWED_EXT)])
                   for v in LIBRARIES.values() if os.path.isdir(v))
        devices=len(APPROVED_DEVICES); now=time.time()
        active=len({k for k,v in ACTIVE_VIEWERS.items() if now-v.get('since',0)<15})
        for w,v in zip(self._stats,[str(folders),str(videos),str(devices),str(active)]): w.setText(v)
        if hasattr(self,'_viewers_lbl'): self._viewers_lbl.setText(f"👁 {active} active viewer{'s' if active!=1 else ''}")

    def _toggle_server(self):
        if self._running: return
        if not LIBRARIES: QMessageBox.warning(self,"CineStream","Add at least one folder first."); return
        self._start_server()

    def _start_server(self):
        global SERVER_START_TIME
        self._running=True; SERVER_START_TIME=time.time()
        self._dot.set_on(True)
        self._srv_lbl.setText("Server Online"); self._srv_lbl.setStyleSheet("color:#22c55e;font-size:11px;font-weight:700;")
        self._start_btn.setText("● Running"); self._start_btn.setEnabled(False)
        ip=self._local_ip(); url=f"http://{ip}:5000"
        self._url_lbl.setText(url)
        self._hint.setText("Open on any device on the same network"); self._hint.setStyleSheet("color:#383858;")
        threading.Thread(target=lambda:flask_app.run(host='0.0.0.0',port=5000,threaded=True,use_reloader=False),daemon=True).start()
        self.tray.showMessage("CineStream v5",f"Live at {url}",QSystemTrayIcon.MessageIcon.Information,3000)

    @pyqtSlot(str,str,str)
    def _on_new_device(self,token,name,ip):
        count=len(PENDING_DEVICES)
        self._badge.setText(str(count)); self._badge.show()
        self.tabs.setTabText(1,f"  Devices ⚡  ")
        card=ApprovalCard(token,name,ip)
        card.sig_approve.connect(self._approve); card.sig_block.connect(self._block)
        self._pend_layout.insertWidget(self._pend_layout.count()-1,card)
        self._pending_w[token]=card; self._no_pend.hide()
        self.tray.showMessage("Access Request",f"{name} ({ip}) wants to join",QSystemTrayIcon.MessageIcon.Information,5000)
        self.activateWindow(); self.raise_()

    @pyqtSlot(dict)
    def _on_session_event(self,ev):
        if hasattr(self,'_log_box'):
            self._log_box.append(
                f'<span style="color:#2a2a44">[{ev["time"]}]</span> '
                f'<span style="color:#a78bfa">{ev["name"]}</span> '
                f'<span style="color:#404055">— {ev["action"]}</span>')
            sb=self._log_box.verticalScrollBar(); sb.setValue(sb.maximum())

    def _approve(self,token):
        dev=PENDING_DEVICES.pop(token,{})
        APPROVED_DEVICES[token]={**dev,'approved_at':datetime.now().strftime("%H:%M")}
        if token in self._pending_w: self._pending_w.pop(token).deleteLater()
        if not PENDING_DEVICES: self._no_pend.show(); self._badge.hide(); self.tabs.setTabText(1,"  Devices  ")
        else: self._badge.setText(str(len(PENDING_DEVICES)))
        row=DeviceRow(token,dev.get('name','?'),dev.get('ip',''))
        row.sig_kick.connect(self._kick)
        self._appr_layout.insertWidget(self._appr_layout.count()-1,row)
        self._approved_w[token]=row; self._no_appr.hide(); self._update_stats()

    def _block(self,token):
        PENDING_DEVICES.pop(token,None); BLOCKED_DEVICES.add(token)
        if token in self._pending_w: self._pending_w.pop(token).deleteLater()
        if not PENDING_DEVICES: self._no_pend.show(); self._badge.hide(); self.tabs.setTabText(1,"  Devices  ")
        else: self._badge.setText(str(len(PENDING_DEVICES)))

    def _kick(self,token):
        APPROVED_DEVICES.pop(token,None); BLOCKED_DEVICES.add(token)
        if token in self._approved_w: self._approved_w.pop(token).deleteLater()
        if not APPROVED_DEVICES: self._no_appr.show(); self._update_stats()

    def _local_ip(self):
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        try: s.connect(('8.8.8.8',1)); return s.getsockname()[0]
        except: return '127.0.0.1'
        finally: s.close()

    def closeEvent(self,e):
        if self._running: self.hide(); e.ignore()
        else: e.accept()


# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app=QApplication(sys.argv); app.setStyle('Fusion'); app.setApplicationName("CineStream")
    pal=QPalette()
    for role,color in [
        (QPalette.ColorRole.Window,"#050508"),(QPalette.ColorRole.WindowText,"#e0e0f0"),
        (QPalette.ColorRole.Base,"#07071a"),(QPalette.ColorRole.AlternateBase,"#0c0c1e"),
        (QPalette.ColorRole.Text,"#e0e0f0"),(QPalette.ColorRole.Button,"#07071a"),
        (QPalette.ColorRole.ButtonText,"#e0e0f0"),(QPalette.ColorRole.Highlight,"#7c3aed"),
        (QPalette.ColorRole.HighlightedText,"#ffffff"),
    ]: pal.setColor(role,QColor(color))
    app.setPalette(pal)
    win=CineApp(); win.show()
    sys.exit(app.exec())
