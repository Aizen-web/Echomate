from __future__ import annotations

import json
import os
import platform
import sys
import threading
import time
import uuid
from pathlib import Path

from PyQt6.QtCore import QObject, QUrl, Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow

from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView

if sys.platform.startswith("linux") and hasattr(os, "geteuid") and os.geteuid() == 0:
    os.environ.setdefault(
        "QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-dev-shm-usage")


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR      = _base_dir()
WEB_DIR       = BASE_DIR / "web"
CONFIG_DIR    = BASE_DIR / "config"
API_FILE      = CONFIG_DIR / "api_keys.json"
CONV_FILE     = CONFIG_DIR / "conversations.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

_DEFAULT_W, _DEFAULT_H = 1280, 780
_MIN_W,     _MIN_H     = 680, 560

# ---------------------------------------------------------------------------
# Emotion -> colour mapping (drives the glow + face tint in the frontend)
# ---------------------------------------------------------------------------
EMOTION_COLORS = {
    "happy":     "#FFB020",  # Deep warm gold
    "proud":     "#FFB020",
    "playful":   "#FFB020",
    "love":      "#FF8FB3",  # Warm rose
    "excited":   "#FF5E6E",  # Vivid coral / hot pink
    "surprised": "#FF5E6E",
    "thinking":  "#8B7CFF",  # Rich violet
    "curious":   "#8B7CFF",
    "focused":   "#8B7CFF",
    "calm":      "#4FC6E8",  # Jewel teal
    "sleepy":    "#4FC6E8",
    "sad":       "#4FC6E8",
    "angry":     "#FF4B5C",  # Ember red
    "annoyed":   "#FF4B5C",
    "error":     "#FF4B5C",
}


def get_emotion_color(emotion: str) -> QColor:
    return QColor(EMOTION_COLORS.get(emotion.lower(), "#FFB020"))


# Deep glass chrome palette (kept for the backend/legacy callers + colour ids)
class C:
    BG         = "#0a0a0d"
    CHROME     = "#101014"
    PANEL      = "#15141a"
    PANEL2     = "#1b1a21"
    BORDER     = "#26252c"
    BORDER_HI  = "#3a3942"
    TEXT       = "#f2efe9"
    TEXT_MED   = "#c3c0b9"
    TEXT_DIM   = "#8f8b84"
    ACC        = "#FFB020"
    ACC_HI     = "#FFC554"
    ACC_DIM    = "#8A5A14"
    GREEN      = "#5BE3A6"
    RED        = "#FF4B5C"
    WHITE      = "#f8f5f0"


def _route_line(text: str):
    """Map a raw log line to (role, display_text)."""
    tl = text.lower()
    if tl.startswith("you:"):
        return "you", text.split(":", 1)[1].strip()
    if tl.startswith(("ecomate:", "calcifer:")):
        return "ai", text.split(":", 1)[1].strip()
    if tl.startswith("file:"):
        return "sys", text
    if "err" in tl:
        return "err", text
    return "sys", text


def _fmt_size(size: int) -> str:
    if   size < 1024:    return f"{size} B"
    elif size < 1024**2: return f"{size/1024:.1f} KB"
    elif size < 1024**3: return f"{size/1024**2:.1f} MB"
    else:                return f"{size/1024**3:.1f} GB"


