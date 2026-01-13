# GovCA Approval Automation - Desktop GUI

A desktop application for automating GovCA approval processes with a modern graphical user interface.

## Features

- **4 Workflow Options**:
  1. Add User (Batch Approval) - Approve pending users in batch
  2. Revoke Certificate - One-by-one approval of revoke requests
  3. Assign User Group - Assign users to groups in a single domain
  4. ALL Domains - Automated group assignment across all domains

- **Modern GUI**: Built with CustomTkinter for a clean, modern look
- **Real-time Logging**: See automation progress in real-time
- **Progress Tracking**: Visual progress bar for long operations
- **Sleep Prevention**: Keeps computer awake during long operations
- **Cross-platform**: Works on Windows and macOS

## Prerequisites

1. **Firefox** browser installed with P12 certificate configured
2. **No Python knowledge required** - just download and run

## Installation

### macOS

1. Download `GovCAApproval.dmg`
2. Open the DMG file
3. Drag `GovCAApproval.app` to your Applications folder
4. **First run**: Right-click the app > "Open" (to bypass Gatekeeper)

### Windows

1. Download `GovCAApproval.exe`
2. Run the executable
3. If Windows Defender shows a warning, click "More info" > "Run anyway"

## Usage

1. Launch the application
2. Select a workflow by clicking one of the 4 buttons
3. Configure options (domain, comment, etc.)
4. Click **START** to begin automation
5. Monitor progress in the log output
6. Click **STOP** to cancel at any time

## Building from Source

### Requirements

- Python 3.8+
- pip

### Setup

```bash
cd govca-approval-gui
pip install -r requirements.txt
```

### Run in Development Mode

```bash
python -m src.main
```

### Build for macOS

```bash
./scripts/build_macos.sh
```

Output: `dist/GovCAApproval.dmg`

### Build for Windows

```batch
scripts\build_windows.bat
```

Output: `dist\GovCAApproval.exe`

## Project Structure

```
govca-approval-gui/
├── src/
│   ├── main.py          # Entry point
│   ├── app.py           # Main GUI application
│   ├── logging_handler.py
│   └── core/
│       ├── bot.py       # Automation logic
│       └── browser.py   # Firefox profile detection
├── specs/               # PyInstaller spec files
│   ├── macos/
│   └── windows/
├── scripts/             # Build scripts
│   ├── build_macos.sh
│   └── build_windows.bat
├── drivers/             # Geckodriver binaries (downloaded during build)
├── requirements.txt
└── README.md
```

## Troubleshooting

### Firefox not found
- Ensure Firefox is installed in the default location
- macOS: `/Applications/Firefox.app`
- Windows: `C:\Program Files\Mozilla Firefox\`

### Certificate authentication fails
- Ensure your P12 certificate is installed in Firefox
- The application uses your default Firefox profile

### geckodriver not found
- The build scripts automatically download geckodriver
- For development, install manually: `brew install geckodriver` (macOS) or download from GitHub

### Application won't start on macOS
- Right-click the app and select "Open" the first time
- This is required because the app is not signed

## License

Internal use only - GovCA automation tool.
