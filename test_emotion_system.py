"""
Quick test script for Calcifer emotion system
Tests: FaceAvatar, CompanionArea, emotion parsing
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from ui_face_avatar import FaceAvatar

def test_face_emotions():
    """Cycle through all emotion modes"""
    app = QApplication(sys.argv)
    face = FaceAvatar()
    face.show()
    
    emotions = ["happy", "excited", "thinking", "sad", "angry", "surprised", "sleepy", "calm"]
    index = [0]
    
    def cycle_emotion():
        emotion = emotions[index[0] % len(emotions)]
        face.setEmotion(emotion, duration_ms=2000)
        print(f"✓ Testing emotion: {emotion}")
        index[0] += 1
        if index[0] >= len(emotions):
            print("\n✅ All emotions tested successfully!")
            QTimer.singleShot(2000, app.quit)
    
    # Cycle through emotions every 2.5 seconds
    timer = QTimer()
    timer.timeout.connect(cycle_emotion)
    timer.start(2500)
    cycle_emotion()  # Start immediately
    
    sys.exit(app.exec())

def test_emotion_parsing():
    """Test regex parsing of emotion tags"""
    import re
    test_cases = [
        ("[emotion: happy] I'm so glad to help!", "happy", "I'm so glad to help!"),
        ("Let me think... [emotion: thinking]", "thinking", "Let me think..."),
        ("[EMOTION: EXCITED] That's amazing!", "EXCITED", "That's amazing!"),
        ("No emotion tag here", None, "No emotion tag here"),
    ]
    
    print("\nTesting emotion tag parsing:")
    for text, expected_emotion, expected_text in test_cases:
        match = re.search(r'\[emotion:\s*(\w+)\]', text, re.IGNORECASE)
        if match:
            emotion = match.group(1).strip()
            cleaned = re.sub(r'\[emotion:\s*\w+\]', '', text, flags=re.IGNORECASE).strip()
        else:
            emotion = None
            cleaned = text
        
        if emotion == expected_emotion and cleaned == expected_text:
            print(f"  ✓ '{text[:40]}...' → emotion={emotion}, text='{cleaned[:30]}...'")
        else:
            print(f"  ✗ FAILED: '{text}' → got emotion={emotion}, expected {expected_emotion}")
            return False
    
    print("✅ All parsing tests passed!")
    return True

if __name__ == "__main__":
    print("=== Calcifer Emotion System Test ===\n")
    
    # Test 1: Emotion tag parsing
    if not test_emotion_parsing():
        sys.exit(1)
    
    # Test 2: Face animation (visual)
    print("\nStarting visual face animation test...")
    print("Watch the face cycle through emotions: happy → excited → thinking → sad → angry → surprised → sleepy → calm")
    test_face_emotions()
