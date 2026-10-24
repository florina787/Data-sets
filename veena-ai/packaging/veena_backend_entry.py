"""PyInstaller entry point for the bundled backend executable."""

import multiprocessing

from backend.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # required on Windows for frozen apps
    main()
