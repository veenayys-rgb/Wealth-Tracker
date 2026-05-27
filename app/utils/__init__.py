# Bump __version__ in the same commit whenever you add new exports to any
# utils module (db.py, fmt.py, sidebar.py, config.py).
# Streamlit Cloud detects this file changing and does a full cold restart,
# clearing the Python module cache so new imports are always found.
__version__ = "1.5"
