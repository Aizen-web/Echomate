/* =====================================================================
   Calcifer web frontend — bridge + UI logic.

   Talks to the Python backend exclusively through the QWebChannel
   "bridge" object:  Python -> JS via signals (onState, onEmotion, ...),
   JS -> Python via methods (sendText, toggleMute, setupDone, ...).
   ===================================================================== */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  var root = document.documentElement;
  var bridge = null;

  /* ------------------------------------------------------------ state */
  var STATE_TEXT = {
    INITIALISING: ["Initialising…", "#8f8b84"],
    LISTENING:    ["Listening…", "#5BE3A6"],
    THINKING:     ["Thinking…", "#FFB020"],
    PROCESSING:   ["Processing…", "#FFB020"],
    SPEAKING:     ["Speaking…", "#FFB020"],
    MUTED:        ["Muted", "#FF4B5C"]
  };
  var STATE_FACE = {
    INITIALISING: "idle",
    MUTED:        "idle",
    LISTENING:    "listening",
    THINKING:     "thinking",
    PROCESSING:   "thinking",
    SPEAKING:     "speaking"
  };

  var EMOTION_COLORS = {
    happy: "#FFB020", proud: "#FFB020", playful: "#FFB020",
    love: "#FF8FB3",
    excited: "#FF5E6E", surprised: "#FF5E6E",
    thinking: "#8B7CFF", curious: "#8B7CFF", focused: "#8B7CFF",
    calm: "#4FC6E8", sleepy: "#4FC6E8", sad: "#4FC6E8",
    angry: "#FF4B5C", annoyed: "#FF4B5C", error: "#FF4B5C"
  };

  function parseHex(hex) {
    var h = hex.replace("#", "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    var n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function mix(hex, target, amt) {
    var a = parseHex(hex), b = target;
    var r = Math.round(a[0] + (b[0] - a[0]) * amt);
    var g = Math.round(a[1] + (b[1] - a[1]) * amt);
    var bl = Math.round(a[2] + (b[2] - a[2]) * amt);
    return "rgb(" + r + "," + g + "," + bl + ")";
  }
  function lighten(hex, amt) { return mix(hex, [255, 255, 255], amt); }

  function setEmotion(emotion) {
    var hex = EMOTION_COLORS[emotion] || "#FFB020";
    root.style.setProperty("--glow-color", hex);
    root.style.setProperty("--face-color", hex);
    root.style.setProperty("--feature-color", lighten(hex, 0.5));
    if (window.CalciferFace) CalciferFace.setEmotion(emotion);
  }

  function setState(state) {
    var entry = STATE_TEXT[state] || [state + "…", "#c3c0b9"];
    $("status-line").textContent = entry[0];
    $("status-line").style.color = entry[1];
    $("state-led").style.color = entry[1];
    if (window.CalciferFace) CalciferFace.setState(STATE_FACE[state] || "idle");
  }

  function setMuted(m) {
    var btn = $("mute-pill");
    var icon = $("mute-icon");
    btn.classList.toggle("muted", !!m);
    btn.title = m ? "Unmute" : "Mute";
    if (icon) icon.textContent = m ? "mic_off" : "mic";
    if (window.CalciferFace) CalciferFace.setMuted(m);
  }

  function setLite(l) {
    document.body.classList.toggle("lite", l);
    $("lite-toggle").checked = l;
    if (window.CalciferFace) CalciferFace.setLite(l);
  }

  /* ------------------------------------------------------------ clocks */
  function tickClock() {
    var now = new Date();
    function pad(n) { return n < 10 ? "0" + n : "" + n; }
    var hms = pad(now.getHours()) + ":" + pad(now.getMinutes()) + ":" + pad(now.getSeconds());
    var hm = pad(now.getHours()) + ":" + pad(now.getMinutes());
    $("stage-clock").textContent = hms;
    $("sb-clock").textContent = hm;
  }

  /* -------------------------------------------------------------- chat */
  var nearBottom = true;
  var msgEl = $("chat-messages");
  var chatScroll = $("chat-scroll");

  function scrollToBottom() {
    chatScroll.scrollTop = chatScroll.scrollHeight;
  }
  chatScroll.addEventListener("scroll", function () {
    nearBottom = (chatScroll.scrollHeight - chatScroll.scrollTop - chatScroll.clientHeight) < 60;
  });

  function renderMessages(messages) {
    msgEl.innerHTML = "";
    $("chat-empty").style.display = (messages && messages.length) ? "none" : "";
    for (var i = 0; i < messages.length; i++) {
      appendBubble(messages[i].role, messages[i].text, messages[i].time, false);
    }
    nearBottom = true;
    scrollToBottom();
  }

  function appendBubble(role, text, time, autoscroll) {
    $("chat-empty").style.display = "none";
    var el;
    if (role === "sys") {
      el = document.createElement("div");
      el.className = "sys-line";
      el.textContent = text;
    } else {
      var bubble = document.createElement("div");
      bubble.className = "bubble bubble-" + (role === "err" ? "err" : (role === "you" ? "you" : "ai"));
      var txt = document.createElement("div");
      txt.className = "bubble-text";
      txt.textContent = text;
      bubble.appendChild(txt);
      if (time) {
        var t = document.createElement("span");
        t.className = "bubble-time";
        t.textContent = time;
        bubble.appendChild(t);
      }
      el = bubble;
    }
    msgEl.appendChild(el);
    while (msgEl.children.length > 200) msgEl.removeChild(msgEl.firstChild);
    if (autoscroll !== false && nearBottom) scrollToBottom();
  }

  /* ------------------------------------------------------------ sidebar */
  function renderConvs(data) {
    var list = $("sb-convs");
    list.innerHTML = "";
    (data.convs || []).forEach(function (c) {
      var row = document.createElement("div");
      row.className = "conv-row" + (c.id === data.active ? " active" : "");
      row.dataset.id = c.id;

      var main = document.createElement("div");
      main.className = "conv-main";
      var title = document.createElement("div");
      title.className = "conv-title";
      title.textContent = c.title;
      title.dataset.kind = "title";
      var meta = document.createElement("div");
      meta.className = "conv-meta";
      meta.textContent = c.meta;
      main.appendChild(title);
      main.appendChild(meta);

      var del = document.createElement("button");
      del.className = "conv-del";
      del.textContent = "×";
      del.addEventListener("click", function (e) {
        e.stopPropagation();
        bridge.deleteConv(c.id);
      });

      row.appendChild(main);
      row.appendChild(del);

      row.addEventListener("click", function () { bridge.selectConv(c.id); });
      row.addEventListener("dblclick", function () { startRename(row, c.id); });
      row.addEventListener("contextmenu", function (e) {
        e.preventDefault();
        showConvMenu(c.id, e);
      });
      list.appendChild(row);
    });
  }

  function startRename(row, cid) {
    var titleEl = row.querySelector(".conv-title");
    var old = titleEl.textContent;
    var input = document.createElement("input");
    input.className = "chat-input";
    input.style.height = "20px";
    input.style.borderRadius = "6px";
    input.value = old;
    titleEl.replaceWith(input);
    input.focus();
    input.select();
    var done = function (commit) {
      var v = input.value.trim();
      if (commit && v && v !== old) bridge.renameConv(cid, v);
      input.replaceWith(titleEl);
    };
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") done(true);
      else if (e.key === "Escape") done(false);
    });
    input.addEventListener("blur", function () { done(true); });
  }

  function showConvMenu(cid, e) {
    var overlay = document.createElement("div");
    overlay.className = "overlay";
    overlay.style.background = "transparent";
    overlay.style.backdropFilter = "none";
    var box = document.createElement("div");
    box.className = "glass-raised";
    box.style.position = "fixed";
    box.style.padding = "6px";
    box.style.minWidth = "140px";
    var mk = function (label, fn) {
      var b = document.createElement("button");
      b.className = "palette-item";
      b.style.width = "100%";
      b.textContent = label;
      b.addEventListener("click", function () { overlay.remove(); fn(); });
      box.appendChild(b);
    };
    mk("Rename", function () {
      var row = document.querySelector('.conv-row[data-id="' + cid + '"]');
      if (row) startRename(row, cid);
    });
    mk("Delete", function () { bridge.deleteConv(cid); });
    overlay.addEventListener("click", function () { overlay.remove(); });
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    box.style.left = Math.min(e.clientX, window.innerWidth - 160) + "px";
    box.style.top = e.clientY + "px";
  }

  function renderTasks(tasks) {
    var running = tasks.filter(function (t) { return t.status === "running"; }).length;
    var label = "Tasks";
    if (running) label = "Tasks (" + running + " running)";
    else if (tasks.length) label = "Tasks (" + tasks.length + ")";
    var labelEl = $("sb-tasks").querySelector(".nav-label");
    if (labelEl) labelEl.textContent = label;

    var panel = $("sb-tasks-panel");
    if (panel.classList.contains("hidden")) return;
    var colors = {
      pending: "#8f8b84", running: "#FFB020",
      completed: "#5BE3A6", failed: "#FF4B5C", cancelled: "#8f8b84"
    };
    panel.innerHTML = "";
    if (!tasks.length) {
      var e = document.createElement("div");
      e.className = "task-empty";
      e.textContent = "No background tasks yet.";
      panel.appendChild(e);
      return;
    }
    var shown = tasks.slice(-6).reverse();
    shown.forEach(function (t) {
      var row = document.createElement("div");
      row.className = "task-row";
      row.style.color = colors[t.status] || "#8f8b84";
      var goal = t.goal || "";
      if (goal.length > 34) goal = goal.slice(0, 33) + "…";
      row.textContent = "● " + goal;
      panel.appendChild(row);
    });
  }

  /* ------------------------------------------------------------- toasts */
  function showToast(text, color) {
    var box = $("toasts");
    var t = document.createElement("div");
    t.className = "toast";
    t.textContent = text;
    t.style.color = color;
    box.appendChild(t);
    setTimeout(function () {
      t.classList.add("dismissing");
      setTimeout(function () { t.remove(); }, 320);
    }, 3200);
  }

  /* ----------------------------------------------------------- palette */
  var COMMANDS = [
    ["Open an application", "Open {arg}", "Type an app name, e.g. Chrome", null],
    ["Search the web", "Search the web for {arg}", "Type a search query", null],
    ["Check the weather", "Check the weather in {arg}", "Type a city name", null],
    ["Set a reminder", "Set a reminder: {arg}", "Describe the reminder", null],
    ["Play a YouTube video", "Play the YouTube video {arg}", "Type a video title", null],
    ["Send a message", "Send a message to {arg}", "Type a contact name", null],
    ["Take a screenshot", "Take a screenshot and analyze it", null, null],
    ["Manage files", "Help me manage files: {arg}", "Describe the file task", null],
    ["New chat", null, null, "new_chat"],
    ["Mute / unmute mic", null, null, "toggle_mute"],
    ["Open settings", null, null, "settings"]
  ];

  var paletteSel = 0;
  var paletteArg = false;
  var palettePending = "";

  function paletteOpen() {
    $("palette").classList.remove("hidden");
    paletteArg = false;
    $("palette-input").value = "";
    $("palette-input").placeholder = "What do you want Calcifer to do?";
    $("palette-hint").textContent = "Esc to close";
    paletteRender();
    $("palette-input").focus();
  }
  function paletteClose() { $("palette").classList.add("hidden"); }
  function paletteToggle() {
    if ($("palette").classList.contains("hidden")) paletteOpen();
    else paletteClose();
  }

  function paletteRender() {
    var q = $("palette-input").value.trim().toLowerCase();
    var list = $("palette-list");
    list.innerHTML = "";
    var visible = [];
    COMMANDS.forEach(function (c, i) {
      if (paletteArg) return;
      if (q && c[0].toLowerCase().indexOf(q) === -1) return;
      visible.push(i);
      var el = document.createElement("div");
      el.className = "palette-item";
      el.textContent = c[0];
      el.dataset.index = i;
      el.addEventListener("click", function () { paletteRun(i); });
      el.addEventListener("mousemove", function () { paletteSel = i; paletteMark(); });
      list.appendChild(el);
    });
    paletteSel = visible.length ? 0 : -1;
    paletteMark();
  }
  function paletteMark() {
    var items = $("palette-list").querySelectorAll(".palette-item");
    for (var i = 0; i < items.length; i++) {
      items[i].classList.toggle("sel", i === paletteSel);
    }
  }
  function paletteRun(index) {
    var c = COMMANDS[index];
    if (!c) return;
    if (c[3]) {
      bridge.paletteAction(c[3]);
      paletteClose();
      return;
    }
    if (c[1] && c[1].indexOf("{arg}") !== -1) {
      paletteArg = true;
      palettePending = c[1];
      $("palette-input").value = "";
      $("palette-input").placeholder = c[2] || "Type a value…";
      $("palette-hint").textContent = "Enter to run · Esc to cancel";
      $("palette-list").innerHTML = "";
      $("palette-input").focus();
      return;
    }
    bridge.sendCommand(c[1]);
    paletteClose();
  }
  function paletteCommit() {
    if (paletteArg) {
      var arg = $("palette-input").value.trim();
      if (!arg) return;
      bridge.sendCommand(palettePending.replace("{arg}", arg));
      paletteClose();
      return;
    }
    var items = $("palette-list").querySelectorAll(".palette-item");
    if (paletteSel >= 0 && items[paletteSel]) {
      paletteRun(parseInt(items[paletteSel].dataset.index, 10));
    }
  }

  /* -------------------------------------------------------- setup modal */
  var selOs = "linux";
  function setupShow() {
    $("setup").classList.remove("hidden");
    var row = $("os-row");
    row.innerHTML = "";
    [["windows", "Windows"], ["mac", "macOS"], ["linux", "Linux"]].forEach(function (o) {
      var b = document.createElement("button");
      b.className = "os-btn";
      b.textContent = o[1];
      b.addEventListener("click", function () { selOs = o[0]; paintOs(); });
      row.appendChild(b);
    });
    paintOs();
    $("setup-gemini").value = "";
    $("setup-or").value = "";
  }
  function paintOs() {
    var btns = $("os-row").querySelectorAll(".os-btn");
    var colors = { windows: "#FFB020", mac: "#5BE3A6", linux: "#5BE3A6" };
    for (var i = 0; i < btns.length; i++) {
      var keys = ["windows", "mac", "linux"];
      var sel = keys[i] === selOs;
      btns[i].classList.toggle("sel", sel);
      if (sel) {
        btns[i].style.background = colors[keys[i]];
        btns[i].style.color = "#141006";
      } else {
        btns[i].style.background = "rgba(255,255,255,0.05)";
        btns[i].style.color = "#c3c0b9";
      }
    }
  }
  function setupSubmit() {
    var g = $("setup-gemini").value.trim();
    var o = $("setup-or").value.trim();
    var ok = true;
    if (!g) { $("setup-gemini").classList.add("error"); ok = false; }
    else $("setup-gemini").classList.remove("error");
    if (!o) { $("setup-or").classList.add("error"); ok = false; }
    else $("setup-or").classList.remove("error");
    if (ok) bridge.setupDone(g, o, selOs);
  }

  /* -------------------------------------------------------- settings modal */
  function settingsShow() {
    var box = $("palette-swatches");
    box.innerHTML = "";
    [
      ["Happy · Proud · Playful", "#FFB020"],
      ["Excited · Surprised", "#FF5E6E"],
      ["Thinking · Curious · Focused", "#8B7CFF"],
      ["Calm · Sleepy · Sad", "#4FC6E8"],
      ["Angry · Annoyed · Error", "#FF4B5C"],
      ["Love", "#FF8FB3"]
    ].forEach(function (s) {
      var row = document.createElement("div");
      row.className = "swatch-row";
      var sw = document.createElement("div");
      sw.className = "swatch";
      sw.style.background = "radial-gradient(circle at 35% 30%, " + lighten(s[1], 0.35) + ", " + s[1] + ")";
      var lbl = document.createElement("span");
      lbl.textContent = s[0];
      row.appendChild(sw);
      row.appendChild(lbl);
      box.appendChild(row);
    });
    $("settings").classList.remove("hidden");
  }

  /* --------------------------------------------------------- chat collapse */
  var chatCollapsed = false;
  function setChatCollapsed(c) {
    chatCollapsed = c;
    $("chat").classList.toggle("collapsed", c);
    var icon = $("chat-collapse").querySelector(".material-symbols-outlined");
    if (icon) icon.textContent = c ? "chevron_left" : "chevron_right";
  }
  function onResize() {
    if (window.innerWidth < 860 && !chatCollapsed) setChatCollapsed(true);
  }

  /* -------------------------------------------------------- file chip */
  function setFile(data) {
    if (!data) {
      $("file-chip").classList.add("hidden");
      return;
    }
    $("chip-label").textContent = "File: " + data.name + "  ·  " + data.size;
    $("file-chip").classList.remove("hidden");
  }

  /* -------------------------------------------------------- bridge wiring */
  function initBridge(channel) {
    bridge = channel.objects.bridge;
    if (!bridge) return;
    window.bridge = bridge;

    bridge.onState.connect(function (s) { setState(s); });
    bridge.onEmotion.connect(function (e) { setEmotion(e); });
    bridge.onMuted.connect(function (m) { setMuted(m); });
    bridge.onFile.connect(function (json) { setFile(json ? JSON.parse(json) : null); });
    bridge.onTasks.connect(function (json) { renderTasks(JSON.parse(json)); });
    bridge.onConvs.connect(function (json) { renderConvs(JSON.parse(json)); });
    bridge.onMessages.connect(function (json) { renderMessages(JSON.parse(json)); });
    bridge.onSetup.connect(function (needed) {
      if (needed) setupShow(); else $("setup").classList.add("hidden");
    });
    bridge.onLite.connect(function (l) { setLite(l); });
    bridge.onToast.connect(function (text, color) { showToast(text, color); });
    bridge.onOpenSettings.connect(function () { settingsShow(); });
    bridge.onReady.connect(function () { });

    /* start interaction */
    document.getElementById("sb-new").addEventListener("click", function () { bridge.newChat(); });
    document.getElementById("sb-settings").addEventListener("click", function () { bridge.openSettings(); });
    document.getElementById("sb-collapse").addEventListener("click", function () {
      document.body.classList.toggle("side-collapsed");
    });
    document.getElementById("sb-tasks").addEventListener("click", function () {
      $("sb-tasks-panel").classList.toggle("hidden");
    });

    document.getElementById("chat-collapse").addEventListener("click", function () {
      setChatCollapsed(!chatCollapsed);
    });
    document.getElementById("attach-btn").addEventListener("click", function () { bridge.attachFile(); });
    document.getElementById("chip-clear").addEventListener("click", function () { bridge.clearFile(); });

    var input = document.getElementById("chat-input");
    var send = document.getElementById("send-btn");
    function syncSend() {
      send.disabled = !input.value.trim();
    }
    input.addEventListener("input", syncSend);
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { sendMessage(); }
    });
    send.addEventListener("click", sendMessage);
    function sendMessage() {
      var txt = input.value.trim();
      if (!txt) return;
      input.value = "";
      syncSend();
      bridge.sendText(txt);
    }

    document.getElementById("mute-pill").addEventListener("click", function () { bridge.toggleMute(); });
    document.getElementById("palette-input").addEventListener("input", paletteRender);
    document.getElementById("palette-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter") paletteCommit();
      else if (e.key === "ArrowDown") { paletteSel = (paletteSel + 1) % Math.max(1, $("palette-list").childElementCount); paletteMark(); }
      else if (e.key === "ArrowUp") { paletteSel = (paletteSel - 1 + Math.max(1, $("palette-list").childElementCount)) % Math.max(1, $("palette-list").childElementCount); paletteMark(); }
    });

    document.getElementById("lite-toggle").addEventListener("change", function (e) {
      bridge.setLite(e.target.checked);
    });
    document.getElementById("settings-done").addEventListener("click", function () {
      $("settings").classList.add("hidden");
    });
    document.getElementById("setup-submit").addEventListener("click", setupSubmit);

    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey && !e.shiftKey && !e.altKey && e.key === "k") {
        e.preventDefault();
        paletteToggle();
      }
      if (e.key === "Escape") {
        if (!$("palette").classList.contains("hidden")) paletteClose();
        else if (!$("settings").classList.contains("hidden")) $("settings").classList.add("hidden");
      }
    });

    window.addEventListener("resize", onResize);
    onResize();

    tickClock();
    setInterval(tickClock, 1000);

    /* notify Python that the JS side is listening */
    bridge.ready();
  }

  window.addEventListener("DOMContentLoaded", function () {
    if (window.QWebChannel && window.qt && window.qt.webChannelTransport) {
      new QWebChannel(window.qt.webChannelTransport, initBridge);
    }
  });
})();
