#!/usr/bin/env python3
"""
Script to launch auto-py-to-exe utility.
This tool provides a GUI to convert Python scripts to executable files using PyInstaller.
"""

import subprocess
import sys


def main():
    """
    Main function to launch auto-py-to-exe.
    """
    try:
        # Try to launch auto-py-to-exe directly
        subprocess.run([sys.executable, "-m", "auto_py_to_exe"], check=True)
    except subprocess.CalledProcessError:
        print("Error: Failed to launch auto-py-to-exe.")
        print("Please make sure it is installed by running: pip install auto-py-to-exe")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: auto-py-to-exe not found.")
        print("Please install it first by running: pip install auto-py-to-exe")
        sys.exit(1)


if __name__ == "__main__":
    main()