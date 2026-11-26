import io
import os
import sys
 
# On Linux, use the desktop's native (GTK) file dialogs instead of Qt's own.
if sys.platform.startswith("linux") and not os.environ.get("QT_QPA_PLATFORMTHEME"):
    os.environ["QT_QPA_PLATFORMTHEME"] = "gtk3"
 
from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
 
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, ID3NoHeaderError
 
try:  # Optional: used to normalise cover images for maximum compatibility
    from PIL import Image
except ImportError:
    Image = None
 
 
LIGHT_COLORS = {
    "bg": "#F3F6FC",
    "card": "#FFFFFF",
    "text": "#1F2937",
    "muted": "#6B7280",
    "accent": "#4F7DF3",
    "accent_hover": "#3B6CE6",
    "secondary": "#EEF3FF",
    "secondary_hover": "#E1EBFF",
    "input_bg": "#F8FAFD",
    "input_border": "#DDE5F0",
    "preview_bg": "#F8FAFD",
    "placeholder": "#9AA7B8",
}
 
DARK_COLORS = {
    "bg": "#151A23",
    "card": "#1E2530",
    "text": "#E8EDF6",
    "muted": "#9AA7BC",
    "accent": "#6E9BFF",
    "accent_hover": "#5A8BF0",
    "secondary": "#263041",
    "secondary_hover": "#314059",
    "input_bg": "#141A24",
    "input_border": "#39455A",
    "preview_bg": "#141A24",
    "placeholder": "#6C7A90",
}
 
 
def get_tag_text(tags, frame_id):
    frame = tags.get(frame_id)
    if frame and getattr(frame, "text", None):
        return str(frame.text[0])
    return ""
 
 
def prepare_cover(path):
    """Return (image_bytes, mime) for embedding as cover art.
 
    With Pillow installed, the image is converted to a baseline JPEG no larger
    than 1000x1000, which Windows Explorer / Media Player display reliably.
    Without Pillow, the original bytes are used and the MIME type is detected
    from the file contents rather than trusting the file extension.
    """
    if Image is not None:
        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((1000, 1000))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90, progressive=False)
            return buf.getvalue(), "image/jpeg"
        except Exception:
            pass  # fall back to the raw file below
 
    with open(path, "rb") as image_file:
        data = image_file.read()
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png"
    return data, "image/jpeg"
 
 
