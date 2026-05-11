# Elixir Macro - Cross-Platform Setup

## macOS Setup

To run Elixir Macro on macOS, follow these steps:

### 1. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 2. Install Tesseract OCR
```bash
brew install tesseract
```

### 3. Install Additional Libraries
```bash
pip install mss ttkbootstrap
```

### 4. Run the Application
```bash
python app.pyw
```

## Windows Setup

The application should work out of the box on Windows. For OCR optimization, the app automatically reduces image size on Windows to improve performance.

## OCR Functionality

The app includes OCR capabilities for reading text from the screen. To use OCR:

1. Configure OCR regions in the settings modals
2. The app will automatically detect and read text from specified screen areas
3. On Windows, OCR is optimized for performance by downscaling images
4. On macOS, ensure Tesseract is installed for OCR to work

## Troubleshooting

- If OCR doesn't work, check that Tesseract is installed
- On macOS, some Windows-specific features may not be available
- Screen capture uses MSS for cross-platform compatibility