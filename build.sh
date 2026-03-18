#!/bin/bash

# Build script for NeoTune - Creates standalone executable with librespot

set -e

echo "🔨 Building NeoTune Release..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running in CI (GitHub Actions)
if [ -n "$CI" ]; then
    echo "Running in CI environment"
    IS_CI=true
else
    IS_CI=false
fi

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect OS and architecture
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

print_status "Detected: $OS $ARCH"

# Map architecture names
if [ "$ARCH" = "x86_64" ]; then
    RUST_TARGET="x86_64-unknown-linux-gnu"
    if [ "$OS" = "darwin" ]; then
        RUST_TARGET="x86_64-apple-darwin"
    fi
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    RUST_TARGET="aarch64-unknown-linux-gnu"
    if [ "$OS" = "darwin" ]; then
        RUST_TARGET="aarch64-apple-darwin"
    fi
else
    print_error "Unsupported architecture: $ARCH"
    exit 1
fi

print_status "Target: $RUST_TARGET"

# Build librespot
print_status "Building librespot..."

cd librespot_src

# Check if cargo is available
if ! command -v cargo &> /dev/null; then
    print_error "Rust/Cargo not found. Please install Rust: https://rustup.rs"
    exit 1
fi

# Build with pulseaudio support on Linux, rodio on macOS
if [ "$OS" = "darwin" ]; then
    # macOS - use rodio which has better compatibility
    cargo build --release --no-default-features \
        --features "rodio-backend with-libmdns rustls-tls-webpki-roots"
else
    # Linux - use pulseaudio for better device/DAC support
    cargo build --release --no-default-features \
        --features "pulseaudio-backend with-libmdns rustls-tls-webpki-roots"
fi

cd ..

# Copy librespot binary
print_status "Copying librespot binary..."
LIBRESPOT_SRC="librespot_src/target/release/librespot"
if [ "$OS" = "msys" ] || [ "$OS" = "mingw" ] || [ "$OS" = "cygwin" ]; then
    LIBRESPOT_SRC="librespot_src/target/release/librespot.exe"
fi

if [ ! -f "$LIBRESPOT_SRC" ]; then
    print_error "librespot binary not found at $LIBRESPOT_SRC"
    exit 1
fi

cp "$LIBRESPOT_SRC" src/network/librespot
chmod +x src/network/librespot
print_status "librespot copied successfully"

# Check for virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "No virtual environment detected. Looking for venv..."
    if [ -d "./venv" ]; then
        print_status "Activating venv..."
        source ./venv/bin/activate
    elif [ -d "./.venv" ]; then
        print_status "Activating .venv..."
        source ./.venv/bin/activate
    else
        print_error "No virtual environment found. Please create one:"
        print_error "  python3 -m venv venv"
        print_error "  source venv/bin/activate"
        exit 1
    fi
fi

# Install Python dependencies
print_status "Installing Python dependencies..."
pip install -q pyinstaller || pip install --break-system-packages -q pyinstaller
pip install -q -e . || pip install --break-system-packages -q -e .

# Build with PyInstaller
print_status "Building standalone executable with PyInstaller..."
python -m PyInstaller neotune.spec --clean --noconfirm

# Create distribution directory
print_status "Creating distribution package..."
DIST_DIR="dist/neotune-$RUST_TARGET"
mkdir -p "$DIST_DIR"

# Copy files
if [ "$OS" = "darwin" ]; then
    # macOS - copy app bundle
    if [ -d "dist/NeoTune.app" ]; then
        cp -r "dist/NeoTune.app" "$DIST_DIR/"
    fi
    cp dist/neotune "$DIST_DIR/" 2>/dev/null || true
else
    # Linux/Windows
    cp dist/neotune "$DIST_DIR/" 2>/dev/null || cp dist/neotune.exe "$DIST_DIR/" 2>/dev/null || true
fi

# Create archive
print_status "Creating archive..."
cd dist
if [ "$OS" = "darwin" ] || [ "$OS" = "linux" ]; then
    tar -czf "neotune-$RUST_TARGET.tar.gz" "neotune-$RUST_TARGET"
    print_status "Created: neotune-$RUST_TARGET.tar.gz"
else
    zip -r "neotune-$RUST_TARGET.zip" "neotune-$RUST_TARGET"
    print_status "Created: neotune-$RUST_TARGET.zip"
fi

cd ..

print_status "✅ Build complete!"
echo ""
echo "Output:"
echo "  - dist/neotune-$RUST_TARGET/ (directory)"
echo "  - dist/neotune-$RUST_TARGET.tar.gz (archive)"
echo ""

# Show file sizes
if command -v du &> /dev/null; then
    echo "File sizes:"
    du -h "dist/neotune-$RUST_TARGET.tar.gz" 2>/dev/null || du -h "dist/neotune-$RUST_TARGET.zip" 2>/dev/null || true
fi
