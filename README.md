# PDF Gallery Auto-Update System

A lightweight tool that monitors PDF folders for changes and automatically extracts embedded images, generating a searchable HTML gallery.

Built for academic research workflows — originally designed to manage image libraries from large collections of research papers.

---

## Features

- **Smart extraction** — Uses PyMuPDF to correctly extract all embedded images (JPEG, PNG, etc.)
- **Incremental updates** — Only re-processes PDFs that have changed (MD5-based detection)
- **Searchable HTML gallery** — Filter by size, search by filename or PDF name, click to view full details
- **Multi-project support** — Manage multiple PDF folders via a single `projects.json` config
- **Windows Task Scheduler** — One-click setup for automatic daily updates

---

## Requirements

- Python 3.7+
- [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`)
- [Pillow](https://pillow.readthedocs.io/)

Install dependencies:

```bash
pip install PyMuPDF Pillow
```

---

## Quick Start

**1. Clone the repo**

```bash
git clone https://github.com/YOUR_USERNAME/pdf-gallery-auto-update.git
cd pdf-gallery-auto-update
```

**2. Configure your projects**

Copy the example config and edit it:

```bash
cp projects.example.json projects.json
```

Edit `projects.json`:

```json
[
  {
    "name": "My Research Project",
    "pdf_dir": "C:\\path\\to\\your\\pdf\\folder",
    "output_dir": "C:\\path\\to\\output"
  }
]
```

**3. Run**

```bash
python auto_update_galleries.py
```

Or on Windows, double-click `run.bat`.

---

## Output Structure

For each project, the following is generated inside `output_dir`:

```
output_dir/
├── extracted_images/          # All extracted images
└── image_analysis/
    ├── index_enhanced.html    # Searchable HTML gallery (open in browser)
    ├── image_metadata.json    # Image metadata
    ├── pdf_refs.json          # PDF reference list
    └── gallery_state.json     # Update state (MD5 hashes)
```

---

## Scheduled Updates (Windows)

Run as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File setup_task.ps1
```

Follow the prompts to choose update frequency (daily, weekly, etc.).

Manage the task later:

```powershell
# Check status
Get-ScheduledTask -TaskName "Update PDF Gallery"

# Run manually
Start-ScheduledTask -TaskName "Update PDF Gallery"

# Remove
Unregister-ScheduledTask -TaskName "Update PDF Gallery" -Confirm:$false
```

---

## Configuration Reference

`projects.json` is an array of project objects:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name shown in the HTML gallery title |
| `pdf_dir` | string | Path to the folder containing your PDF files |
| `output_dir` | string | Path where images and HTML will be written |

You can add as many projects as needed.

---

## How It Works

```
1. Read projects.json
2. For each project:
   a. Scan PDF folder, compute MD5 hash of each file
   b. Compare with saved state (gallery_state.json)
   c. If changes detected:
      - Extract all embedded images via PyMuPDF
      - Save images to extracted_images/
      - Generate index_enhanced.html with embedded metadata
      - Update gallery_state.json
   d. If no changes: skip (fast)
```

---

## Troubleshooting

**Gallery not updating**
→ Delete `output_dir/image_analysis/gallery_state.json` to force a full rebuild.

**Script fails to run**
→ Check Python is installed: `python --version`
→ Check dependencies: `pip install PyMuPDF Pillow`

**Scheduled task not running**
→ Re-run `setup_task.ps1` as Administrator.

---

## License

MIT License — see [LICENSE](LICENSE) for details.
