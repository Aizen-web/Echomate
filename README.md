# A Face engine for Xiaozhi
A plugin code to have a simple face instead of the Xiaozhi AI firmware

Designed to be simple, modular, and easy to plug into existing display code without modifying core firmware.

[![Ko-fi](https://techtalkies.github.io/support_me_256.png)](https://ko-fi.com/techtalkies)

---

## 🚀 Features

- Animated eyes (blink + idle movement)
- Speaking animation (dynamic mouth)
- Multiple states:
  - Idle
  - Listening
  - Speaking
- Fully modular (separate from display driver)

---

## 🧩 Integration

The project should already be configured and working before making the below changes.

- Copy the 2 files from the Face Engine folder, into the main\display folder.
- In the main\CMakeLists.txt file, add the below line to the list of sources.
```
"display\face_engine.cc"
```
- Open main\display\oled_display.cc and paste the code from the Display code.c file.
- Delete the original SetupUI_128x64() function.
- Open main\display\oled_display.h and paste the below line inside the constructor.
```
void SetStatus(const char* status) override;
```
- Flash the firmware.