# ---------------------------------------------------------------------------
# Web view: the entire UI is rendered by the embedded frontend (web/).
# The QWebEngineView fills the window; only OS-level things (window frame,
# shortcuts, file dialogs) stay native. The QWebChannel bridge carries every
# backend call through to the JS side and every JS interaction back.
# ---------------------------------------------------------------------------
class _WebView(QWebEngineView):
    file_dropped = pyqtSignal(str)

    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            super().dragEnterEvent(e)

    def dropEvent(self, e: QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self.file_dropped.emit(path)
                e.acceptProposedAction()
                return
        super().dropEvent(e)


class Bridge(QObject):
    """QWebChannel object exposed to the frontend as `bridge`.

    Python -> JS: the *on* signals below.
    JS -> Python: the @pyqtSlot methods below.
    """

    onReady      = pyqtSignal()
    onState      = pyqtSignal(str)
    onEmotion    = pyqtSignal(str)
    onMuted      = pyqtSignal(bool)
    onFile       = pyqtSignal(str)
    onTasks      = pyqtSignal(str)
    onConvs      = pyqtSignal(str)
    onMessages   = pyqtSignal(str)
    onSetup      = pyqtSignal(bool)
    onLite       = pyqtSignal(bool)
    onToast      = pyqtSignal(str, str)
    onOpenSettings = pyqtSignal()
    onSensors    = pyqtSignal(str)

    def __init__(self, win: "MainWindow"):
        super().__init__()
        self._win = win

    @pyqtSlot()
    def ready(self):
        self._win._push_initial()

    @pyqtSlot(str)
    def sendText(self, text: str):
        self._win._send(text)

    @pyqtSlot(str)
    def sendCommand(self, text: str):
        self._win._send(text)

    @pyqtSlot(str)
    def paletteAction(self, action: str):
        self._win._palette_action(action)

    @pyqtSlot()
    def newChat(self):
        self._win._new_chat()

    @pyqtSlot(str)
    def selectConv(self, cid: str):
        self._win._switch_conversation(cid)

    @pyqtSlot(str, str)
    def renameConv(self, cid: str, title: str):
        self._win._rename_conversation(cid, title)

    @pyqtSlot(str)
    def deleteConv(self, cid: str):
        self._win._delete_conversation(cid)

    @pyqtSlot()
    def attachFile(self):
        self._win._attach_file()

    @pyqtSlot()
    def clearFile(self):
        self._win._clear_file()

    @pyqtSlot()
    def toggleMute(self):
        self._win._toggle_mute()

    @pyqtSlot()
    def toggleFullscreen(self):
        self._win._toggle_fullscreen()

    @pyqtSlot()
    def openSettings(self):
        self._win._open_settings()

    @pyqtSlot(bool)
    def setLite(self, lite: bool):
        self._win._set_lite(lite)

    @pyqtSlot()
    def refreshSensors(self):
        self._win._poll_sensors()

    @pyqtSlot(str)
    def triggerAnimation(self, payload_json: str):
        self._win._trigger_animation(payload_json)

    @pyqtSlot(str)
    def setDeviceUrl(self, url: str):
        self._win._set_device_url(url)

    @pyqtSlot(str, str, str)
    def setupDone(self, gemini: str, or_key: str, os_name: str):
        self._win._on_setup_done(gemini, or_key, os_name)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    _log_sig     = pyqtSignal(str)
    _state_sig   = pyqtSignal(str)
    _emotion_sig = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self.setWindowTitle("EcoMate")
        icon_path = BASE_DIR / "ecomate.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)

        # Start in fullscreen mode
        self.showFullScreen()

        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - _DEFAULT_W) // 2,
            (screen.height() - _DEFAULT_H) // 2,
        )

        self.on_text_command = None
        self._muted = False
        self._current_file: str | None = None
        self._last_state = "INITIALISING"
        self._last_emotion = "happy"
        self._last_sensor_data: dict | None = None
        self._sensor_url = ""

        self._web = _WebView(self)
        self.setCentralWidget(self._web)
        self._web.file_dropped.connect(self._set_current_file)

        st = self._web.settings()
        st.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        st.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        st.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        self._channel = QWebChannel(self._web.page())
        self._bridge = Bridge(self)
        self._channel.registerObject("bridge", self._bridge)
        self._web.page().setWebChannel(self._channel)
        self._web.setUrl(QUrl.fromLocalFile(str(WEB_DIR / "index.html")))

        # --- conversations ---
        self._conversations: list[dict] = []
        self._active_id: str | None = None
        self._load_conversations()
        if not self._conversations:
            self._new_chat(select=True, save=False)

        # --- wiring ---
        self._log_sig.connect(self._append_log)
        self._state_sig.connect(self._apply_state)
        self._emotion_sig.connect(self._apply_emotion)

        # settings
        self._lite = False
        self._load_settings()
        
        # ESP32 connection retry tracking
        self._esp32_retry_count = 0
        self._esp32_max_retries = 3
        self._esp32_connection_aborted = False

        # Sensor polling every 3 seconds for real-time updates
        # Polls ESP32 automatically to show live sensor readings
        self._sensor_timer = QTimer(self)
        self._sensor_timer.timeout.connect(self._poll_sensors)
        self._sensor_timer.start(3000)  # Poll every 3 seconds

        # shortcuts (kept native: global hotkeys for mute/fullscreen)
        QShortcut(QKeySequence("F4"), self).activated.connect(self._toggle_mute)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)

        # background-task monitoring (activity feed + toasts)
        self._task_timer = QTimer(self)
        self._task_timer.timeout.connect(self._poll_tasks)
        self._task_timer.start(1000)
        self._known_task_status: dict[str, str] = {}

        # setup
        self._ready = self._check_config()

    # ---------------------------------------------------------- conversation
    def _load_conversations(self):
        try:
            if CONV_FILE.exists():
                data = json.loads(CONV_FILE.read_text(encoding="utf-8"))
                self._conversations = data.get("conversations", [])
                self._active_id = data.get("active_id")
        except Exception:
            self._conversations = []
            self._active_id = None

    def _save_conversations(self):
        try:
            CONFIG_DIR.mkdir(exist_ok=True)
            CONV_FILE.write_text(json.dumps({
                "conversations": self._conversations,
                "active_id": self._active_id,
            }, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _active_conv(self) -> dict | None:
        for c in self._conversations:
            if c["id"] == self._active_id:
                return c
        return None

    def _new_chat(self, select=True, save=True):
        conv = {
            "id": str(uuid.uuid4()),
            "title": "New chat",
            "created": time.time(),
            "updated": time.time(),
            "messages": [],
        }
        self._conversations.append(conv)
        if select:
            self._active_id = conv["id"]
        if save:
            self._save_conversations()
        self._push_convs()
        self._push_messages()

    def _switch_conversation(self, cid: str):
        self._active_id = cid
        self._save_conversations()
        self._push_convs()
        self._push_messages()

    def _rename_conversation(self, cid: str, title: str):
        title = (title or "").strip()
        if not title:
            return
        for c in self._conversations:
            if c["id"] == cid:
                c["title"] = title[:40]
                break
        self._save_conversations()
        self._push_convs()

    def _delete_conversation(self, cid: str):
        self._conversations = [c for c in self._conversations if c["id"] != cid]
        if self._active_id == cid:
            self._active_id = self._conversations[0]["id"] if self._conversations else None
        if not self._conversations:
            self._new_chat(select=True, save=False)
        self._save_conversations()
        self._push_convs()
        self._push_messages()

    def _maybe_title(self, conv: dict, role: str, body: str):
        if role == "you" and conv["title"] == "New chat" and body:
            conv["title"] = body[:28]

    def _append_log(self, text: str):
        conv = self._active_conv()
        if conv is None:
            return
        role, body = _route_line(text)
        conv["messages"].append({
            "role": role, "text": body, "time": time.strftime("%H:%M"),
        })
        if len(conv["messages"]) > 200:
            conv["messages"] = conv["messages"][-200:]
        conv["updated"] = time.time()
        self._maybe_title(conv, role, body)
        self._save_conversations()
        self._push_convs()
        self._push_messages()

    def _push_convs(self):
        convs = []
        for c in self._conversations:
            n = len(c.get("messages", []))
            meta = f"{time.strftime('%H:%M', time.localtime(c.get('updated', 0)))} · {n} msg"
            convs.append({"id": c["id"], "title": c.get("title", "New chat"), "meta": meta})
        self._bridge.onConvs.emit(json.dumps({
            "convs": convs, "active": self._active_id,
        }))

    def _push_messages(self):
        conv = self._active_conv()
        self._bridge.onMessages.emit(json.dumps(conv.get("messages", []) if conv else []))

    def _push_initial(self):
        self._bridge.onState.emit(self._last_state)
        self._bridge.onEmotion.emit(self._last_emotion)
        self._bridge.onMuted.emit(self._muted)
        self._bridge.onFile.emit(self._file_payload())
        self._bridge.onLite.emit(self._lite)
        self._bridge.onSetup.emit(not self._ready)
        self._push_convs()
        self._push_messages()
        self._poll_tasks()
        self._poll_sensors()

    # ----------------------------------------------------------- sensors
    @staticmethod
    def _normalise_sensor_payload(payload: dict, is_live: bool, source: str) -> dict:
        """Accept both the current flat firmware response and the documented
        nested response.  The browser receives one stable, presentation-only
        contract regardless of which compatible firmware is installed.
        """
        soil = payload.get("soil") if isinstance(payload.get("soil"), dict) else {}
        rain = payload.get("rain") if isinstance(payload.get("rain"), dict) else {}
        device = payload.get("device") if isinstance(payload.get("device"), dict) else {}

        soil_percent = soil.get("percent", payload.get("soil_percent"))
        soil_raw = soil.get("raw", payload.get("soil_raw"))
        leak_detected = rain.get("detected", payload.get("raindrop_wet"))
        leak_raw = rain.get("raw", payload.get("raindrop_raw"))

        try:
            soil_percent = max(0, min(100, int(soil_percent)))
        except (TypeError, ValueError):
            soil_percent = None

        return {
            "soil_percent": soil_percent,
            "soil_raw": soil_raw,
            "soil_status": soil.get("status") or (
                "Needs attention" if soil_percent is not None and (soil_percent < 25 or soil_percent > 90)
                else "Healthy" if soil_percent is not None and soil_percent >= 60
                else "Monitoring"
            ),
            "leak_detected": bool(leak_detected),
            "leak_raw": leak_raw,
            "leak_status": rain.get("severity") or ("Leak detected" if leak_detected else "Dry / safe"),
            "animation": device.get("animation") or payload.get("animation", "idle"),
            "is_live": is_live,
            "source": source,
            "updated_at": int(time.time()),
        }

    def _device_base_url(self) -> str:
        value = (self._sensor_url or "").strip()
        if not value:
            return ""
        if value.startswith(("http://", "https://")):
            return value.rstrip("/")
        return ("http://" + value).rstrip("/")

    def _sensor_url_from_settings(self) -> str:
        base = self._device_base_url()
        if not base:
            return ""
        return base + "/api/sensors"

    def _trigger_animation(self, payload_json: str) -> None:
        try:
            data = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError:
            data = {"animation": payload_json}

        animation = str(data.get("animation", "")).strip()
        if not animation:
            self._bridge.onToast.emit("No animation selected", "error")
            return

        base = self._device_base_url()
        if not base:
            self._bridge.onToast.emit("Add your ESP32 address in Settings first", "error")
            return

        body: dict = {
            "animation": animation,
            "lock_seconds": int(data.get("lock_seconds") or 60),
        }
        task = str(data.get("task") or "").strip()
        if task:
            body["task"] = task
        duration = data.get("duration")
        if duration:
            body["duration"] = int(duration)

        try:
            import requests

            response = requests.post(
                f"{base}/api/animation",
                json=body,
                timeout=3,
            )
            response.raise_for_status()
            result = response.json()
            name = result.get("animation", animation)
            self._append_log(f"SYS: Animation triggered on robot → {name}")
            self._bridge.onToast.emit(f"Playing “{name}” on Tabbie", "success")
            self._esp32_retry_count = 0
            self._esp32_connection_aborted = False
            self._poll_sensors()
        except Exception as exc:
            self._append_log(f"SYS: Animation request failed ({exc})")
            self._bridge.onToast.emit(f"Could not reach ESP32: {exc}", "error")

    def _emit_sensors(self):
        if self._last_sensor_data:
            self._bridge.onSensors.emit(json.dumps(self._last_sensor_data))
        else:
            self._bridge.onSensors.emit(json.dumps({
                "is_live": False, "configured": bool(self._sensor_url),
                "source": self._sensor_url, "updated_at": int(time.time()),
            }))

    def _poll_sensors(self):
        url = self._sensor_url_from_settings()
        if not url:
            self._emit_sensors()
            return
        
        # If connection was aborted after 3 failed attempts, don't retry
        if self._esp32_connection_aborted:
            self._emit_sensors()
            return
        
        prev_leak_state = None
        if self._last_sensor_data:
            prev_leak_state = self._last_sensor_data.get("leak_detected", False)
        
        try:
            import requests
            response = requests.get(url, timeout=2)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("Sensor response must be a JSON object")
            
            # Connection successful - reset retry counter
            self._esp32_retry_count = 0
            self._last_sensor_data = self._normalise_sensor_payload(payload, True, url)
            
            # Check if leak just started (transition from False/None to True)
            current_leak = self._last_sensor_data.get("leak_detected", False)
            if current_leak and not prev_leak_state:
                # Leak just detected! Auto-respond with AI
                self._handle_leak_alert()
                
        except Exception as e:
            # Connection failed - increment retry counter
            self._esp32_retry_count += 1
            
            if self._esp32_retry_count >= self._esp32_max_retries:
                # Abort after 3 failed attempts
                self._esp32_connection_aborted = True
                print(f"[ESP32] ❌ Connection aborted after {self._esp32_max_retries} failed attempts")
                self._append_log(f"SYS: ESP32 connection failed after {self._esp32_max_retries} attempts. Running without sensor data.")
            
            if self._last_sensor_data:
                self._last_sensor_data = dict(self._last_sensor_data)
                self._last_sensor_data["is_live"] = False
                self._last_sensor_data["updated_at"] = int(time.time())
            else:
                self._last_sensor_data = {
                    "is_live": False, "configured": True, "source": url,
                    "updated_at": int(time.time()),
                }
        self._emit_sensors()
    
    def _handle_leak_alert(self):
        """Auto-respond when leak is detected"""
        alert_msg = "[EMERGENCY] Water leak detected by sensor! The system needs immediate attention."
        self._append_log(f"SYSTEM ALERT: {alert_msg}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(alert_msg,), daemon=True).start()

    def _set_device_url(self, url: str):
        cleaned = url.strip().rstrip("/")
        if cleaned != self._sensor_url:
            self._sensor_url = cleaned
            self._last_sensor_data = None
            # Reset connection retry state when URL changes
            self._esp32_retry_count = 0
            self._esp32_connection_aborted = False
            self._save_settings()
        self._poll_sensors()

    def sensor_context(self) -> str:
        """A compact, current context injected into every text turn."""
        # Force a fresh poll to get the absolute latest data before generating context
        if self._sensor_url_from_settings():
            import requests
            try:
                url = self._sensor_url_from_settings()
                response = requests.get(url, timeout=1.5)
                if response.ok:
                    payload = response.json()
                    if isinstance(payload, dict):
                        self._last_sensor_data = self._normalise_sensor_payload(payload, True, url)
            except Exception:
                pass  # Use cached data if fetch fails
        
        data = self._last_sensor_data
        if not data:
            return "EcoMate sensor status: no ESP32 reading has been received yet."
        if not data.get("is_live"):
            return "EcoMate sensor status: the last reading is stale because the ESP32 is offline or not configured."
        soil = data.get("soil_percent")
        soil_text = f"{soil}%" if soil is not None else "unknown"
        return (
            f"EcoMate live sensor status: soil moisture {soil_text} ({data.get('soil_status', 'monitoring')}); "
            f"leak sensor: {data.get('leak_status', 'unknown')}; "
            f"device animation: {data.get('animation', 'idle')}."
        )

    # ---------------------------------------------------------------- chat
    def _send(self, txt: str):
        txt = txt.strip()
        if not txt:
            return
        self._append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _attach_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file for EcoMate", str(Path.home()),
            "All Files (*.*);;"
            "Images (*.jpg *.jpeg *.png *.gif *.webp *.bmp *.svg);;"
            "Documents (*.pdf *.docx *.txt *.md *.pptx);;"
            "Data (*.csv *.xlsx *.json *.xml);;"
            "Code (*.py *.js *.ts *.html *.css *.java *.cpp *.go);;"
            "Audio (*.mp3 *.wav *.ogg *.m4a *.aac *.flac);;"
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.webm);;"
            "Archives (*.zip *.rar *.tar *.gz *.7z)",
        )
        if path:
            self._set_current_file(path)

    def _file_payload(self) -> str:
        if not self._current_file:
            return ""
        try:
            p = Path(self._current_file)
            return json.dumps({"name": p.name, "size": _fmt_size(p.stat().st_size)})
        except Exception:
            return json.dumps({"name": Path(self._current_file).name, "size": ""})

    def _set_current_file(self, path: str):
        try:
            p = Path(path)
            size = _fmt_size(p.stat().st_size)
            self._current_file = path
            self._bridge.onFile.emit(self._file_payload())
            self._append_log(f"FILE: {p.name} ({size}) loaded")
            if self.on_text_command:
                msg = (
                    f"[FILE_UPLOADED] path={path} | name={p.name} | "
                    f"type={p.suffix.lstrip('.')} | size={size} | "
                    f"Briefly tell the user you can see the file '{p.name}' "
                    f"({size}) has been uploaded and ask what they'd like to do with it."
                )
                threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()
        except Exception:
            pass

    def _clear_file(self):
        self._current_file = None
        self._bridge.onFile.emit("")

    # ----------------------------------------------------------- companion
    def _apply_state(self, state: str):
        self._last_state = state
        self._bridge.onState.emit(state)

    def _apply_emotion(self, emotion: str):
        self._last_emotion = emotion
        self._bridge.onEmotion.emit(emotion)

    def _toggle_mute(self):
        self._muted = not self._muted
        self._bridge.onMuted.emit(self._muted)
        if self._muted:
            self._apply_state("MUTED")
            self._append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._append_log("SYS: Microphone active.")

    # ---------------------------------------------------------- quick cmds
    def _palette_action(self, action: str):
        if action == "new_chat":
            self._new_chat()
        elif action == "toggle_mute":
            self._toggle_mute()
        elif action == "settings":
            self._open_settings()

    # -------------------------------------------------------------- tasks
    def _poll_tasks(self):
        try:
            from agent.task_queue import get_queue
            tasks = get_queue().get_all_statuses()
        except Exception:
            tasks = []

        for t in tasks:
            tid = t.get("task_id")
            status = t.get("status", "pending")
            prev = self._known_task_status.get(tid)
            if status in ("completed", "failed", "cancelled"):
                if prev not in ("completed", "failed", "cancelled"):
                    self._toast_task(t)
            self._known_task_status[tid] = status

        self._bridge.onTasks.emit(json.dumps(tasks))

    def _toast_task(self, t: dict):
        status = t.get("status", "")
        goal = t.get("goal", "")
        color = C.GREEN
        text = "Finished:"
        if status == "failed":
            color = C.RED
            text = "Failed:"
        elif status == "cancelled":
            color = C.TEXT_DIM
            text = "Cancelled:"
        self._bridge.onToast.emit(f"{text} {goal[:48]}", color)

    # ------------------------------------------------------------ settings
    def _load_settings(self):
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                self._lite = bool(data.get("lite", False))
                self._sensor_url = str(data.get("esp32_url", "")).strip()
        except Exception:
            self._lite = False

    def _save_settings(self):
        try:
            CONFIG_DIR.mkdir(exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps({"lite": self._lite, "esp32_url": self._sensor_url}, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _set_lite(self, lite: bool):
        if lite != self._lite:
            self._lite = lite
            self._save_settings()
        self._bridge.onLite.emit(lite)

    def _open_settings(self):
        self._bridge.onOpenSettings.emit()

    # ------------------------------------------------------------ window
    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ------------------------------------------------------------ setup
    def _check_config(self) -> bool:
        if not API_FILE.exists():
            return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return (bool(d.get("gemini_api_key")) and
                    bool(d.get("openrouter_api_key")) and
                    bool(d.get("os_system")))
        except Exception:
            return False

    def _on_setup_done(self, key: str, or_key: str, os_name: str):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        API_FILE.write_text(
            json.dumps({
                "gemini_api_key":     key,
                "openrouter_api_key": or_key,
                "os_system":          os_name,
            }, indent=4),
            encoding="utf-8",
        )
        self._ready = True
        self._bridge.onSetup.emit(False)
        self._apply_state("LISTENING")
        self._append_log("SYS: Initialised. OS=%s. EcoMate online." % os_name.upper())


# ---------------------------------------------------------------------------
# Public backend-facing API (must stay compatible with main.py)
# ---------------------------------------------------------------------------
class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app

    def mainloop(self):
        self._app.exec()

    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._current_file

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def set_emotion(self, emotion: str):
        self._win._emotion_sig.emit(emotion)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def sensor_context(self) -> str:
        return self._win.sensor_context()

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")
