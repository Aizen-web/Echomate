/* =====================================================================
   Calcifer face engine — hand-authored SVG, driven entirely by JS.

   Every expression is a set of scalar parameters (eye + mouth geometry)
   that share a fixed anchor layout, so morphing between expressions is a
   plain parameter interpolation with a consistent point count.  A per-frame
   easing step means colour/expression changes glide rather than snap.

   Expressions are authored as code: to add or tweak one, edit the
   EXPRESSIONS table below — no external animation assets.
   ===================================================================== */
(function () {
  "use strict";

  var D = 0.15;               // easing coefficient per frame (~300ms glide)
  var eyeL = document.getElementById("eye-l");
  var eyeR = document.getElementById("eye-r");
  var mouth = document.getElementById("mouth");
  var face = document.getElementById("face");
  var glow = document.getElementById("glow");

  var exprMap = {
    happy: "happy", proud: "happy", playful: "happy",
    love: "love",
    excited: "excited", surprised: "surprised",
    thinking: "thinking", curious: "thinking", focused: "thinking",
    calm: "calm", sleepy: "sleepy", sad: "sad",
    angry: "angry", annoyed: "angry", error: "angry"
  };

  /* Eye geometry params (see eyePath for meaning).
     cx     = horizontal offset from FACE_CX (200)
     cy     = absolute vertical centre (viewBox 400x300)
     w      = half width          up = upper lid arch (+ raised)
     h      = vertical extent     dn = lower lid depth
     tilt   = degrees of rotation */
  var EXPRESSIONS = {
    happy:     { eyeL: {cx:-46, cy:96, w:34, h:20, up:17, dn:-1, tilt:-2},
                 eyeR: {cx: 46, cy:96, w:34, h:20, up:17, dn:-1, tilt: 2},
                 mouth:{w:46, cup:13, h:5} },
    love:      { eyeL: {cx:-44, cy:98, w:30, h:14, up:19, dn:3,  tilt:-4},
                 eyeR: {cx: 44, cy:98, w:30, h:14, up:19, dn:3,  tilt: 4},
                 mouth:{w:34, cup:9, h:4} },
    surprised: { eyeL: {cx:-46, cy:90, w:42, h:34, up:6,  dn:6,  tilt: 0},
                 eyeR: {cx: 46, cy:90, w:42, h:34, up:6,  dn:6,  tilt: 0},
                 mouth:{w:30, cup:2, h:27} },
    excited:   { eyeL: {cx:-46, cy:92, w:40, h:30, up:10, dn:4,  tilt:-3},
                 eyeR: {cx: 46, cy:92, w:40, h:30, up:10, dn:4,  tilt: 3},
                 mouth:{w:40, cup:7, h:20} },
    thinking:  { eyeL: {cx:-44, cy:82, w:30, h:14, up:6,  dn:2,  tilt: 0},
                 eyeR: {cx: 44, cy:86, w:34, h:18, up:10, dn:4,  tilt: 0},
                 mouth:{w:22, cup:2, h:4} },
    calm:      { eyeL: {cx:-46, cy:96, w:32, h:18, up:8,  dn:2,  tilt: 0},
                 eyeR: {cx: 46, cy:96, w:32, h:18, up:8,  dn:2,  tilt: 0},
                 mouth:{w:34, cup:3, h:3} },
    sleepy:    { eyeL: {cx:-46, cy:100,w:26, h:7,  up:-2, dn:-2, tilt: 0},
                 eyeR: {cx: 46, cy:100,w:26, h:7,  up:-2, dn:-2, tilt: 0},
                 mouth:{w:26, cup:2, h:2} },
    sad:       { eyeL: {cx:-44, cy:102,w:28, h:11, up:-4, dn:5,  tilt: 6},
                 eyeR: {cx: 44, cy:102,w:28, h:11, up:-4, dn:5,  tilt:-6},
                 mouth:{w:34, cup:-11, h:4} },
    angry:     { eyeL: {cx:-45, cy:104,w:24, h:10, up:-2, dn:7,  tilt: 9},
                 eyeR: {cx: 45, cy:104,w:24, h:10, up:-2, dn:7,  tilt:-9},
                 mouth:{w:34, cup:-8, h:3} }
  };

  var STATE_ANIM = {
    idle:      { class: "idle" },
    listening: { class: "listening" },
    thinking:  { class: "thinking" },
    speaking:  { class: "speaking" }
  };

  var state = "idle";
  var muted = false;
  var lite = false;
  var speaking = false;
  var cur = {
    eL: {cx:-46, cy:96, w:34, h:20, up:17, dn:-1, tilt:-2},
    eR: {cx: 46, cy:96, w:34, h:20, up:17, dn:-1, tilt: 2},
    m:  {w:46, cup:13, h:5}
  };

  var blinkTimer = 2600;
  var blinkActive = 0;   // countdown while eyes are squeezed shut
  var blinkIn = 0;       // easing-in counter
  var lastNow = 0;

  function clamp(v, a, b) { return v < a ? a : (v > b ? b : v); }

  /* --- smooth closed path through midpoints of a point list --- */
  function closedPath(pts) {
    var n = pts.length;
    var d = "M" + ((pts[0][0] + pts[n - 1][0]) / 2).toFixed(2) + " " +
                 ((pts[0][1] + pts[n - 1][1]) / 2).toFixed(2);
    for (var i = 0; i < n; i++) {
      var p = pts[i];
      var nx = pts[(i + 1) % n];
      var mx = (p[0] + nx[0]) / 2, my = (p[1] + nx[1]) / 2;
      d += " Q" + p[0].toFixed(2) + " " + p[1].toFixed(2) + " " + mx.toFixed(2) + " " + my.toFixed(2);
    }
    return d + " Z";
  }

  function rotate(pt, deg) {
    if (!deg) return pt;
    var r = deg * Math.PI / 180;
    var c = Math.cos(r), s = Math.sin(r);
    return [pt[0] * c - pt[1] * s, pt[0] * s + pt[1] * c];
  }

  function eyePath(e) {
    var pts = [
      [-e.w, 0], [-e.w * 0.5, -e.up], [0, -(e.up + e.h)], [e.w * 0.5, -e.up],
      [e.w, 0], [e.w * 0.5, -e.dn], [0, e.dn + e.h], [-e.w * 0.5, -e.dn]
    ];
    for (var i = 0; i < pts.length; i++) {
      var r = rotate(pts[i], e.tilt);
      pts[i] = [r[0] + FACE_CX + e.cx, r[1] + e.cy];
    }
    return closedPath(pts);
  }

  /* Face centre in the viewBox — cx values in EXPRESSIONS are offsets
     from this centre, so they must be added to it, not used as-is. */
  var FACE_CX = 200;

  /* Mouth sits on a fixed baseline below the eyes (viewBox 400x300,
     eyes ~y96-133, mouth baseline at y176 keeps it clear of them). */
  var MOUTH_Y = 176;

  function mouthPath(m) {
    var pts = [
      [FACE_CX - m.w, MOUTH_Y - m.cup], [FACE_CX, MOUTH_Y + m.cup],
      [FACE_CX + m.w, MOUTH_Y - m.cup],
      [FACE_CX + m.w * 0.55, MOUTH_Y + m.h * 0.6], [FACE_CX, MOUTH_Y + m.h],
      [FACE_CX - m.w * 0.55, MOUTH_Y + m.h * 0.6]
    ];
    return closedPath(pts);
  }

  function setEmotion(emotion) {
    var key = exprMap[emotion] || "happy";
    face.setAttribute("data-expr", key);
  }

  function setState(next) {
    state = STATE_ANIM[next] ? next : "idle";
    speaking = (state === "speaking");
    face.setAttribute("data-state", state);
    face.classList.toggle("speaking", speaking && !lite);
    glow.classList.toggle("speaking", speaking && !lite);
  }

  function setMuted(m) {
    muted = !!m;
    glow.classList.toggle("muted", muted);
  }

  function setLite(l) {
    lite = !!l;
    face.classList.toggle("lite", lite);
    glow.classList.toggle("lite", lite);
    if (lite) speaking = false;
  }

  function easeTo(curObj, targetObj) {
    for (var k in targetObj) {
      curObj[k] = curObj[k] + (targetObj[k] - curObj[k]) * D;
    }
  }

  function tick(now) {
    if (!lastNow) lastNow = now;
    var dt = now - lastNow;
    lastNow = now;

    var expr = EXPRESSIONS[face.getAttribute("data-expr")] || EXPRESSIONS.happy;

    /* --- idle motion overrides (blink + gaze drift) --- */
    blinkTimer -= dt;
    if (!lite && blinkTimer <= 0 && !blinkActive) {
      blinkActive = 110;          // shut time
      blinkIn = 90;               // ease-in time
      blinkTimer = 2200 + Math.random() * 3200;  // irregular, not metronomic
    }
    if (blinkActive > 0) blinkActive -= dt;
    if (blinkIn > 0) blinkIn -= dt;

    var blinkAmt = 0;
    if (blinkActive > 0) {
      var tPhase = (blinkIn > 0) ? (1 - blinkIn / 90) : 1;   // snap shut fast
      blinkAmt = (1 - blinkActive / 110) * 0.85 * tPhase;    // then ease open
      if (blinkActive < 45) blinkAmt = (1 - blinkActive / 110) * 0.85;
    }

    var gazeX = Math.sin(now * 0.00032) * 3.5;
    var gazeY = Math.sin(now * 0.00023 + 1.4) * 2.2;

    /* --- speaking mouth: rhythmic open/close --- */
    var mTarget = { w: expr.mouth.w, cup: expr.mouth.cup, h: expr.mouth.h };
    if (speaking && !lite) {
      var s = 0.5 + 0.5 * Math.sin(now * 0.024);
      mTarget.h = 4 + s * 18;
      mTarget.cup = mTarget.cup * (0.4 + s * 0.5);
      mTarget.w = expr.mouth.w * (0.9 + s * 0.25);
    }

    /* --- build targets --- */
    var tL = {
      cx: expr.eyeL.cx + gazeX, cy: expr.eyeL.cy + gazeY,
      w: expr.eyeL.w * (1 - blinkAmt), h: expr.eyeL.h * (1 - blinkAmt * 1.15),
      up: expr.eyeL.up * (1 - blinkAmt), dn: expr.eyeL.dn * (1 - blinkAmt),
      tilt: expr.eyeL.tilt
    };
    var tR = {
      cx: expr.eyeR.cx + gazeX, cy: expr.eyeR.cy + gazeY,
      w: expr.eyeR.w * (1 - blinkAmt), h: expr.eyeR.h * (1 - blinkAmt * 1.15),
      up: expr.eyeR.up * (1 - blinkAmt), dn: expr.eyeR.dn * (1 - blinkAmt),
      tilt: expr.eyeR.tilt
    };

    easeTo(cur.eL, tL);
    easeTo(cur.eR, tR);
    easeTo(cur.m, mTarget);

    eyeL.setAttribute("d", eyePath(cur.eL));
    eyeR.setAttribute("d", eyePath(cur.eR));
    mouth.setAttribute("d", mouthPath(cur.m));
  }

  /* export a small API used by app.js */
  window.CalciferFace = {
    setEmotion: setEmotion,
    setState: setState,
    setMuted: setMuted,
    setLite: setLite
  };

  setInterval(function () { tick(Date.now()); }, 30);
})();
