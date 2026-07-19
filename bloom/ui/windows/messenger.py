"""
Bloom LAN Messenger — real WiFi peer-to-peer chat.

Architecture (ponytail: minimal, no external deps beyond what's in requirements.txt):
  • UDP broadcast on port 55001  → peer discovery
  • TCP server on port 55002     → message delivery
  • Flask HTTP on port 55003     → web UI so phone/other browsers on same WiFi can join
  • PyQt5 window                 → desktop UI matching messanger-degine.png

Features:
  • Block user — blocked users' messages are dropped silently
  • First-message prompt — when a NEW user (not friend) messages you,
    the chat shows two options: "Add User" or "Block User".
    Added users appear in the Friends list. Blocked users are ignored.
  • Mobile-optimised web UI — full-page chat, peer list, per-peer conversation

ponytail: single-file; profiles are in-memory only (ceiling: add sqlite if persistence needed).
ponytail: no TLS on TCP (ceiling: wrap with ssl.SSLContext for production).
"""

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from PyQt5.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QPainter, QPainterPath, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ─── Network constants ───────────────────────────────────────────────────────
UDP_PORT   = 55001   # discovery broadcasts
TCP_PORT   = 55002   # message delivery
WEB_PORT   = 55003   # browser clients
BROADCAST  = "<broadcast>"
DISCOVERY_INTERVAL = 4   # seconds between beacon sends

# ─── Helpers ─────────────────────────────────────────────────────────────────

def local_ip() -> str:
    """Best-effort local LAN IP (not 127.0.0.1)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

MY_IP       = local_ip()
MY_USERNAME = socket.gethostname()

# ─── Peer registry (shared state, protected by a lock) ───────────────────────
_peers_lock = threading.Lock()
_peers: dict[str, dict] = {}   # ip → {username, ip, last_seen, status}

# ─── Message store ───────────────────────────────────────────────────────────
_msgs_lock = threading.Lock()
_messages: dict[str, list] = {}   # peer_ip → [{from, text, ts}]

def _add_msg(peer_ip: str, from_name: str, text: str):
    with _msgs_lock:
        _messages.setdefault(peer_ip, []).append({
            "from": from_name, "text": text, "ts": time.time()
        })

def get_messages(peer_ip: str) -> list:
    with _msgs_lock:
        return list(_messages.get(peer_ip, []))

# ─── Friend-request registry ─────────────────────────────────────────────────
_friends_lock = threading.Lock()
_friends: set[str] = set()          # ips we accepted
_pending_in: set[str] = set()       # incoming requests not yet accepted
_pending_out: set[str] = set()      # outgoing requests we sent

# ─── Block registry ───────────────────────────────────────────────────────────
_blocked_lock = threading.Lock()
_blocked: set[str] = set()          # ips we have blocked

def is_blocked(ip: str) -> bool:
    with _blocked_lock:
        return ip in _blocked

def block_user(ip: str):
    with _blocked_lock:
        _blocked.add(ip)
    # Also remove from friends / pending
    with _friends_lock:
        _friends.discard(ip)
        _pending_in.discard(ip)
        _pending_out.discard(ip)

def unblock_user(ip: str):
    with _blocked_lock:
        _blocked.discard(ip)

# ─── First-message notification ──────────────────────────────────────────────
# Tracks IPs that have sent us a first message but we haven't responded to yet
_first_msg_lock = threading.Lock()
_first_msg_pending: set[str] = set()   # ip → awaiting our add/block decision

# ─── UDP Discovery ───────────────────────────────────────────────────────────

class DiscoveryWorker(QThread):
    peers_updated = pyqtSignal()

    def run(self):
        send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        recv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        recv_sock.settimeout(1.0)
        try:
            recv_sock.bind(("", UDP_PORT))
        except OSError:
            pass  # port already in use (another instance); still send beacons

        def send_beacon():
            payload = json.dumps({"type": "bloom_beacon", "username": MY_USERNAME, "ip": MY_IP}).encode()
            try:
                send_sock.sendto(payload, (BROADCAST, UDP_PORT))
            except Exception:
                pass

        while True:
            send_beacon()
            deadline = time.time() + DISCOVERY_INTERVAL
            while time.time() < deadline:
                try:
                    data, addr = recv_sock.recvfrom(1024)
                    peer_ip = addr[0]
                    if peer_ip == MY_IP:
                        continue
                    msg = json.loads(data.decode())
                    if msg.get("type") == "bloom_beacon":
                        with _peers_lock:
                            _peers[peer_ip] = {
                                "username": msg.get("username", peer_ip),
                                "ip": peer_ip,
                                "last_seen": time.time(),
                                "status": "online",
                            }
                        self.peers_updated.emit()
                    elif msg.get("type") == "friend_request":
                        with _friends_lock:
                            _pending_in.add(peer_ip)
                        self.peers_updated.emit()
                    elif msg.get("type") == "friend_accept":
                        with _friends_lock:
                            _friends.add(peer_ip)
                            _pending_out.discard(peer_ip)
                        self.peers_updated.emit()
                except (socket.timeout, json.JSONDecodeError, OSError):
                    pass

            # prune stale peers
            cutoff = time.time() - 15
            with _peers_lock:
                stale = [ip for ip, p in _peers.items() if p["last_seen"] < cutoff]
                for ip in stale:
                    del _peers[ip]
            if stale:
                self.peers_updated.emit()

def _udp_send(peer_ip: str, payload: dict):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.sendto(json.dumps(payload).encode(), (peer_ip, UDP_PORT))
        s.close()
    except Exception:
        pass

# ─── TCP Message Server ───────────────────────────────────────────────────────

class TCPServerWorker(QThread):
    message_received = pyqtSignal(str, str, str)   # peer_ip, from_name, text

    def run(self):
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("0.0.0.0", TCP_PORT))
        except OSError:
            return
        srv.listen(10)
        srv.settimeout(1.0)
        while True:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            threading.Thread(target=self._handle, args=(conn, addr[0]), daemon=True).start()

    def _handle(self, conn, peer_ip):
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            msg = json.loads(data.decode())
            text = msg.get("text", "")
            from_name = msg.get("from", peer_ip)

            # Drop messages from blocked users silently
            if is_blocked(peer_ip):
                return

            _add_msg(peer_ip, from_name, text)

            # Mark as first-message-pending if not yet a friend
            with _friends_lock:
                known = peer_ip in _friends
            if not known:
                with _first_msg_lock:
                    _first_msg_pending.add(peer_ip)

            self.message_received.emit(peer_ip, from_name, text)
        except Exception:
            pass
        finally:
            conn.close()

def tcp_send(peer_ip: str, text: str):
    """Send a message via TCP to peer_ip."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((peer_ip, TCP_PORT))
        payload = json.dumps({"from": MY_USERNAME, "text": text}).encode()
        s.sendall(payload)
        s.close()
        _add_msg(peer_ip, MY_USERNAME, text)
        return True
    except Exception:
        return False

# ─── Flask-lite web server (stdlib only, no Flask needed) ─────────────────────
# ponytail: using stdlib http.server instead of Flask (ceiling: swap for Flask if routes get complex)

_WEB_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>Bloom Messenger — {username}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  :root{{--bg:#0f0f1a;--sidebar:#12122a;--accent:#7c3aed;--accent2:#a855f7;--text:#e2e8f8;--muted:#94a3b8;--bubble-me:linear-gradient(135deg,#7c3aed,#a855f7);--bubble-peer:#1e293b;--green:#4ade80;--red:#ef4444;--amber:#f59e0b}}
  html,body{{height:100%;overflow:hidden;background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif}}

  /* ── Layout ── */
  #app{{display:flex;height:100vh}}
  #sidebar{{width:260px;min-width:260px;background:var(--sidebar);border-right:1px solid #1e1e3a;display:flex;flex-direction:column;overflow:hidden}}
  #main{{flex:1;display:flex;flex-direction:column;overflow:hidden}}

  /* ── Sidebar header ── */
  #sidebar-header{{padding:16px 14px 12px;border-bottom:1px solid #1e1e3a}}
  #sidebar-header h2{{font-size:15px;color:#c084fc;font-weight:700;letter-spacing:.5px}}
  #my-info{{font-size:11px;color:var(--muted);margin-top:3px}}

  /* ── Peer list ── */
  #peer-list{{flex:1;overflow-y:auto;padding:8px 0}}
  .peer-item{{display:flex;align-items:center;gap:10px;padding:10px 14px;cursor:pointer;transition:background .15s;border-radius:0}}
  .peer-item:hover,.peer-item.active{{background:#1e1e3a}}
  .avatar{{width:38px;height:38px;border-radius:50%;background:var(--accent);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;flex-shrink:0}}
  .peer-name{{font-size:13px;font-weight:600;line-height:1.3}}
  .peer-status{{font-size:11px;color:var(--green)}}
  .peer-status.pending{{color:var(--amber)}}
  .peer-status.unknown{{color:var(--muted)}}
  .unread-badge{{margin-left:auto;background:var(--accent);border-radius:10px;padding:2px 7px;font-size:10px;font-weight:700}}

  /* ── Chat area ── */
  #chat-header{{padding:14px 18px;background:#12122a;border-bottom:1px solid #1e1e3a;display:flex;align-items:center;gap:12px}}
  #chat-title{{font-size:15px;font-weight:700;color:#c084fc}}
  #chat-subtitle{{font-size:11px;color:var(--muted)}}

  /* ── First-message banner ── */
  #first-msg-banner{{display:none;background:#1e1b4b;padding:12px 18px;border-bottom:1px solid #312e81;align-items:center;gap:10px;flex-wrap:wrap}}
  #first-msg-banner span{{font-size:13px;color:var(--amber);flex:1}}
  .banner-btn{{padding:7px 16px;border-radius:20px;border:none;font-size:12px;font-weight:700;cursor:pointer;transition:.15s}}
  #add-btn{{background:var(--accent);color:#fff}}
  #add-btn:hover{{background:#6d28d9}}
  #block-btn{{background:transparent;color:var(--red);border:1.5px solid var(--red)}}
  #block-btn:hover{{background:var(--red);color:#fff}}

  /* ── Messages ── */
  #messages{{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:10px}}
  .bubble{{max-width:72%;padding:10px 15px;border-radius:18px;font-size:13px;line-height:1.5;word-break:break-word}}
  .bubble.me{{align-self:flex-end;background:var(--bubble-me);color:#fff;border-bottom-right-radius:4px}}
  .bubble.peer{{align-self:flex-start;background:var(--bubble-peer);color:var(--text);border-bottom-left-radius:4px}}
  .bubble-from{{font-size:10px;color:#a78bfa;margin-bottom:3px;font-weight:700}}
  .bubble-ts{{font-size:9px;color:#475569;margin-top:3px;text-align:right}}

  /* ── Input bar ── */
  #input-bar{{padding:12px 16px;background:#12122a;border-top:1px solid #1e1e3a;display:flex;gap:10px}}
  #msg-input{{flex:1;background:#1e1e3a;border:1px solid #4c1d95;border-radius:24px;padding:10px 18px;color:var(--text);font-size:14px;outline:none}}
  #msg-input:focus{{border-color:var(--accent2)}}
  #send-btn{{background:var(--accent);border:none;border-radius:24px;padding:10px 20px;color:#fff;cursor:pointer;font-size:15px;transition:.15s}}
  #send-btn:hover{{background:#6d28d9}}

  /* ── Status bar ── */
  #status-bar{{padding:5px 18px;font-size:10px;color:#4b5563;background:#0a0a14;border-top:1px solid #1e1e3a}}

  /* ── Empty state ── */
  #empty-state{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#374151}}
  #empty-state .emoji{{font-size:52px;margin-bottom:12px}}
  #empty-state p{{font-size:13px}}

  /* ── Mobile responsive (≤600px) ── */
  @media(max-width:600px){{
    #sidebar{{width:100%;position:absolute;z-index:10;height:100%;transform:translateX(0);transition:.25s}}
    #sidebar.hidden{{transform:translateX(-100%)}}
    #main{{width:100%}}
    #chat-header{{padding:10px 14px}}
    #back-btn{{display:flex!important}}
    .bubble{{max-width:85%}}
  }}
  #back-btn{{display:none;background:none;border:none;color:#c084fc;font-size:18px;cursor:pointer;padding:0 8px 0 0}}
</style>
</head>
<body>
<div id="app">
  <!-- Sidebar -->
  <div id="sidebar">
    <div id="sidebar-header">
      <h2>🌸 Bloom Messenger</h2>
      <div id="my-info">{username} &nbsp;·&nbsp; {ip}</div>
    </div>
    <div id="peer-list">{peer_list_html}</div>
  </div>

  <!-- Main chat -->
  <div id="main">
    <div id="chat-header">
      <button id="back-btn" onclick="showSidebar()" title="Back">◀</button>
      <div>
        <div id="chat-title">Select a peer</div>
        <div id="chat-subtitle">No peer selected</div>
      </div>
    </div>

    <!-- First-message action banner -->
    <div id="first-msg-banner">
      <span id="banner-text">⚠️ This person sent you a message. What would you like to do?</span>
      <button class="banner-btn" id="add-btn" onclick="addUser()">+ Add User</button>
      <button class="banner-btn" id="block-btn" onclick="blockUser()">🚫 Block</button>
    </div>

    <div id="messages"><div id="empty-state"><div class="emoji">🌸</div><p>Select a peer from the left to start chatting</p></div></div>
    <div id="input-bar">
      <input id="msg-input" placeholder="Type a message…" autocomplete="off">
      <button id="send-btn" onclick="sendMsg()">➤</button>
    </div>
    <div id="status-bar" id="status-bar">🌐 {web_url}</div>
  </div>
</div>

<script>
let currentPeer = null;
let pollTimer = null;

function initials(name) {{
  return name.split(' ').slice(0,2).map(w=>w[0]||'').join('').toUpperCase() || '?';
}}

function selectPeer(ip, username) {{
  currentPeer = {{ip, username}};
  document.getElementById('chat-title').textContent = username;
  document.getElementById('chat-subtitle').textContent = ip;
  // On mobile: hide sidebar
  document.getElementById('sidebar').classList.add('hidden');
  loadChat();
}}

function showSidebar() {{
  document.getElementById('sidebar').classList.remove('hidden');
}}

function loadChat() {{
  if (!currentPeer) return;
  fetch('/chat?peer=' + encodeURIComponent(currentPeer.ip))
    .then(r => r.json())
    .then(data => {{
      // Render messages
      const box = document.getElementById('messages');
      box.innerHTML = '';
      data.messages.forEach(m => {{
        const wrap = document.createElement('div');
        const isMe = m.from === '{username}';
        wrap.style.display='flex';
        wrap.style.flexDirection='column';
        wrap.style.alignItems = isMe ? 'flex-end' : 'flex-start';
        const ts = new Date(m.ts * 1000).toLocaleTimeString([], {{hour:'2-digit',minute:'2-digit'}});
        wrap.innerHTML = `
          ${{!isMe ? `<div class="bubble-from">${{m.from}}</div>` : ''}}
          <div class="bubble ${{isMe ? 'me' : 'peer'}}">${{m.text}}</div>
          <div class="bubble-ts">${{ts}}</div>
        `;
        box.appendChild(wrap);
      }});
      box.scrollTop = box.scrollHeight;

      // Show/hide first-message banner
      const banner = document.getElementById('first-msg-banner');
      if (data.first_msg_pending && !data.is_friend && !data.is_blocked) {{
        banner.style.display = 'flex';
        document.getElementById('banner-text').textContent =
          '\u26a0\ufe0f ' + (data.messages[0]?.from || 'Someone') + ' sent you a message. Add them or block?';
      }} else {{
        banner.style.display = 'none';
      }}
    }});
}}

function sendMsg() {{
  const input = document.getElementById('msg-input');
  const text = input.value.trim();
  if (!text || !currentPeer) return;
  input.value = '';
  fetch('/send?to=' + encodeURIComponent(currentPeer.ip) + '&text=' + encodeURIComponent(text) + '&from=' + encodeURIComponent(myUsername))
    .then(() => loadChat());
}}

function addUser() {{
  if (!currentPeer) return;
  fetch('/add?ip=' + encodeURIComponent(currentPeer.ip)).then(() => {{
    document.getElementById('first-msg-banner').style.display = 'none';
    loadChat();
  }});
}}

function blockUser() {{
  if (!currentPeer) return;
  if (!confirm('Block ' + currentPeer.username + '? They will no longer be able to message you.')) return;
  fetch('/block?ip=' + encodeURIComponent(currentPeer.ip)).then(() => {{
    document.getElementById('first-msg-banner').style.display = 'none';
    document.getElementById('messages').innerHTML =
      '<div id="empty-state"><div class="emoji">🚫</div><p>User blocked</p></div>';
    currentPeer = null;
    document.getElementById('chat-title').textContent = 'Select a peer';
    document.getElementById('chat-subtitle').textContent = '';
  }});
}}

document.getElementById('msg-input').addEventListener('keydown', e => {{
  if (e.key === 'Enter' && !e.shiftKey) {{ e.preventDefault(); sendMsg(); }}
}});

// LocalStorage username registration
let myUsername = localStorage.getItem('bloom_username');
if (!myUsername) {{
  myUsername = 'Web-' + Math.floor(1000 + Math.random() * 9000);
  localStorage.setItem('bloom_username', myUsername);
}}
document.getElementById('my-info').textContent = myUsername + ' \u00b7 ' + '{ip}';

function pingServer() {{
  fetch('/ping?username=' + encodeURIComponent(myUsername));
}}
pingServer();
setInterval(pingServer, 4000);

// Auto-refresh chat and page peer list every 3s
setInterval(() => {{
  if (currentPeer) loadChat();
}}, 3000);
</script>
</body>
</html>"""

class _WebHandler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # silence access log

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # ── /ping  ──────────────────────────────────────────────────────────
        if parsed.path == "/ping":
            username = params.get("username", [""])[0]
            if username:
                peer_ip = self.client_address[0]
                with _peers_lock:
                    _peers[peer_ip] = {
                        "username": username,
                        "ip": peer_ip,
                        "last_seen": time.time(),
                        "status": "online",
                    }
            self._json({"ok": True})
            return

        # ── /send  ──────────────────────────────────────────────────────────
        if parsed.path == "/send":
            to_ip = params.get("to", [""])[0]
            text  = params.get("text", [""])[0]
            from_user = params.get("from", [""])[0] or self.client_address[0]
            if to_ip and text:
                if not is_blocked(to_ip):
                    if to_ip != MY_IP and to_ip != "127.0.0.1":
                        # Send via TCP to remote peer
                        try:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(5)
                            s.connect((to_ip, TCP_PORT))
                            payload = json.dumps({"from": from_user, "text": text}).encode()
                            s.sendall(payload)
                            s.close()
                            _add_msg(to_ip, from_user, text)
                        except Exception:
                            _add_msg(to_ip, from_user, f"[send failed] {text}")
                    else:
                        # Direct save since target is this host (the laptop itself)
                        # We store under the sender's IP so it shows in the chat history on both sides
                        _add_msg(self.client_address[0], from_user, text)
            self._json({"ok": True})
            return

        # ── /chat  ──────────────────────────────────────────────────────────
        if parsed.path == "/chat":
            peer_ip = params.get("peer", [""])[0]
            # If checking chat with the laptop itself, look under client IP
            if peer_ip == MY_IP or peer_ip == "127.0.0.1":
                peer_ip = self.client_address[0]
            msgs = get_messages(peer_ip)
            with _friends_lock:
                is_friend = peer_ip in _friends
            with _first_msg_lock:
                first_pending = peer_ip in _first_msg_pending
            self._json({
                "messages": msgs,
                "is_friend": is_friend,
                "is_blocked": is_blocked(peer_ip),
                "first_msg_pending": first_pending,
            })
            return

        # ── /add  ───────────────────────────────────────────────────────────
        if parsed.path == "/add":
            ip = params.get("ip", [""])[0]
            if ip:
                with _friends_lock:
                    _friends.add(ip)
                with _first_msg_lock:
                    _first_msg_pending.discard(ip)
                _udp_send(ip, {"type": "friend_accept", "from": MY_USERNAME, "ip": MY_IP})
            self._json({"ok": True})
            return

        # ── /block  ─────────────────────────────────────────────────────────
        if parsed.path == "/block":
            ip = params.get("ip", [""])[0]
            if ip:
                block_user(ip)
                with _first_msg_lock:
                    _first_msg_pending.discard(ip)
            self._json({"ok": True})
            return

        # ── / (main page)  ──────────────────────────────────────────────────
        with _peers_lock:
            peer_list = list(_peers.values())
        with _friends_lock:
            friends_set = set(_friends)

        peer_list_html = ""
        for p in peer_list:
            ip = p["ip"]
            init = "".join(w[0].upper() for w in p["username"].split()[:2]) or "?"
            if is_blocked(ip):
                continue
            is_fr = ip in friends_set
            badge = ' <span class="unread-badge">' + str(len(get_messages(ip))) + '</span>' if get_messages(ip) else ""
            status_cls = "online" if is_fr else "unknown"
            status_txt = "● Friend" if is_fr else "○ Not added"
            peer_list_html += f"""
            <div class="peer-item" onclick="selectPeer('{ip}', '{p['username']}')">
              <div class="avatar">{init}</div>
              <div>
                <div class="peer-name">{p['username']}</div>
                <div class="peer-status {status_cls}">{status_txt}</div>
              </div>
              {badge}
            </div>"""

        if not peer_list_html:
            peer_list_html = '<div style="padding:20px 14px;color:#4b5563;font-size:12px;">No peers found on network yet…</div>'

        web_url = f"http://{MY_IP}:{WEB_PORT}"
        html = _WEB_HTML_TEMPLATE.format(
            username=MY_USERNAME,
            ip=MY_IP,
            peer_list_html=peer_list_html,
            web_url=web_url,
        )
        self._html(html)

    def _html(self, body: str):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj: dict):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def _start_web_server():
    try:
        srv = HTTPServer(("0.0.0.0", WEB_PORT), _WebHandler)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        return True
    except OSError:
        return False

# ─── Avatar widget ────────────────────────────────────────────────────────────

class AvatarLabel(QLabel):
    """Circular avatar with initials fallback."""
    def __init__(self, name: str, size: int = 40, parent=None):
        super().__init__(parent)
        self._name = name
        self._sz = size
        self.setFixedSize(size, size)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addEllipse(0, 0, self._sz, self._sz)
        p.setClipPath(path)
        color = QColor(124, 58, 237)
        p.fillRect(0, 0, self._sz, self._sz, color)
        initials = "".join(w[0].upper() for w in self._name.split()[:2]) or "?"
        p.setPen(QColor(255, 255, 255))
        font = QFont("Arial", max(8, self._sz // 3), QFont.Bold)
        p.setFont(font)
        p.drawText(0, 0, self._sz, self._sz, Qt.AlignCenter, initials)
        p.end()

# ─── Chat bubble ─────────────────────────────────────────────────────────────

class BubbleWidget(QWidget):
    def __init__(self, from_name: str, text: str, is_me: bool, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 3, 8, 3)
        bubble = QLabel()
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(340)
        bubble.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        if is_me:
            bubble.setText(text)
            bubble.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7c3aed,stop:1 #a855f7);
                    color: #fff;
                    border-radius: 18px;
                    border-bottom-right-radius: 4px;
                    padding: 10px 14px;
                    font-size: 13px;
                }
            """)
            me_lbl = QLabel("me")
            me_lbl.setStyleSheet("color: #ef4444; font-size: 10px; font-weight: bold;")
            me_lbl.setAlignment(Qt.AlignBottom)
            lay.addStretch()
            lay.addWidget(bubble)
            lay.addWidget(me_lbl)
        else:
            name_lbl = QLabel(from_name)
            name_lbl.setStyleSheet("color: #a78bfa; font-size: 10px; font-weight: bold;")
            name_lbl.setAlignment(Qt.AlignBottom)
            bubble.setText(text)
            bubble.setStyleSheet("""
                QLabel {
                    background: #1e293b;
                    color: #e2e8f8;
                    border-radius: 18px;
                    border-bottom-left-radius: 4px;
                    padding: 10px 14px;
                    font-size: 13px;
                }
            """)
            lay.addWidget(name_lbl)
            lay.addWidget(bubble)
            lay.addStretch()

# ─── Left sidebar peer row ────────────────────────────────────────────────────

class PeerRow(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, peer: dict, is_friend: bool, pending_in: bool, blocked: bool = False, parent=None):
        super().__init__(parent)
        self._peer = peer
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        av = AvatarLabel(peer["username"], 36)
        lay.addWidget(av)

        info = QVBoxLayout()
        info.setSpacing(2)
        name = QLabel(peer["username"])
        name.setStyleSheet(
            "color: #6b7280; font-size: 13px; font-weight: bold;"
            if blocked else
            "color: #e2e8f8; font-size: 13px; font-weight: bold;"
        )
        info.addWidget(name)

        if blocked:
            status_txt = "🚫 Blocked"
            status_css = "color: #ef4444; font-size: 10px;"
        elif pending_in:
            status_txt = "⏳ Sent you a message"
            status_css = "color: #f59e0b; font-size: 10px;"
        elif is_friend:
            status_txt = "● Friend"
            status_css = "color: #4ade80; font-size: 10px;"
        else:
            status_txt = "○ Add or Block"
            status_css = "color: #9ca3af; font-size: 10px;"

        status = QLabel(status_txt)
        status.setStyleSheet(status_css)
        info.addWidget(status)
        lay.addLayout(info)
        lay.addStretch()

        self.setStyleSheet("""
            PeerRow { background: transparent; border-radius: 10px; }
            PeerRow:hover { background: #1e293b; }
        """)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, _e):
        self.clicked.emit(self._peer)

# ─── Main window ──────────────────────────────────────────────────────────────

class EncryptedMessengerWindow(QWidget):
    """
    Bloom LAN Messenger.
    Left panel  = friends/groups/settings (design: panel 1 → panel 2 on friend click)
    Center      = conversation list / peer list
    Right       = chat window with first-message Add/Block banner
    """

    def __init__(self, key_passphrase="", parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("🌸 Bloom Messenger")
        self.setMinimumSize(900, 600)
        self._active_peer: dict | None = None

        self._apply_stylesheet()
        self._build_ui()

        # Start network workers
        self._discovery = DiscoveryWorker()
        self._discovery.peers_updated.connect(self._refresh_peers)
        self._discovery.start()

        self._tcp_srv = TCPServerWorker()
        self._tcp_srv.message_received.connect(self._on_message_received)
        self._tcp_srv.start()

        # Start web server and show IP
        web_ok = _start_web_server()
        if web_ok:
            self._status_lbl.setText(f"🌐 Web UI: http://{MY_IP}:{WEB_PORT}  |  📡 LAN: {MY_IP}")
        else:
            self._status_lbl.setText(f"📡 LAN: {MY_IP}  (web port busy)")

        # Refresh peer list every 3s to catch stale pruning
        t = QTimer(self)
        t.timeout.connect(self._refresh_peers)
        t.start(3000)

    # ── Stylesheet ────────────────────────────────────────────────────────────

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0f0f1a;
                color: #e2e8f8;
                font-family: 'Segoe UI', 'Ubuntu', sans-serif;
            }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: #1a1a2e; width: 6px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #4c1d95; border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QLineEdit {
                background: #1e1e3a;
                border: 1px solid #4c1d95;
                border-radius: 20px;
                padding: 8px 16px;
                color: #e2e8f8;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #a855f7; }
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7c3aed,stop:1 #a855f7);
                color: white;
                border: none;
                border-radius: 20px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background: #6d28d9; }
            QPushButton:disabled { background: #374151; color: #6b7280; }
        """)

    # ── UI layout ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── LEFT SIDEBAR (profile + friends + groups + settings) ─────────────
        left = QFrame()
        left.setFixedWidth(220)
        left.setStyleSheet("QFrame { background: #12122a; border-right: 1px solid #1e1e3a; }")
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(12, 18, 12, 12)
        left_lay.setSpacing(8)

        # Profile
        prof_row = QHBoxLayout()
        self._my_avatar = AvatarLabel(MY_USERNAME, 46)
        prof_row.addWidget(self._my_avatar)
        prof_info = QVBoxLayout()
        prof_info.setSpacing(2)
        prof_name = QLabel(MY_USERNAME)
        prof_name.setStyleSheet("color: #e2e8f8; font-weight: bold; font-size: 14px;")
        prof_info.addWidget(prof_name)
        prof_ip = QLabel(MY_IP)
        prof_ip.setStyleSheet("color: #6b7280; font-size: 10px;")
        prof_info.addWidget(prof_ip)
        prof_row.addLayout(prof_info)
        prof_row.addStretch()
        left_lay.addLayout(prof_row)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet("color: #1e293b;")
        left_lay.addWidget(div)

        # Section label: Friends
        friends_hdr = QLabel("Friends")
        friends_hdr.setStyleSheet("color: #a78bfa; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        left_lay.addWidget(friends_hdr)

        self._friends_list = QVBoxLayout()
        self._friends_list.setSpacing(2)
        friends_container = QWidget()
        friends_container.setLayout(self._friends_list)
        friends_scroll = QScrollArea()
        friends_scroll.setWidgetResizable(True)
        friends_scroll.setWidget(friends_container)
        friends_scroll.setMaximumHeight(160)
        friends_scroll.setStyleSheet("background: transparent; border: none;")
        left_lay.addWidget(friends_scroll)

        # Section label: Online
        online_hdr = QLabel("Online")
        online_hdr.setStyleSheet("color: #4ade80; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        left_lay.addWidget(online_hdr)

        self._online_list = QVBoxLayout()
        self._online_list.setSpacing(2)
        online_container = QWidget()
        online_container.setLayout(self._online_list)
        online_scroll = QScrollArea()
        online_scroll.setWidgetResizable(True)
        online_scroll.setWidget(online_container)
        online_scroll.setStyleSheet("background: transparent; border: none;")
        left_lay.addWidget(online_scroll, 1)

        # Section label: Blocked
        self._blocked_hdr = QLabel("Blocked")
        self._blocked_hdr.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        self._blocked_hdr.setVisible(False)
        left_lay.addWidget(self._blocked_hdr)

        self._blocked_list = QVBoxLayout()
        self._blocked_list.setSpacing(2)
        blocked_container = QWidget()
        blocked_container.setLayout(self._blocked_list)
        blocked_scroll = QScrollArea()
        blocked_scroll.setWidgetResizable(True)
        blocked_scroll.setWidget(blocked_container)
        blocked_scroll.setMaximumHeight(100)
        blocked_scroll.setStyleSheet("background: transparent; border: none;")
        self._blocked_scroll = blocked_scroll
        blocked_scroll.setVisible(False)
        left_lay.addWidget(blocked_scroll)

        left_lay.addStretch()

        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6b7280;
                border: 1px solid #1e293b;
                border-radius: 10px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover { color: #e2e8f8; border-color: #4c1d95; }
        """)
        left_lay.addWidget(settings_btn)

        root.addWidget(left)

        # ── CENTER (conversation / peer detail) ──────────────────────────────
        center = QFrame()
        center.setFixedWidth(260)
        center.setStyleSheet("QFrame { background: #0f0f1a; border-right: 1px solid #1e1e3a; }")
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(0)

        center_hdr = QLabel("Messages")
        center_hdr.setAlignment(Qt.AlignCenter)
        center_hdr.setStyleSheet("""
            color: #c084fc; font-size: 15px; font-weight: bold;
            padding: 16px 12px; border-bottom: 1px solid #1e1e3a;
        """)
        center_lay.addWidget(center_hdr)

        self._conv_list = QVBoxLayout()
        self._conv_list.setSpacing(0)
        self._conv_list.setAlignment(Qt.AlignTop)
        conv_container = QWidget()
        conv_container.setLayout(self._conv_list)
        conv_scroll = QScrollArea()
        conv_scroll.setWidgetResizable(True)
        conv_scroll.setWidget(conv_container)
        conv_scroll.setStyleSheet("background: transparent; border: none;")
        center_lay.addWidget(conv_scroll, 1)

        root.addWidget(center)

        # ── RIGHT (chat window) ───────────────────────────────────────────────
        right = QFrame()
        right.setStyleSheet("QFrame { background: #0d0d1f; }")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        # Chat header
        self._chat_header = QLabel("Select a peer to start chatting")
        self._chat_header.setAlignment(Qt.AlignCenter)
        self._chat_header.setStyleSheet("""
            color: #a78bfa; font-size: 14px; font-weight: bold;
            padding: 16px; border-bottom: 1px solid #1e1e3a;
            background: #12122a;
        """)
        right_lay.addWidget(self._chat_header)

        # ── First-message action banner ───────────────────────────────────────
        self._first_msg_bar = QFrame()
        self._first_msg_bar.setStyleSheet("QFrame { background: #1e1b4b; }")
        first_bar_lay = QHBoxLayout(self._first_msg_bar)
        first_bar_lay.setContentsMargins(14, 10, 14, 10)
        first_bar_lay.setSpacing(10)

        self._first_msg_lbl = QLabel("⚠️ This person messaged you. Add them or block?")
        self._first_msg_lbl.setStyleSheet("color: #f59e0b; font-size: 12px; background: transparent;")
        self._first_msg_lbl.setWordWrap(True)
        first_bar_lay.addWidget(self._first_msg_lbl, 1)

        self._add_user_btn = QPushButton("+ Add User")
        self._add_user_btn.setFixedWidth(90)
        self._add_user_btn.setStyleSheet("""
            QPushButton {
                background: #7c3aed; color: #fff;
                border-radius: 14px; padding: 6px 12px;
                font-size: 12px; font-weight: bold; border: none;
            }
            QPushButton:hover { background: #6d28d9; }
        """)
        self._add_user_btn.clicked.connect(self._on_add_user_from_banner)
        first_bar_lay.addWidget(self._add_user_btn)

        self._block_from_banner_btn = QPushButton("🚫 Block")
        self._block_from_banner_btn.setFixedWidth(80)
        self._block_from_banner_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #ef4444;
                border: 1.5px solid #ef4444; border-radius: 14px;
                padding: 6px 10px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: #ef4444; color: #fff; }
        """)
        self._block_from_banner_btn.clicked.connect(self._on_block_user_from_banner)
        first_bar_lay.addWidget(self._block_from_banner_btn)

        self._first_msg_bar.hide()
        right_lay.addWidget(self._first_msg_bar)

        # Stacked: placeholder vs chat
        self._chat_stack = QStackedWidget()

        # Placeholder page
        placeholder = QWidget()
        ph_lay = QVBoxLayout(placeholder)
        ph_lay.setAlignment(Qt.AlignCenter)
        ph_ico = QLabel("🌸")
        ph_ico.setAlignment(Qt.AlignCenter)
        ph_ico.setStyleSheet("font-size: 48px;")
        ph_txt = QLabel("Connect with peers on your WiFi network\nSelect someone from the left to chat")
        ph_txt.setAlignment(Qt.AlignCenter)
        ph_txt.setStyleSheet("color: #4b5563; font-size: 13px;")
        ph_lay.addWidget(ph_ico)
        ph_lay.addWidget(ph_txt)
        self._chat_stack.addWidget(placeholder)

        # Chat page
        chat_page = QWidget()
        chat_page_lay = QVBoxLayout(chat_page)
        chat_page_lay.setContentsMargins(0, 0, 0, 0)
        chat_page_lay.setSpacing(0)

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setStyleSheet("background: transparent; border: none;")
        self._bubble_container = QWidget()
        self._bubble_lay = QVBoxLayout(self._bubble_container)
        self._bubble_lay.setAlignment(Qt.AlignTop)
        self._bubble_lay.setSpacing(4)
        self._bubble_lay.addStretch()
        self._chat_scroll.setWidget(self._bubble_container)
        chat_page_lay.addWidget(self._chat_scroll, 1)

        # Legacy friend-request bar (shown when they sent us a friend request via UDP)
        self._fr_bar = QFrame()
        self._fr_bar.setStyleSheet("QFrame { background: #1e1b4b; padding: 8px; }")
        fr_bar_lay = QHBoxLayout(self._fr_bar)
        fr_bar_lay.setContentsMargins(12, 8, 12, 8)
        self._fr_label = QLabel("⏳ Incoming friend request")
        self._fr_label.setStyleSheet("color: #f59e0b; font-size: 12px;")
        fr_bar_lay.addWidget(self._fr_label)
        fr_bar_lay.addStretch()
        self._accept_btn = QPushButton("✓ Accept")
        self._accept_btn.clicked.connect(self._accept_friend_request)
        fr_bar_lay.addWidget(self._accept_btn)
        self._fr_bar.hide()
        chat_page_lay.addWidget(self._fr_bar)

        # Add friend bar (shown when neither friend nor pending)
        self._add_fr_bar = QFrame()
        self._add_fr_bar.setStyleSheet("QFrame { background: #1a1a2e; padding: 8px; }")
        add_fr_lay = QHBoxLayout(self._add_fr_bar)
        add_fr_lay.setContentsMargins(12, 8, 12, 8)
        self._add_fr_lbl = QLabel("Not friends yet")
        self._add_fr_lbl.setStyleSheet("color: #6b7280; font-size: 12px;")
        add_fr_lay.addWidget(self._add_fr_lbl)
        add_fr_lay.addStretch()
        self._send_fr_btn = QPushButton("+ Add Friend")
        self._send_fr_btn.clicked.connect(self._send_friend_request)
        add_fr_lay.addWidget(self._send_fr_btn)
        # Block button in the add-friend bar
        self._block_btn = QPushButton("🚫 Block")
        self._block_btn.setStyleSheet("""
            QPushButton {
                background: transparent; color: #ef4444;
                border: 1.5px solid #ef4444; border-radius: 16px;
                padding: 6px 12px; font-size: 12px; font-weight: bold;
            }
            QPushButton:hover { background: #ef4444; color: #fff; }
        """)
        self._block_btn.clicked.connect(self._on_block_active_peer)
        add_fr_lay.addWidget(self._block_btn)
        self._add_fr_bar.hide()
        chat_page_lay.addWidget(self._add_fr_bar)

        # Input row
        input_frame = QFrame()
        input_frame.setStyleSheet("QFrame { background: #12122a; border-top: 1px solid #1e1e3a; }")
        input_lay = QHBoxLayout(input_frame)
        input_lay.setContentsMargins(14, 10, 14, 10)
        input_lay.setSpacing(10)

        self._msg_input = QLineEdit()
        self._msg_input.setPlaceholderText("type here  and click enter to send")
        self._msg_input.returnPressed.connect(self._send_message)
        input_lay.addWidget(self._msg_input, 1)

        send_btn = QPushButton("➤")
        send_btn.setFixedSize(40, 40)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7c3aed,stop:1 #a855f7);
                border-radius: 20px;
                font-size: 16px;
                padding: 0;
            }
        """)
        send_btn.clicked.connect(self._send_message)
        input_lay.addWidget(send_btn)

        chat_page_lay.addWidget(input_frame)
        self._chat_stack.addWidget(chat_page)

        right_lay.addWidget(self._chat_stack, 1)

        # Status bar at very bottom
        self._status_lbl = QLabel("🔍 Scanning for peers...")
        self._status_lbl.setStyleSheet("""
            color: #4b5563; font-size: 10px; padding: 4px 12px;
            border-top: 1px solid #1e1e3a; background: #0a0a14;
        """)
        right_lay.addWidget(self._status_lbl)

        root.addWidget(right, 1)

    # ── Peer management ────────────────────────────────────────────────────────

    def _refresh_peers(self):
        with _peers_lock:
            peers = list(_peers.values())
        with _friends_lock:
            friends = set(_friends)
            pending_in = set(_pending_in)
        with _blocked_lock:
            blocked = set(_blocked)
        with _first_msg_lock:
            first_pending = set(_first_msg_pending)

        # Clear lists
        for lay in (self._friends_list, self._online_list, self._blocked_list, self._conv_list):
            while lay.count():
                item = lay.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

        has_blocked = False
        for p in peers:
            ip = p["ip"]
            is_fr = ip in friends
            pend  = ip in pending_in or ip in first_pending
            blkd  = ip in blocked

            if blkd:
                has_blocked = True
                row = PeerRow(p, False, False, blocked=True)
                row.clicked.connect(self._open_chat)
                self._blocked_list.addWidget(row)
                continue

            # Left sidebar: friends section
            if is_fr:
                row = PeerRow(p, True, False)
                row.clicked.connect(self._open_chat)
                self._friends_list.addWidget(row)

            # Left sidebar: online section (non-friends, non-blocked)
            if not is_fr:
                row2 = PeerRow(p, False, pend)
                row2.clicked.connect(self._open_chat)
                self._online_list.addWidget(row2)

            # Center conversation list
            conv_btn = QPushButton()
            conv_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border-bottom: 1px solid #1e1e3a;
                    border-radius: 0;
                    text-align: left;
                    padding: 12px 16px;
                    color: #e2e8f8;
                    font-size: 13px;
                }
                QPushButton:hover { background: #1e1e3a; }
            """)
            msgs = get_messages(ip)
            last = msgs[-1]["text"][:28] + "…" if msgs else "No messages yet"
            badge = " 🔔" if pend and not is_fr else ""
            conv_btn.setText(f"  {p['username']}{badge}\n  {last}")
            conv_btn.clicked.connect(lambda checked, peer=p: self._open_chat(peer))
            self._conv_list.addWidget(conv_btn)

        # Show/hide blocked section
        self._blocked_hdr.setVisible(has_blocked)
        self._blocked_scroll.setVisible(has_blocked)

        # Update active chat if open
        if self._active_peer:
            self._load_bubbles(self._active_peer["ip"])
            self._update_friendship_bars(self._active_peer["ip"])

    def _open_chat(self, peer: dict):
        self._active_peer = peer
        self._chat_header.setText(f"  {peer['username']}  ·  {peer['ip']}")
        self._load_bubbles(peer["ip"])
        self._update_friendship_bars(peer["ip"])
        self._chat_stack.setCurrentIndex(1)
        self._msg_input.setFocus()

    def _update_friendship_bars(self, ip: str):
        with _friends_lock:
            is_fr   = ip in _friends
            pend_in = ip in _pending_in
            pend_out= ip in _pending_out
        with _first_msg_lock:
            first_pend = ip in _first_msg_pending
        blkd = is_blocked(ip)

        # First-message banner: show when someone who is not a friend sent us a msg
        self._first_msg_bar.setVisible(first_pend and not is_fr and not blkd)

        # Legacy friend-request bar
        self._fr_bar.setVisible(pend_in and not is_fr and not first_pend)

        # Add-friend bar
        if pend_out and not is_fr:
            self._add_fr_bar.show()
            self._add_fr_lbl.setText("Friend request sent — waiting…")
            self._send_fr_btn.hide()
            self._block_btn.show()
        elif not is_fr and not pend_in and not first_pend and not blkd:
            self._add_fr_bar.show()
            self._add_fr_lbl.setText("Not friends yet")
            self._send_fr_btn.show()
            self._block_btn.show()
        else:
            self._add_fr_bar.hide()

        # Disable input if blocked
        self._msg_input.setEnabled(not blkd)
        if blkd:
            self._msg_input.setPlaceholderText("🚫 User is blocked")

    def _load_bubbles(self, peer_ip: str):
        # Remove old bubbles (keep the trailing stretch)
        while self._bubble_lay.count() > 1:
            item = self._bubble_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        msgs = get_messages(peer_ip)
        for m in msgs:
            is_me = (m["from"] == MY_USERNAME)
            bw = BubbleWidget(m["from"], m["text"], is_me)
            self._bubble_lay.insertWidget(self._bubble_lay.count() - 1, bw)

        # Scroll to bottom
        QTimer.singleShot(50, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))

    def _on_message_received(self, peer_ip: str, from_name: str, text: str):
        # Register peer if unknown
        with _peers_lock:
            if peer_ip not in _peers:
                _peers[peer_ip] = {"username": from_name, "ip": peer_ip, "last_seen": time.time(), "status": "online"}
        self._refresh_peers()

    # ── First-message banner actions ──────────────────────────────────────────

    def _on_add_user_from_banner(self):
        if not self._active_peer:
            return
        ip = self._active_peer["ip"]
        with _friends_lock:
            _friends.add(ip)
        with _first_msg_lock:
            _first_msg_pending.discard(ip)
        _udp_send(ip, {"type": "friend_accept", "from": MY_USERNAME, "ip": MY_IP})
        self._refresh_peers()

    def _on_block_user_from_banner(self):
        if not self._active_peer:
            return
        ip = self._active_peer["ip"]
        with _first_msg_lock:
            _first_msg_pending.discard(ip)
        block_user(ip)
        self._first_msg_bar.hide()
        self._chat_stack.setCurrentIndex(0)
        self._active_peer = None
        self._refresh_peers()

    def _on_block_active_peer(self):
        if not self._active_peer:
            return
        ip = self._active_peer["ip"]
        block_user(ip)
        self._add_fr_bar.hide()
        self._chat_stack.setCurrentIndex(0)
        self._active_peer = None
        self._refresh_peers()

    # ── Friend requests ────────────────────────────────────────────────────────

    def _send_friend_request(self):
        if not self._active_peer:
            return
        ip = self._active_peer["ip"]
        _udp_send(ip, {"type": "friend_request", "from": MY_USERNAME, "ip": MY_IP})
        with _friends_lock:
            _pending_out.add(ip)
        self._update_friendship_bars(ip)

    def _accept_friend_request(self):
        if not self._active_peer:
            return
        ip = self._active_peer["ip"]
        _udp_send(ip, {"type": "friend_accept", "from": MY_USERNAME, "ip": MY_IP})
        with _friends_lock:
            _friends.add(ip)
            _pending_in.discard(ip)
        self._refresh_peers()

    # ── Sending messages ───────────────────────────────────────────────────────

    def _send_message(self):
        if not self._active_peer:
            return
        if is_blocked(self._active_peer["ip"]):
            return
        text = self._msg_input.text().strip()
        if not text:
            return
        self._msg_input.clear()
        peer_ip = self._active_peer["ip"]

        ok = tcp_send(peer_ip, text)
        if not ok:
            _add_msg(peer_ip, MY_USERNAME, f"[send failed] {text}")

        self._load_bubbles(peer_ip)
