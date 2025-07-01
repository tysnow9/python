# Camera Project

A modular application for controlling an IS8502C camera with a Tkinter GUI.

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Run: `python src/main.py`
# IS8502C Camera Control

A modular Python application for controlling an IS8502C camera using Telnet for commands and FTP for image retrieval, with a Tkinter-based GUI for live streaming, native command input, and exposure/gain adjustments.

## Project Structure

- `src/`: Source code
  - `camera/`: Camera control logic (`CameraController`)
  - `gui/`: Tkinter GUI (`CameraGUI`)
  - `processing/`: Image handling (`ImageProcessor`)
  - `config/`: Settings (`settings.py`)
  - `main.py`: Application entry point
- `data/`: Storage for images (`images/`) and logs (`logs/`)
- `requirements.txt`: Python dependencies

## Setup

1. **Clone or set up the project**:
   - Ensure the project structure is in place (use `setup_project.py` if needed).
   - Place a `placeholder.bmp` in `data/` for initial GUI display.

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt