import io
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from mutagen.id3 import APIC, ID3, TALB, TIT2, TPE1, ID3NoHeaderError
from PIL import Image


# Light, modern palette
COLORS = {
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
}


def pick_resample():
    # Pillow 10+ uses Image.Resampling.LANCZOS; older versions use Image.LANCZOS
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.BICUBIC)


def get_tag_text(tags, frame_id):
    frame = tags.get(frame_id)
    if frame and getattr(frame, "text", None):
        return str(frame.text[0])
    return ""


class MP3TagEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("MP3 Tag Editor")
        self.root.geometry("980x700")  # slightly taller to avoid clipping
        self.root.minsize(940, 660)
        self.root.resizable(False, False)
        self.root.configure(fg_color=COLORS["bg"])

        self.mp3_path = ""
        self.cover_path = ""  # newly selected image; empty means keep existing cover
        self.preview_image = None
        self.status_var = tk.StringVar(value="Select an MP3 file to get started.")

        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkFrame(self.root, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=28, pady=28)

        # Header
        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 22))

        ctk.CTkLabel(
            header,
            text="MP3 Tag Editor",
            font=ctk.CTkFont(family="Segoe UI", size=30, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Update song details and cover art with a simple, clean interface.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=COLORS["muted"],
        ).pack(anchor="w", pady=(4, 0))

        # Bottom bar: pack before content so it always keeps its space
        bottom = ctk.CTkFrame(container, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", pady=(22, 0))

        self.status_label = ctk.CTkLabel(
            bottom,
            textvariable=self.status_var,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["muted"],
        )
        self.status_label.pack(side="left")

        ctk.CTkButton(
            bottom,
            text="Save Metadata",
            command=self.save,
            width=170,
            height=44,
            corner_radius=14,
            border_width=0,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color="white",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
        ).pack(side="right")

        # Content area
        content = ctk.CTkFrame(container, fg_color="transparent")
        content.pack(fill="both", expand=True)

        # Left card: file + metadata
        left_card = ctk.CTkFrame(
            content,
            fg_color=COLORS["card"],
            corner_radius=24,
            border_width=0,
        )
        left_card.pack(side="left", fill="both", expand=True, padx=(0, 18))

        left_inner = ctk.CTkFrame(left_card, fg_color="transparent")
        left_inner.pack(fill="both", expand=True, padx=28, pady=28)

        ctk.CTkLabel(
            left_inner,
            text="Track details",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w", pady=(0, 18))

        # MP3 picker row
        mp3_row = ctk.CTkFrame(left_inner, fg_color="transparent")
        mp3_row.pack(fill="x", pady=(0, 20))

        ctk.CTkButton(
            mp3_row,
            text="Choose MP3",
            command=self.choose_mp3,
            width=140,
            height=40,
            corner_radius=12,
            border_width=0,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            text_color=COLORS["accent"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
        ).pack(side="left")

        self.mp3_label = ctk.CTkLabel(
            mp3_row,
            text="No file selected",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORS["muted"],
            anchor="w",
        )
        self.mp3_label.pack(side="left", padx=(14, 0), fill="x", expand=True)

        # Metadata fields
        self.entries = {}
        fields = [
            ("Title", "title", "Enter song title"),
            ("Artist", "artist", "Enter artist name"),
            ("Album", "album", "Enter album name"),
        ]
        for label, key, placeholder in fields:
            ctk.CTkLabel(
                left_inner,
                text=label,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                text_color=COLORS["muted"],
            ).pack(anchor="w", pady=(0, 6))

            entry = ctk.CTkEntry(
                left_inner,
                height=44,
                corner_radius=12,
                border_width=1,
                border_color=COLORS["input_border"],
                fg_color=COLORS["input_bg"],
                text_color=COLORS["text"],
                placeholder_text=placeholder,
                placeholder_text_color="#9AA7B8",
                font=ctk.CTkFont(family="Segoe UI", size=13),
            )
            entry.pack(fill="x", pady=(0, 16))
            self.entries[key] = entry

        # Image picker row
        image_row = ctk.CTkFrame(left_inner, fg_color="transparent")
        image_row.pack(fill="x", pady=(4, 0))

        self.choose_image_btn = ctk.CTkButton(
            image_row,
            text="Choose Image",
            command=self.choose_image,
            width=140,
            height=40,
            corner_radius=12,
            border_width=0,
            fg_color=COLORS["secondary"],
            hover_color=COLORS["secondary_hover"],
            text_color=COLORS["accent"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            state="disabled",  # disabled until an MP3 is selected
        )
        self.choose_image_btn.pack(side="left")

        self.cover_label = ctk.CTkLabel(
            image_row,
            text="Cover unchanged on save",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORS["muted"],
            anchor="w",
        )
        self.cover_label.pack(side="left", padx=(14, 0), fill="x", expand=True)

        # Right card: preview
        right_card = ctk.CTkFrame(
            content,
            width=320,
            fg_color=COLORS["card"],
            corner_radius=24,
            border_width=0,
        )
        right_card.pack(side="right", fill="y")
        right_card.pack_propagate(False)

        right_inner = ctk.CTkFrame(right_card, fg_color="transparent")
        right_inner.pack(fill="both", expand=True, padx=28, pady=28)

        ctk.CTkLabel(
            right_inner,
            text="Cover art",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=COLORS["text"],
        ).pack(anchor="w")

        ctk.CTkLabel(
            right_inner,
            text="Preview the image before saving it to the MP3.",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORS["muted"],
            wraplength=250,
            justify="left",
        ).pack(anchor="w", pady=(6, 18))

        self.preview_box = ctk.CTkFrame(
            right_inner,
            width=260,
            height=260,
            corner_radius=20,
            fg_color=COLORS["preview_bg"],
            border_width=0,
        )
        self.preview_box.pack()
        self.preview_box.pack_propagate(False)

        self.preview_label = ctk.CTkLabel(
            self.preview_box,
            text="No cover art\n\nSelect an image\nto preview it here",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=COLORS["muted"],
            justify="center",
        )
        self.preview_label.place(relx=0.5, rely=0.5, anchor="center")

        self.preview_hint = ctk.CTkLabel(
            right_inner,
            text="Existing cover art will appear here when you load an MP3.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["muted"],
            wraplength=250,
            justify="left",
        )
        self.preview_hint.pack(anchor="w", pady=(14, 0))

    def set_preview(self, image_source, hint=None):
        """Display an image in the preview box. image_source: path, bytes, or None."""
        if hint is not None:
            self.preview_hint.configure(text=hint)

        if image_source is None:
            self.preview_image = None
            self.preview_label.configure(
                image=None,
                text="No cover art\n\nSelect an image\nto preview it here",
            )
            return

        try:
            if isinstance(image_source, (bytes, bytearray)):
                img = Image.open(io.BytesIO(image_source))
            else:
                img = Image.open(image_source)

            img = img.copy()
            # Fit within the preview area while preserving aspect ratio
            max_w, max_h = 240, 240
            img.thumbnail((max_w, max_h), pick_resample())
            w, h = img.size

            self.preview_image = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
            self.preview_label.configure(image=self.preview_image, text="")
        except Exception:
            self.preview_image = None
            self.preview_label.configure(image=None, text="Could not load image")

    def choose_mp3(self):
        path = filedialog.askopenfilename(
            title="Select an MP3 file",
            filetypes=[("MP3 files", "*.mp3"), ("All files", "*.*")],
        )
        if not path:
            return

        self.mp3_path = path
        self.cover_path = ""  # clear any previously selected new cover
        self.choose_image_btn.configure(state="normal")

        self.mp3_label.configure(text=os.path.basename(path), text_color=COLORS["text"])
        self.cover_label.configure(text="Cover unchanged on save", text_color=COLORS["muted"])
        self.load_tags()
        self.status_var.set(f"Loaded: {os.path.basename(path)}")

    def load_tags(self):
        for entry in self.entries.values():
            entry.delete(0, "end")

        self.set_preview(None, hint="Existing cover art will appear here when you load an MP3.")

        try:
            tags = ID3(self.mp3_path)
        except ID3NoHeaderError:
            return

        self.entries["title"].insert(0, get_tag_text(tags, "TIT2"))
        self.entries["artist"].insert(0, get_tag_text(tags, "TPE1"))
        self.entries["album"].insert(0, get_tag_text(tags, "TALB"))

        apics = tags.getall("APIC")
        if apics:
            self.set_preview(apics[0].data, hint="Showing cover art embedded in this MP3.")

    def choose_image(self):
        if not self.mp3_path:
            messagebox.showerror("No file selected", "Please choose an MP3 file first.")
            return

        path = filedialog.askopenfilename(
            title="Select a cover image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png"), ("All files", "*.*")],
        )
        if not path:
            return

        self.cover_path = path
        self.cover_label.configure(text=os.path.basename(path), text_color=COLORS["text"])
        self.set_preview(path, hint="New cover selected. Click Save Metadata to embed it.")
        self.status_var.set(f"Cover selected: {os.path.basename(path)}")

    def save(self):
        if not self.mp3_path:
            messagebox.showerror("No file selected", "Please choose an MP3 file first.")
            return

        try:
            try:
                tags = ID3(self.mp3_path)
            except ID3NoHeaderError:
                tags = ID3()

            tags["TIT2"] = TIT2(encoding=3, text=[self.entries["title"].get().strip()])
            tags["TPE1"] = TPE1(encoding=3, text=[self.entries["artist"].get().strip()])
            tags["TALB"] = TALB(encoding=3, text=[self.entries["album"].get().strip()])

            # Only embed a new cover if the user selected one
            if self.cover_path:
                ext = os.path.splitext(self.cover_path)[1].lower()
                mime = "image/png" if ext == ".png" else "image/jpeg"
                with open(self.cover_path, "rb") as img_file:
                    image_data = img_file.read()

                tags.delall("APIC")
                tags.add(
                    APIC(
                        encoding=3,  # UTF-8
                        mime=mime,
                        type=3,      # front cover
                        desc="Cover",
                        data=image_data,
                    )
                )

            tags.save(self.mp3_path)
            self.status_var.set("Metadata saved successfully.")
            messagebox.showinfo("Saved", "Metadata saved successfully.")

        except Exception as e:
            self.status_var.set("Save failed.")
            messagebox.showerror("Error", f"Failed to save metadata:\n{e}")


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    MP3TagEditor(root)
    root.mainloop()