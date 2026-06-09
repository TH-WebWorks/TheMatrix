"""Launch the Matrix display."""

from icon_setup import apply_app_icon
from matrix_display import main

if __name__ == "__main__":
    apply_app_icon()
    raise SystemExit(main())
