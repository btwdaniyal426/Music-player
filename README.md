# Music Player

A modern, feature-rich music player built with Python and tkinter.

## Features

- 🎵 Play, pause, stop, next, and previous controls
- 📁 Add individual files or entire folders to playlist
- 🔊 Volume control slider
- 📊 Progress bar with time display
- 🎨 Modern dark-themed GUI
- 📋 Playlist management (add, remove, clear)
- 🏷️ Automatic metadata extraction (artist and title)
- 🔄 Auto-play next song when current song ends

## Supported Audio Formats

- MP3
- WAV
- OGG
- FLAC
- M4A

## Installation

1. Make sure you have Python 3.7+ installed

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the music player:
```bash
python music_player.py
```

### Controls

- **Add File**: Add a single audio file to the playlist
- **Add Folder**: Add all audio files from a folder to the playlist
- **Remove Selected**: Remove the selected song from the playlist
- **Clear Playlist**: Clear all songs from the playlist
- **Play/Pause**: Toggle playback
- **Stop**: Stop playback
- **Previous/Next**: Navigate through the playlist
- **Volume Slider**: Adjust playback volume
- **Double-click**: Double-click any song in the playlist to play it

## Requirements

- Python 3.7+
- pygame 2.5.2+
- mutagen 1.47.0+

## Troubleshooting

### MP3 Playback Issues

If you encounter errors playing MP3 files:

1. **Windows**: Pygame requires system codecs to play MP3 files. Make sure your system has MP3 codecs installed (usually included with Windows Media Player).

2. **Alternative Formats**: If MP3 doesn't work, try:
   - WAV files (always supported)
   - OGG files (better support)
   - Convert MP3 to WAV/OGG using a converter

3. **Error Messages**: The player now provides detailed error messages. Check the error dialog for specific information about what went wrong.

### Common Issues

- **"Could not load audio file"**: The file format may not be supported, or the file might be corrupted
- **"File not found"**: The file may have been moved or deleted
- **No sound**: Check your system volume and ensure audio drivers are installed

## License

Free to use and modify.
