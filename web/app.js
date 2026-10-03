/* EcoMate's browser layer is deliberately presentation-only.  All device
   polling and Gemini work remains in Python behind the QWebChannel bridge. */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var bridge = null;
  var sensorData = null;
  var messages = [];
  
  // Notification state tracking
  var notificationsEnabled = false;
  var lastNotifiedSoilDry = false;
  var lastNotifiedSoilWet = false;
  var lastNotifiedLeak = false;

  var ROBOT_ANIMATIONS = [
    { id: "startup", name: "Startup", icon: "power_settings_new", oled: "startup01 bitmap loop", servo: "Left → right → center once", trigger: "Power-on (or replay from here)", lock: 25 },
    { id: "idle", name: "Idle", icon: "self_improvement", oled: "idle01 loop", servo: "Nod every 4th loop", trigger: "Default rest; soil 25–60%", lock: 45 },
    { id: "focus", name: "Focus", icon: "center_focus_strong", oled: "focus01 loop", servo: "Nudge at 50% of timer", trigger: "Pomodoro / study timer", task: "Focus session", duration: 120, lock: 120 },
    { id: "break", name: "Break", icon: "coffee", oled: "relax01 loop", servo: "Every loop: L → R → center", trigger: "Break timer / API alias relax", lock: 45 },
    { id: "love", name: "Love", icon: "favorite", oled: "love01 once", servo: "Celebration wiggle", trigger: "Task done; soil ≥ 60%", lock: 45 },
    { id: "paused", name: "Paused / Angry", icon: "mood_bad", oled: "angry static face", servo: "Shake every 30s", trigger: "Dry/wet soil, leak, timer paused", lock: 45 },
    { id: "pomodoro", name: "Pomodoro HUD", icon: "timer", oled: "Text focus screen + bar", servo: "Quick L → R → center", trigger: "Legacy pomodoro display mode", task: "Pomodoro", lock: 60 },
    { id: "complete", name: "Complete", icon: "celebration", oled: "Text “Great job!”", servo: "Wiggle then idle", trigger: "Task finished in dashboard", task: "Task complete!", lock: 30 }
  ];

  var STATE = {
    INITIALISING: ["Waking up…", "#a18b8d", "idle"], LISTENING: ["Listening", "#4cd98a", "listening"],
    THINKING: ["Thinking", "#e0a64c", "thinking"], PROCESSING: ["Checking that", "#e0a64c", "thinking"],
    SPEAKING: ["Speaking", "#df7c8c", "speaking"], MUTED: ["Voice muted", "#e05c5c", "idle"]
  };
  var EMOTION = { happy:"#df7c8c", proud:"#df7c8c", playful:"#df7c8c", love:"#ff8fb3", excited:"#e8768b", surprised:"#e8768b", thinking:"#b19cff", curious:"#b19cff", focused:"#b19cff", calm:"#8ed9d0", sleepy:"#8ed9d0", sad:"#8ed9d0", angry:"#e05c5c", annoyed:"#e05c5c", error:"#e05c5c" };
  function setState(state) { var v = STATE[state] || [state, "#a18b8d", "idle"]; $("status-line").textContent = v[0]; $("status-line").style.color = v[1]; $("state-led").style.background = v[1]; if (window.CalciferFace) window.CalciferFace.setState(v[2]); }
  function setEmotion(emotion) { var color = EMOTION[emotion] || EMOTION.happy; document.documentElement.style.setProperty("--face-color", color); document.documentElement.style.setProperty("--face-light", mix(color, 0.42)); if (window.CalciferFace) window.CalciferFace.setEmotion(emotion); }
  function mix(hex, amount) { var n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255; return "rgb(" + Math.round(r + (255 - r) * amount) + "," + Math.round(g + (255 - g) * amount) + "," + Math.round(b + (255 - b) * amount) + ")"; }
  function setMuted(muted) { $("mute-icon").textContent = muted ? "mic_off" : "mic"; }
  function setLite(lite) { document.body.classList.toggle("lite", lite); $("lite-toggle").checked = lite; if (window.CalciferFace) window.CalciferFace.setLite(lite); }

  // === THEME SWITCHER ===
  function setTheme(theme) {
    document.body.setAttribute("data-theme", theme);
    document.querySelectorAll(".theme-btn").forEach(function(btn) {
      btn.classList.toggle("active", btn.dataset.theme === theme);
    });
    try {
      localStorage.setItem("ecomate-color-theme", theme);
    } catch (_) {}
  }

  function loadTheme() {
    try {
      var savedTheme = localStorage.getItem("ecomate-color-theme");
      if (savedTheme) {
        setTheme(savedTheme);
      }
    } catch (_) {}
  }

  // === NOTIFICATION SYSTEM ===
  function requestNotificationPermission() {
    if (!("Notification" in window)) {
      console.warn("Browser doesn't support notifications");
      return Promise.resolve(false);
    }
    if (Notification.permission === "granted") {
      notificationsEnabled = true;
      return Promise.resolve(true);
    }
    if (Notification.permission !== "denied") {
      return Notification.requestPermission().then(function(permission) {
        notificationsEnabled = (permission === "granted");
        return notificationsEnabled;
      });
    }
    return Promise.resolve(false);
  }

  function showNotification(title, body, tag) {
    if (!notificationsEnabled) return;
    var notification = new Notification(title, {
      body: body,
      icon: "ecomate.ico",
      tag: tag || "ecomate-alert",
      requireInteraction: true,
      silent: false
    });
    notification.onclick = function() {
      window.focus();
      notification.close();
    };
  }

  function checkAndNotify(data) {
    if (!notificationsEnabled || !data.is_live) return;
    
    var soil = data.soil_percent;
    var leak = data.leak_detected;
    
    // Soil too dry (<30%)
    if (soil !== null && soil !== undefined && soil < 30 && !lastNotifiedSoilDry) {
      showNotification(
        "🌱 Soil Too Dry!",
        "Soil moisture is at " + soil + "%. Your plant needs water! Consider watering now to prevent stress.",
        "soil-dry"
      );
      lastNotifiedSoilDry = true;
      lastNotifiedSoilWet = false;
    } else if (soil >= 30) {
      lastNotifiedSoilDry = false;
    }
    
    // Soil overwatered (>75%)
    if (soil !== null && soil !== undefined && soil > 75 && !lastNotifiedSoilWet) {
      showNotification(
        "💧 Soil Overwatered!",
        "Soil moisture is at " + soil + "%. Too much water can harm roots. Hold off on watering for now.",
        "soil-wet"
      );
      lastNotifiedSoilWet = true;
      lastNotifiedSoilDry = false;
    } else if (soil <= 75) {
      lastNotifiedSoilWet = false;
    }
    
    // Water leak detected
    if (leak && !lastNotifiedLeak) {
      showNotification(
        "🚨 Water Leak Detected!",
        "A water leak has been detected! Please check your sensors and investigate immediately to prevent water waste.",
        "water-leak"
      );
      lastNotifiedLeak = true;
    } else if (!leak && lastNotifiedLeak) {
      showNotification(
        "✅ Leak Resolved",
        "The water leak has been cleared. Your system is secure.",
        "leak-cleared"
      );
      lastNotifiedLeak = false;
    }
  }

  function timeGreeting() { var hour = new Date().getHours(), greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"; $("time-greeting").textContent = greeting.toUpperCase(); }
  function statusClass(el, state) { el.className = "card-state " + state; }
  function renderSensors(data) {
    var prevData = sensorData;
    var newData = data || {};
    
    // Create fingerprint to detect actual changes
    var prevFingerprint = prevData ? JSON.stringify({
      soil: prevData.soil_percent,
      leak: prevData.leak_detected,
      live: prevData.is_live,
      status: prevData.soil_status,
      leak_status: prevData.leak_status,
      configured: prevData.configured || !!prevData.source
    }) : null;
    
    var newFingerprint = JSON.stringify({
      soil: newData.soil_percent,
      leak: newData.leak_detected,
      live: newData.is_live,
      status: newData.soil_status,
      leak_status: newData.leak_status,
      configured: newData.configured || !!newData.source
    });
    
    // If nothing changed, skip entire render
    if (prevFingerprint === newFingerprint) {
      return;
    }
    
    sensorData = newData;
    var live = !!newData.is_live, configured = !!newData.configured || !!newData.source, soil = newData.soil_percent;
    var leak = !!newData.leak_detected, soilState = soil === null || soil === undefined ? "" : (soil < 25 || soil > 90 ? "warning" : "good");
    
    // RED SCREEN DANGER MODE when leak detected
    if (!prevData || prevData.leak_detected !== leak) {
      document.body.classList.toggle("danger-mode", leak);
    }
    
    // Only update if values actually changed
    if (!prevData || prevData.soil_percent !== soil) {
      $("soil-value").textContent = soil === null || soil === undefined ? "—" : soil + "%";
      $("soil-trend").textContent = soilState === "good" ? "HEALTHY" : soilState === "warning" ? "CHECK" : "WAITING"; 
      statusClass($("soil-trend"), soilState);
    }
    
    if (!prevData || prevData.soil_status !== newData.soil_status || prevData.configured !== configured) {
      $("soil-detail").textContent = newData.soil_status || (configured ? "Connecting to ESP32…" : "Add your ESP32 address in Settings");
    }
    
    if (!prevData || prevData.leak_detected !== leak) {
      $("leak-value").textContent = newData.leak_detected === undefined ? "—" : (leak ? "Water found" : "Dry");
      $("leak-trend").textContent = leak ? "ALERT" : newData.leak_detected === undefined ? "WAITING" : "SAFE"; 
      statusClass($("leak-trend"), leak ? "danger" : newData.leak_detected === undefined ? "" : "good");
    }
    
    if (!prevData || prevData.leak_status !== newData.leak_status || prevData.configured !== configured) {
      $("leak-detail").textContent = newData.leak_status || (configured ? "Waiting for leak sensor" : "No ESP32 configured");
    }
    
    if (!prevData || prevData.is_live !== live || prevData.configured !== configured) {
      $("device-value").textContent = live ? "Live" : configured ? "Offline / stale" : "Not connected";
      $("device-detail").textContent = live ? "Last update just now" : configured ? "Last known values are preserved" : "Configure the local device address";
      $("device-trend").textContent = live ? "ONLINE" : "OFFLINE"; 
      statusClass($("device-trend"), live ? "good" : "");
      $("connection-label").textContent = live ? "EcoMate online" : "EcoMate"; 
      $("connection-detail").textContent = live ? "ESP32 sensor link active" : configured ? "ESP32 unavailable" : "Set up your ESP32";
    }
    
    var dot = document.querySelector(".profile-row .presence-dot"); 
    if (dot && (!prevData || prevData.leak_detected !== leak || prevData.is_live !== live)) {
      dot.classList.toggle("online", live); 
      dot.classList.toggle("alert", leak);
    }
    
    if (!prevData || prevData.leak_detected !== leak || prevData.soil_percent !== soil || prevData.is_live !== live) {
      var summary = !configured ? "Connect EcoMate to your ESP32 to see live soil and leak readings." : !live ? "Your ESP32 is unavailable, so EcoMate is showing the last known sensor status." : leak ? "Water was detected — check the leak sensor or nearby pipe." : soilState === "warning" ? "Your plant needs attention. EcoMate has noticed an unusual soil reading." : "Everything looks calm. Your plant and water monitor are doing well.";
      $("sensor-summary").textContent = summary; 
      $("greeting").textContent = leak ? "I spotted some water." : soilState === "warning" ? "Your plant needs a little care." : live ? "Your eco lab is feeling good." : "Your eco lab is waiting.";
    }
    
    // Check for notifications
    checkAndNotify(newData);
    
    // Only update detail view if anything changed
    if (!prevData || prevData.soil_percent !== soil || prevData.leak_detected !== leak || prevData.is_live !== live || prevData.animation !== newData.animation) {
      renderSensorDetail();
      updateAnimationsStatus();
    }
  }
  function renderSensorDetail() { var d = sensorData || {}, host = d.source || "Not configured", cards = [["Soil moisture", d.soil_percent === undefined || d.soil_percent === null ? "—" : d.soil_percent + "%", d.soil_status || "No reading received yet."], ["Leak detector", d.leak_detected === undefined ? "—" : d.leak_detected ? "Alert" : "Dry / safe", d.leak_status || "No reading received yet."], ["Connection", d.is_live ? "Live" : "Offline", d.is_live ? "Polling " + host : host === "Not configured" ? "Open settings to add the ESP32 IP address." : "The last known sensor values remain visible while reconnecting."], ["Device expression", d.animation || "idle", "The physical OLED chooses its ambient face from the current sensor condition."]]; var root = $("sensor-detail-cards"); root.innerHTML = ""; cards.forEach(function (c) { var el = document.createElement("article"); el.className = "sensor-detail-card"; el.innerHTML = "<h3></h3><strong></strong><p></p>"; el.children[0].textContent = c[0]; el.children[1].textContent = c[1]; el.children[2].textContent = c[2]; root.appendChild(el); }); }

  function makeBubble(message) { var el = document.createElement("div"); if (message.role === "sys") { el.className = "sys-line"; el.textContent = message.text; return el; } el.className = "bubble " + (message.role === "you" ? "you" : message.role === "err" ? "err" : "ai"); var text = document.createElement("div"); text.textContent = message.text; el.appendChild(text); if (message.time) { var time = document.createElement("span"); time.className = "bubble-time"; time.textContent = message.time; el.appendChild(time); } return el; }
  function renderMessages(next) { messages = next || []; var root = $("chat-messages"), history = $("history-messages"); root.innerHTML = ""; history.innerHTML = ""; $("chat-empty").classList.toggle("hidden", messages.length > 0); messages.forEach(function (m) { root.appendChild(makeBubble(m)); history.appendChild(makeBubble(m)); }); $("chat-scroll").scrollTop = $("chat-scroll").scrollHeight; }
  function renderConversations(data) { var root = $("conversation-list"); root.innerHTML = ""; (data.convs || []).forEach(function (c) { var row = document.createElement("div"); row.className = "conversation-row" + (c.id === data.active ? " active" : ""); var main = document.createElement("div"); main.className = "conversation-main"; var title = document.createElement("div"); title.className = "conversation-title"; title.textContent = c.title; var meta = document.createElement("div"); meta.className = "conversation-meta"; meta.textContent = c.meta; main.appendChild(title); main.appendChild(meta); row.appendChild(main); var remove = document.createElement("button"); remove.className = "conversation-delete"; remove.textContent = "×"; remove.title = "Delete"; remove.addEventListener("click", function (e) { e.stopPropagation(); bridge.deleteConv(c.id); }); row.appendChild(remove); row.addEventListener("click", function () { bridge.selectConv(c.id); }); row.addEventListener("dblclick", function () { var name = window.prompt("Conversation name", c.title); if (name && name.trim()) bridge.renameConv(c.id, name.trim()); }); root.appendChild(row); }); }
  function setFile(json) { var data = json ? JSON.parse(json) : null; $("file-chip").classList.toggle("hidden", !data); if (data) $("file-label").textContent = data.name + (data.size ? " · " + data.size : ""); }
  function showToast(message, kind) {
    var el = $("toast");
    if (!el) return;
    el.textContent = message;
    el.className = "toast toast-" + (kind || "info");
    el.classList.remove("hidden");
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(function () { el.classList.add("hidden"); }, 4200);
  }

  function renderAnimationGallery() {
    var grid = $("animation-grid");
    var tbody = $("animation-reference-body");
    if (!grid || !tbody) return;
    grid.innerHTML = "";
    tbody.innerHTML = "";
    ROBOT_ANIMATIONS.forEach(function (anim) {
      var card = document.createElement("button");
      card.type = "button";
      card.className = "animation-card";
      card.setAttribute("role", "listitem");
      card.innerHTML = "<span class=\"material-symbols-outlined\">" + anim.icon + "</span><strong></strong><small></small>";
      card.children[1].textContent = anim.name;
      card.children[2].textContent = anim.trigger;
      card.addEventListener("click", function () {
        if (!bridge) return;
        bridge.triggerAnimation(JSON.stringify({
          animation: anim.id,
          task: anim.task || "",
          duration: anim.duration || 0,
          lock_seconds: anim.lock || 60
        }));
      });
      grid.appendChild(card);

      var row = document.createElement("tr");
      row.innerHTML = "<td><code></code></td><td></td><td></td><td></td>";
      row.children[0].children[0].textContent = anim.id;
      row.children[1].textContent = anim.oled;
      row.children[2].textContent = anim.servo;
      row.children[3].textContent = anim.trigger;
      tbody.appendChild(row);
    });
    updateAnimationsStatus();
  }

  function updateAnimationsStatus() {
    var el = $("animations-status");
    if (!el) return;
    var configured = sensorData && (sensorData.configured || sensorData.source);
    var live = sensorData && sensorData.is_live;
    var anim = sensorData && sensorData.animation ? sensorData.animation : "—";
    if (!configured) {
      el.textContent = "Add your ESP32 IP in Settings to control the physical OLED.";
    } else if (live) {
      el.textContent = "ESP32 online — current face: " + anim + ". Click a card to play on the robot.";
    } else {
      el.textContent = "ESP32 offline — clicks will retry the animation API. Last face: " + anim + ".";
    }
  }

  function switchView(view) {
    document.querySelectorAll(".nav-item").forEach(function (el) { el.classList.toggle("active", el.dataset.view === view); });
    document.querySelectorAll(".view").forEach(function (el) { el.classList.toggle("hidden", el.id !== view + "-view"); });
    var kicker = "ENVIRONMENTAL COMPANION";
    if (view === "history") kicker = "CONVERSATION HISTORY";
    else if (view === "sensors") kicker = "LIVE SENSOR STATUS";
    else if (view === "animations") kicker = "ROBOT ANIMATIONS";
    $("view-kicker").textContent = kicker;
    if (view === "animations") renderAnimationGallery();
  }
  function openSettings() { $("settings-modal").classList.remove("hidden"); $("device-url").value = sensorData && sensorData.source ? sensorData.source.replace(/\/api\/sensors$/, "") : ""; }
  function closeSettings() { $("settings-modal").classList.add("hidden"); }
  function toggleTheme() { var light = document.body.classList.toggle("theme-light"); document.body.classList.toggle("theme-dark", !light); $("theme-icon").textContent = light ? "dark_mode" : "light_mode"; try { localStorage.setItem("ecomate-theme", light ? "light" : "dark"); } catch (_) {} }

  function bindEvents() {
    $("new-chat").addEventListener("click", function () { bridge.newChat(); switchView("home"); }); 
    $("refresh-sensors").addEventListener("click", function () { bridge.refreshSensors(); }); 
    $("theme-toggle").addEventListener("click", toggleTheme); 
    $("settings-button").addEventListener("click", openSettings); 
    $("settings-button-top").addEventListener("click", openSettings); 
    document.querySelectorAll("[data-close-modal]").forEach(function (button) { button.addEventListener("click", closeSettings); }); 
    document.querySelectorAll(".nav-item").forEach(function (button) { button.addEventListener("click", function () { switchView(button.dataset.view); }); }); 
    $("mute-button").addEventListener("click", function () { bridge.toggleMute(); }); 
    $("attach-button").addEventListener("click", function () { bridge.attachFile(); }); 
    $("file-clear").addEventListener("click", function () { bridge.clearFile(); });
    
    // Theme switcher buttons
    document.querySelectorAll(".theme-btn").forEach(function(btn) {
      btn.addEventListener("click", function() {
        setTheme(btn.dataset.theme);
      });
    });
    
    var startBtn = $("start-button"); 
    if (startBtn) { 
      startBtn.addEventListener("click", function () { 
        if ($("mute-icon").textContent === "mic_off") { 
          bridge.toggleMute(); 
        } 
        setState("LISTENING"); 
        setEmotion("excited"); 
        // Request notification permission when starting
        requestNotificationPermission();
        bridge.sendText("Hello EcoMate! Ready to begin."); 
      }); 
    }
    
    $("save-settings").addEventListener("click", function () { bridge.setLite($("lite-toggle").checked); bridge.setDeviceUrl($("device-url").value.trim()); closeSettings(); }); 
    $("lite-toggle").addEventListener("change", function () { bridge.setLite(this.checked); });
    
    var input = $("chat-input"), send = $("send-button"); 
    function sync() { send.disabled = !input.value.trim(); } 
    function sendText() { var text = input.value.trim(); if (!text) return; bridge.sendText(text); input.value = ""; sync(); } 
    input.addEventListener("input", sync); 
    input.addEventListener("keydown", function (e) { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendText(); } }); 
    send.addEventListener("click", sendText);
    
    var selectedOs = "linux"; 
    $("os-row").addEventListener("click", function (e) { var button = e.target.closest("button[data-os]"); if (!button) return; selectedOs = button.dataset.os; $("os-row").querySelectorAll("button").forEach(function (b) { b.classList.toggle("selected", b === button); }); }); 
    $("setup-submit").addEventListener("click", function () { var gemini = $("setup-gemini").value.trim(), openRouter = $("setup-openrouter").value.trim(); if (!gemini || !openRouter) return; bridge.setupDone(gemini, openRouter, selectedOs); });
  }
  
  function init(channel) { 
    bridge = channel.objects.bridge; 
    if (!bridge) return; 
    bridge.onState.connect(setState); 
    bridge.onEmotion.connect(setEmotion); 
    bridge.onMuted.connect(setMuted); 
    bridge.onSensors.connect(function (json) { renderSensors(JSON.parse(json)); }); 
    bridge.onMessages.connect(function (json) { renderMessages(JSON.parse(json)); }); 
    bridge.onConvs.connect(function (json) { renderConversations(JSON.parse(json)); }); 
    bridge.onFile.connect(setFile); 
    bridge.onLite.connect(setLite); 
    bridge.onSetup.connect(function (needed) { $("setup-modal").classList.toggle("hidden", !needed); }); 
    bridge.onToast.connect(function (message, kind) { showToast(message, kind); });
    bindEvents(); 
    renderAnimationGallery();
    timeGreeting(); 
    loadTheme(); // Load saved theme on startup
    try { if (localStorage.getItem("ecomate-theme") === "light") toggleTheme(); } catch (_) {} 
    
    // Request notification permission on startup
    requestNotificationPermission();
    
    bridge.ready(); 
  }
  
  window.addEventListener("DOMContentLoaded", function () { if (window.QWebChannel && window.qt && window.qt.webChannelTransport) new QWebChannel(window.qt.webChannelTransport, init); });
})();
