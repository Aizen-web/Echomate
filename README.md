# 🌱 EcoMate — Desktop Companion & AI Eco Lab

<div align="center">

**An AI-managed environmental companion and study buddy built for the Science Congress.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6%20WebEngine-41CD52.svg?style=flat&logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini%20API-4285F4.svg?style=flat&logo=google&logoColor=white)](https://ai.google.dev/)
[![Hardware](https://img.shields.io/badge/Hardware-ESP32%20DevKit%20V1-E7352C.svg?style=flat&logo=espressif&logoColor=white)](https://espressif.com)

</div>

---

## 📖 Overview

**EcoMate** transforms passive environmental monitoring into an interactive, affective experience. Instead of static sensor readouts, EcoMate combines:

1. **Physical Microcontroller (ESP32):** Telemetry from Soil Moisture (ADC1_CH7) and Rain/Leak Detection (ADC1_CH6) sensors.
2. **Conversational AI Agent:** Powered by Google's Gemini API with real-time sensor context injected into prompts.
3. **Glassmorphic Cybernetic Dashboard:** Modern embedded web UI (HTML5, CSS3, JavaScript, QWebChannel) featuring live sensor graphs, animated avatar, multi-theme selector, and telemetry controls.
4. **Affective Personality:** Dynamic states (Happy, Relaxed, Alert, Sassy) that react organically to environmental waste and study sessions.

---

## 🚀 Features

- 💧 **Real-time Environmental Telemetry:** Live soil moisture percentages, leak/drip detection warnings, and water conservation tracking.
- 🤖 **Interactive AI Assistant:** Voice and text interaction powered by Gemini, capable of discussing sensor conditions and study tasks.
- 🎨 **Modern Cybernetic UI:** Embedded glassmorphic design with animated avatar, ambient sky backdrops, and theme switching (Default Blue, Cherry Blossom, Mood Blue, Mystic Purple, Luxury Gold).
- 🔄 **ESP32 Network Bridge:** Asynchronous polling and sync with ESP32 hardware over local Wi-Fi.
- 🖥️ **Desktop Launcher:** Quick launch batch script and desktop shortcut installer.

---

## 🛠️ Getting Started

### Prerequisites

- **Python 3.11+** installed
- An active **Google Gemini API Key**
- ESP32 running the companion firmware (optional for offline/demo mode)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Aizen-web/Echomate.git
   cd Echomate
   ```

2. **Set up a virtual environment (recommended):**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # On Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your API Key:**
   Add your Gemini API key in `config/api_keys.json` or configure it in the app settings:
   ```json
   {
     "gemini": "YOUR_GEMINI_API_KEY_HERE"
   }
   ```

5. **Run EcoMate:**
   Double-click `Launch EcoMate.bat` or run:
   ```bash
   python main.py
   ```

---

## 📁 Project Architecture

```
Echomate/
├── main.py                     # Application entry point and orchestrator
├── ui.py                       # PyQt6 QWebEngineView window and Qt bridge
├── or_client.py                # Gemini Live & async AI communication client
├── calcifer_face.py            # Avatar face renderer and emotion states
├── calcifer_blob.py            # Minimal animated blob visualizer
├── actions/                    # Companion tool declarations & automation actions
├── agent/                      # Background agent routines
├── config/                     # Configuration schemas (keys ignored by git)
├── core/                       # System prompt and personality guidelines
├── memory/                     # Local memory management and state
├── web/                        # Embedded web frontend
│   ├── index.html              # Modern glassmorphism dashboard
│   ├── style.css               # Dynamic styling, themes, and animations
│   ├── app.js                  # Frontend state, charts, and QWebChannel logic
│   └── face.js                 # Frontend animated face engine
├── Launch EcoMate.bat          # Quick launcher script
└── Create Desktop Shortcut.ps1 # Helper to generate desktop icon
```

---

## 🛡️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
