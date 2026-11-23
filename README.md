# MP3 Tag Editor

A simple desktop app to edit an MP3's cover art, title, artist, and album.

## Features

- Edit song title, artist, and album
- View the cover art already embedded in the MP3
- Choose a new cover image (JPG or PNG) and preview it before saving
- Light and dark mode with a smooth transition

## Requirements

- Python 3
- Dependencies:

      pip install PySide6 mutagen

## Usage

Run the script:

    python mp3_tag_editor.py

1. Click **Choose MP3** and select a file. Its current tags and cover art load automatically.
2. Edit the title, artist, and album.
3. (Optional) Click **Choose Image** to replace the cover art. If you skip this, the existing cover is left unchanged.
4. Click **Save Metadata**.

Note: changes are written directly to the MP3 file, so keep a backup of anything important.
