import sys
import os
from pathlib import Path
from PyQt6.QtCore import QUrl, QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings

def main():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication(sys.argv)
    view = QWebEngineView()
    
    st = view.settings()
    st.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
    st.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    st.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
    
    web_dir = Path(__file__).resolve().parent / "web"
    index_path = web_dir / "index.html"
    
    def on_loaded(ok):
        print(f"Page loaded: {ok}")
        if not ok:
            app.quit()
            return
            
        def check_fonts(res):
            print("Font status:", res)
            # Render page to image
            img = view.grab()
            out_img = Path(__file__).resolve().parent / "ui_test_render.png"
            img.save(str(out_img))
            print(f"Saved render screenshot to {out_img}")
            app.quit()

        # Check if Material Symbols font is loaded in the page
        js = """
        (function() {
            var icon = document.querySelector('.material-symbols-outlined');
            var fontLoaded = document.fonts.check('16px "Material Symbols Outlined"');
            return {
                iconText: icon ? icon.textContent : 'none',
                fontLoaded: fontLoaded,
                fontCount: document.fonts.size
            };
        })();
        """
        QTimer.singleShot(1500, lambda: view.page().runJavaScript(js, check_fonts))

    view.loadFinished.connect(on_loaded)
    view.resize(1280, 800)
    view.load(QUrl.fromLocalFile(str(index_path)))
    
    # Timeout safety
    QTimer.singleShot(10000, app.quit)
    app.exec()

if __name__ == "__main__":
    main()
