"""Entry point used by PyInstaller to build the standalone .exe.

For normal development, run the app with `py -m app.main` instead -- this
file exists only so PyInstaller has a plain script to analyze and bundle.
"""

from app.main import main

if __name__ == "__main__":
    main()
