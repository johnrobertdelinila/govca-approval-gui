#!/bin/bash
# Build script for macOS
# Creates GovCAApproval.app and GovCAApproval.dmg

set -e

echo "========================================"
echo " Building GovCA Approval for macOS"
echo "========================================"

# Navigate to project root (scripts/ -> project root)
cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "Project root: $PROJECT_ROOT"

# Create virtual environment if not exists
if [ ! -d "build_env" ]; then
    echo "Creating virtual environment..."
    python3 -m venv build_env
fi

# Activate virtual environment
source build_env/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt
pip3 install pyinstaller

# Create drivers directory if not exists
mkdir -p drivers

# Download BOTH geckodriver versions for Universal Binary support
# ARM64 (Apple Silicon)
if [ ! -f "drivers/geckodriver-macos-arm64" ]; then
    echo "Downloading geckodriver (ARM64 - Apple Silicon)..."
    curl -L -o geckodriver-arm64.tar.gz "https://github.com/mozilla/geckodriver/releases/download/v0.34.0/geckodriver-v0.34.0-macos-aarch64.tar.gz"
    tar xzf geckodriver-arm64.tar.gz
    mv geckodriver drivers/geckodriver-macos-arm64
    chmod +x drivers/geckodriver-macos-arm64
    rm geckodriver-arm64.tar.gz
    echo "Geckodriver ARM64 downloaded"
else
    echo "Geckodriver ARM64 already present"
fi

# Intel x64
if [ ! -f "drivers/geckodriver-macos-x64" ]; then
    echo "Downloading geckodriver (Intel x64)..."
    curl -L -o geckodriver-x64.tar.gz "https://github.com/mozilla/geckodriver/releases/download/v0.34.0/geckodriver-v0.34.0-macos.tar.gz"
    tar xzf geckodriver-x64.tar.gz
    mv geckodriver drivers/geckodriver-macos-x64
    chmod +x drivers/geckodriver-macos-x64
    rm geckodriver-x64.tar.gz
    echo "Geckodriver Intel x64 downloaded"
else
    echo "Geckodriver Intel x64 already present"
fi

# Clean previous PyInstaller builds (but NOT our spec files)
echo "Cleaning previous builds..."
rm -rf build dist

# Run PyInstaller with spec file from specs/ directory
echo "Running PyInstaller..."
pyinstaller specs/macos/govca_approval.spec --clean --noconfirm

# Check if app was created
if [ -d "dist/GovCAApproval.app" ]; then
    echo "App bundle created successfully!"

    # Create DMG
    echo "Creating DMG..."
    rm -f dist/GovCAApproval.dmg

    hdiutil create \
        -volname "GovCA Approval Automation" \
        -srcfolder dist/GovCAApproval.app \
        -ov \
        -format UDZO \
        dist/GovCAApproval.dmg

    echo "========================================"
    echo " Build Complete!"
    echo "========================================"
    echo ""
    echo "Output files:"
    echo "  - dist/GovCAApproval.app"
    echo "  - dist/GovCAApproval.dmg"
    echo ""
    echo "To install:"
    echo "  1. Open dist/GovCAApproval.dmg"
    echo "  2. Drag GovCAApproval to Applications"
    echo "  3. First run: Right-click > Open (to bypass Gatekeeper)"
    echo ""
else
    echo "ERROR: App bundle was not created!"
    exit 1
fi

deactivate
echo "Done!"
