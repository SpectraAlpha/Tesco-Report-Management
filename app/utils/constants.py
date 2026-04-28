"""Application-wide constants: colours, fonts, role labels."""

COLORS = {
    # Test result status
    "pass": "#2ecc71",
    "pass_bg": "#d5f5e3",
    "pass_text": "#1a7a42",
    "fail": "#e74c3c",
    "fail_bg": "#fadbd8",
    "fail_text": "#922b21",
    "pending": "#f39c12",
    "pending_bg": "#fef9e7",
    "pending_text": "#7d6608",
    # Report workflow status
    "draft": "#95a5a6",
    "submitted": "#f39c12",
    "audited": "#3498db",
    "approved": "#2ecc71",
    "rejected": "#e74c3c",
    # UI palette
    "primary": "#2c3e50",
    "primary_light": "#34495e",
    "accent": "#2980b9",
    "accent_hover": "#1f618d",
    "bg_main": "#ecf0f1",
    "bg_panel": "#ffffff",
    "bg_header": "#2c3e50",
    "fg_header": "#ecf0f1",
    "border": "#bdc3c7",
    "text_dark": "#2c3e50",
    "text_muted": "#7f8c8d",
    "highlight": "#eaf2ff",
    # Report icon colours
    "icon_bg": "#2980b9",
    "icon_hover": "#1a5276",
    "icon_text": "#ffffff",
    "icon_border": "#1a5276",
    "icon_selected": "#f0c040",
}

FONTS = {
    "title": ("Helvetica", 15, "bold"),
    "subtitle": ("Helvetica", 12, "bold"),
    "heading": ("Helvetica", 11, "bold"),
    "body": ("Helvetica", 10),
    "small": ("Helvetica", 9),
    "tiny": ("Helvetica", 8),
    "icon_title": ("Helvetica", 9, "bold"),
    "mono": ("Courier", 10),
}

ROLES = {
    "technician": "Lab Technician",
    "lab_manager": "Lab Manager",
    "manager": "Manager",
}

STATUS_LABELS = {
    "draft": "Draft",
    "submitted": "Submitted",
    "audited": "Audited",
    "approved": "Approved",
    "rejected": "Rejected",
}

# Convenience aliases that point to the canonical COLORS dictionary values.
PASS_COLOR = COLORS["pass"]
FAIL_COLOR = COLORS["fail"]
NA_COLOR   = COLORS["draft"]