class MP3TagEditor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MP3 Tag Editor")
        self.setFixedWidth(980)
        self.setObjectName("appRoot")
        self.setAttribute(Qt.WA_StyledBackground, True)
 
        self.mp3_path = ""
        self.cover_path = ""
        self.dark_mode = False
        self._theme_progress = 0.0
        self._theme_animation = None
 
        self._build_ui()
        self._apply_theme()
 
    def _get_theme_progress(self):
        return self._theme_progress
 
    def _set_theme_progress(self, value):
        self._theme_progress = float(value)
        self._apply_theme()
 
    # Qt animates this property directly; every frame updates the stylesheet.
    themeProgress = Property(float, _get_theme_progress, _set_theme_progress)
 
    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(28, 28, 28, 28)
        root_layout.setSpacing(0)
 
        header = QHBoxLayout()
        header.setSpacing(16)
        heading_box = QVBoxLayout()
        heading_box.setSpacing(4)
 
        title = QLabel("MP3 Tag Editor")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        heading_box.addWidget(title)
        header.addLayout(heading_box, 1)
 
        self.theme_button = QPushButton("Dark Mode")
        self.theme_button.setObjectName("secondary")
        self.theme_button.setFixedSize(130, 36)
        self.theme_button.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.theme_button.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_button, 0, Qt.AlignTop)
        root_layout.addLayout(header)
        root_layout.addSpacing(22)
 
        content = QHBoxLayout()
        content.setSpacing(18)
 
        left_card = QFrame()
        left_card.setObjectName("card")
        left_layout = QVBoxLayout(left_card)
        left_layout.setContentsMargins(28, 28, 28, 28)
        left_layout.setSpacing(0)
 
        details = QLabel("Track details")
        details.setFont(QFont("Segoe UI", 13, QFont.Bold))
        left_layout.addWidget(details)
        left_layout.addSpacing(18)
 
        mp3_row = QHBoxLayout()
        mp3_row.setSpacing(14)
        choose_mp3 = QPushButton("Choose MP3")
        choose_mp3.setObjectName("secondary")
        choose_mp3.setFixedSize(140, 40)
        choose_mp3.setFont(QFont("Segoe UI", 10, QFont.Bold))
        choose_mp3.clicked.connect(self.choose_mp3)
        self.mp3_label = QLabel("No file selected")
        self.mp3_label.setObjectName("muted")
        self.mp3_label.setFont(QFont("Segoe UI", 10))
        mp3_row.addWidget(choose_mp3)
        mp3_row.addWidget(self.mp3_label, 1)
        left_layout.addLayout(mp3_row)
        left_layout.addSpacing(20)
 
        self.entries = {}
        for label_text, key, placeholder in (
            ("Title", "title", "Enter song title"),
            ("Artist", "artist", "Enter artist name"),
            ("Album", "album", "Enter album name"),
        ):
            field_label = QLabel(label_text)
            field_label.setObjectName("muted")
            field_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
            left_layout.addWidget(field_label)
            left_layout.addSpacing(6)
 
            entry = QLineEdit()
            entry.setPlaceholderText(placeholder)
            entry.setFixedHeight(44)
            entry.setFont(QFont("Segoe UI", 10))
            left_layout.addWidget(entry)
            left_layout.addSpacing(16)
            self.entries[key] = entry
 
        image_row = QHBoxLayout()
        image_row.setSpacing(14)
        self.choose_image_btn = QPushButton("Choose Image")
        self.choose_image_btn.setObjectName("secondary")
        self.choose_image_btn.setFixedSize(140, 40)
        self.choose_image_btn.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.choose_image_btn.setEnabled(False)
        self.choose_image_btn.clicked.connect(self.choose_image)
        self.cover_label = QLabel("Cover unchanged on save")
        self.cover_label.setObjectName("muted")
        self.cover_label.setFont(QFont("Segoe UI", 10))
        image_row.addWidget(self.choose_image_btn)
        image_row.addWidget(self.cover_label, 1)
        left_layout.addLayout(image_row)
 
        content.addWidget(left_card, 1)
 
        right_card = QFrame()
        right_card.setObjectName("card")
        right_card.setFixedWidth(320)
        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(28, 28, 28, 28)
        right_layout.setSpacing(0)
 
        cover_heading = QLabel("Cover art")
        cover_heading.setFont(QFont("Segoe UI", 13, QFont.Bold))
        right_layout.addWidget(cover_heading)
 
        cover_hint = QLabel("Preview the image before saving it to the MP3.")
        cover_hint.setObjectName("muted")
        cover_hint.setFont(QFont("Segoe UI", 10))
        cover_hint.setWordWrap(True)
        right_layout.addSpacing(6)
        right_layout.addWidget(cover_hint)
        right_layout.addSpacing(18)
 
        self.preview_box = QLabel()
        self.preview_box.setObjectName("previewBox")
        self.preview_box.setFixedSize(260, 260)
        self.preview_box.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.preview_box, 0, Qt.AlignHCenter)
 
        self.preview_hint = QLabel(
            "Existing cover art will appear here when you load an MP3."
        )
        self.preview_hint.setObjectName("muted")
        self.preview_hint.setFont(QFont("Segoe UI", 9))
        self.preview_hint.setWordWrap(True)
        right_layout.addSpacing(14)
        right_layout.addWidget(self.preview_hint)
 
        content.addWidget(right_card, 0)
        root_layout.addLayout(content)
        root_layout.addSpacing(22)
 
        bottom = QHBoxLayout()
        self.status_label = QLabel("Select an MP3 file to get started.")
        self.status_label.setObjectName("muted")
        self.status_label.setFont(QFont("Segoe UI", 9))
        save_button = QPushButton("Save Metadata")
        save_button.setObjectName("primary")
        save_button.setFixedSize(170, 44)
        save_button.setFont(QFont("Segoe UI", 10, QFont.Bold))
        save_button.clicked.connect(self.save)
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(save_button)
        root_layout.addLayout(bottom)
 
        self.set_preview(None)
        # Fit the window snugly around the content instead of leaving
        # empty space at the bottom of the cards.
        self.setFixedHeight(self.sizeHint().height())
 
    def _interpolated_colors(self):
        t = self._theme_progress
        colors = {}
        for key, light in LIGHT_COLORS.items():
            dark = DARK_COLORS[key]
            a = QColor(light)
            b = QColor(dark)
            blended = QColor(
                round(a.red() + (b.red() - a.red()) * t),
                round(a.green() + (b.green() - a.green()) * t),
                round(a.blue() + (b.blue() - a.blue()) * t),
            )
            colors[key] = blended.name()
        return colors
 
    def _apply_theme(self):
        c = self._interpolated_colors()
        self.setStyleSheet(
            f"""
            QWidget#appRoot {{ background-color: {c['bg']}; }}
            QLabel {{ color: {c['text']}; font-family: 'Segoe UI'; }}
            QLabel#muted {{ color: {c['muted']}; }}
            QFrame#card {{ background-color: {c['card']}; border-radius: 24px; }}
            QPushButton#primary {{
                background-color: {c['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 14px;
            }}
            QPushButton#primary:hover {{ background-color: {c['accent_hover']}; }}
            QPushButton#secondary {{
                background-color: {c['secondary']};
                color: {c['accent']};
                border: none;
                border-radius: 12px;
            }}
            QPushButton#secondary:hover {{ background-color: {c['secondary_hover']}; }}
            QPushButton#secondary:disabled {{
                background-color: {c['secondary']};
                color: {c['muted']};
            }}
            QLineEdit {{
                background-color: {c['input_bg']};
                border: 1px solid {c['input_border']};
                border-radius: 12px;
                color: {c['text']};
                padding: 0 12px;
                selection-background-color: {c['accent']};
            }}
            QLineEdit::placeholder {{ color: {c['placeholder']}; }}
            QLabel#previewBox {{
                background-color: {c['preview_bg']};
                color: {c['muted']};
                border-radius: 20px;
            }}
            """
        )
 
    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.theme_button.setText("Light Mode" if self.dark_mode else "Dark Mode")
 
        if self._theme_animation is not None:
            self._theme_animation.stop()
        animation = QPropertyAnimation(self, b"themeProgress", self)
        animation.setDuration(550)
        animation.setStartValue(self._theme_progress)
        animation.setEndValue(1.0 if self.dark_mode else 0.0)
        animation.setEasingCurve(QEasingCurve.InOutCubic)
        self._theme_animation = animation
        animation.start()
 
    def set_preview(self, image_source, hint=None):
        if hint is not None:
            self.preview_hint.setText(hint)
 
        if image_source is None:
            self.preview_box.setPixmap(QPixmap())
            self.preview_box.setText(
                "No cover art\n\nSelect an image\nto preview it here"
            )
            return
 
        try:
            if isinstance(image_source, (bytes, bytearray)):
                pixmap = QPixmap()
                if not pixmap.loadFromData(bytes(image_source)):
                    raise ValueError("could not decode image")
            else:
                pixmap = QPixmap(image_source)
            if pixmap.isNull():
                raise ValueError("could not load image")
            pixmap = pixmap.scaled(
                240, 240, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.preview_box.setPixmap(pixmap)
            self.preview_box.setText("")
        except Exception:
            self.preview_box.setPixmap(QPixmap())
            self.preview_box.setText("Could not load image")
 
    def choose_mp3(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select an MP3 file", "", "MP3 files (*.mp3);;All files (*.*)"
        )
        if not path:
            return
 
        self.mp3_path = path
        self.cover_path = ""
        self.choose_image_btn.setEnabled(True)
        self.mp3_label.setText(os.path.basename(path))
        self.cover_label.setText("Cover unchanged on save")
        self.load_tags()
        self.status_label.setText(f"Loaded: {os.path.basename(path)}")
 
    def load_tags(self):
        for entry in self.entries.values():
            entry.clear()
 
        self.set_preview(
            None, hint="Existing cover art will appear here when you load an MP3."
        )
 
        try:
            tags = ID3(self.mp3_path)
        except ID3NoHeaderError:
            return
 
        self.entries["title"].setText(get_tag_text(tags, "TIT2"))
        self.entries["artist"].setText(get_tag_text(tags, "TPE1"))
        self.entries["album"].setText(get_tag_text(tags, "TALB"))
 
        apics = tags.getall("APIC")
        if apics:
            self.set_preview(
                apics[0].data, hint="Showing cover art embedded in this MP3."
            )
 
    def choose_image(self):
        if not self.mp3_path:
            QMessageBox.critical(self, "No file selected", "Please choose an MP3 file first.")
            return
 
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a cover image",
            "",
            "Image files (*.jpg *.jpeg *.png);;All files (*.*)",
        )
        if not path:
            return
 
        self.cover_path = path
        self.cover_label.setText(os.path.basename(path))
        self.set_preview(path, hint="New cover selected. Click Save Metadata to embed it.")
        self.status_label.setText(f"Cover selected: {os.path.basename(path)}")
 
    def save(self):
        if not self.mp3_path:
            QMessageBox.critical(self, "No file selected", "Please choose an MP3 file first.")
            return
 
        try:
            try:
                tags = ID3(self.mp3_path)
            except ID3NoHeaderError:
                tags = ID3()
 
            # encoding=1 (UTF-16) is valid in ID3v2.3, which Windows reads reliably.
            tags["TIT2"] = TIT2(encoding=1, text=[self.entries["title"].text().strip()])
            tags["TPE1"] = TPE1(encoding=1, text=[self.entries["artist"].text().strip()])
            tags["TALB"] = TALB(encoding=1, text=[self.entries["album"].text().strip()])
 
            if self.cover_path:
                image_data, mime = prepare_cover(self.cover_path)
                tags.delall("APIC")
                tags.add(
                    APIC(
                        encoding=1,
                        mime=mime,
                        type=3,
                        desc="Cover",
                        data=image_data,
                    )
                )
 
            # Write ID3v2.3 (best Windows compatibility) and remove any stale ID3v1 tag.
            tags.update_to_v23()
            tags.save(self.mp3_path, v2_version=3, v1=0)
            self.status_label.setText("Metadata saved successfully.")
            QMessageBox.information(self, "Saved", "Metadata saved successfully.")
        except Exception as exc:
            self.status_label.setText("Save failed.")
            QMessageBox.critical(self, "Error", f"Failed to save metadata:\n{exc}")
 
 
if __name__ == "__main__":
    app = QApplication([])
    window = MP3TagEditor()
    window.show()
    app.exec()
 