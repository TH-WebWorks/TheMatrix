# TheMatrix

Fullscreen **Matrix** digital rain on your **4K TV**, with **Spotify** (now playing, album art, playback controls).

## Documentation

Full documentation is available at **[docs/index.md](docs/index.md)** (source) or build locally:

```bash
python3 -m pip install -r requirements-docs.txt
python3 -m mkdocs serve
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) to browse.

## Quick start

**macOS**

```bash
chmod +x start-matrix.sh
python3 -m pip install -r requirements.txt   # first time only
./start-matrix.sh
```

**Windows**

```bat
start-matrix.bat
```

**ESC** quits · **F1** settings · **F11** toggle fullscreen · **SPACE** play/pause · **← / →** prev/next track.

See the [documentation](docs/index.md) for panels, Spotify setup, display options, and development guides.
