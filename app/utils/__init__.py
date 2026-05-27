# Bump __version__ whenever you add new exports to any utils module.
# The eviction loop below ensures Streamlit Cloud's warm-reload always
# picks up the latest code — no manual cache-busting needed.
__version__ = "1.4"

import sys as _sys
_pkg = __name__   # "utils"
for _k in [k for k in _sys.modules if k == _pkg or k.startswith(_pkg + ".")]:
    _sys.modules.pop(_k, None)
