"""Manager view – icon-based lab report grid with colour-coded results."""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

from app.utils.constants import COLORS, FONTS, STATUS_LABELS
from app import database as db

# ── Icon dimensions ──────────────────────────────────────────────────────────
ICON_W   = 120
ICON_H   = 100
ICON_GAP = 30
ICON_PAD = 20   # canvas padding


class ManagerApp:
    """Main window for the Manager role – shows approved reports as icons."""

    def __init__(self, root: tk.Tk, user: dict):
        self.root = root
        self.user = user
        self._reports: list = []
        self._selected_id: int | None = None
        self._build()
        self._load_reports()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        self.root.title(
            f"Manager – {self.user['full_name']}  |  Lab Report Management"
        )
        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.attributes("-zoomed", True)
        self.root.configure(bg=COLORS["bg_main"])
        self._build_topbar()

        # Main horizontal split
        self._paned = tk.PanedWindow(self.root, orient="horizontal",
                                     sashwidth=6, bg=COLORS["border"])
        self._paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Left: icon canvas
        left = tk.Frame(self._paned, bg=COLORS["bg_main"])
        self._paned.add(left, minsize=400)
        self._build_icon_panel(left)

        # Right: detail panel
        right = tk.Frame(self._paned, bg=COLORS["bg_main"])
        self._paned.add(right, minsize=420)
        self.detail_panel = right
        self._show_placeholder(right)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=COLORS["bg_header"], height=50)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="⚗  Lab Report Management",
                 font=FONTS["subtitle"], bg=COLORS["bg_header"],
                 fg=COLORS["fg_header"]).pack(side="left", padx=16)

        # Filter combobox
        tk.Label(bar, text="Filter:", font=FONTS["small"],
                 bg=COLORS["bg_header"], fg=COLORS["text_muted"]).pack(
            side="right", padx=(0, 4))
        self._filter_var = tk.StringVar(value="All")
        filter_cb = ttk.Combobox(
            bar, textvariable=self._filter_var,
            values=["All", "Approved", "Audited", "Submitted", "Rejected"],
            state="readonly", width=12,
        )
        filter_cb.pack(side="right", padx=(0, 12), pady=8)
        filter_cb.bind("<<ComboboxSelected>>", lambda _e: self._load_reports())

        tk.Button(bar, text="⟳ Refresh", command=self._load_reports,
                  bg=COLORS["accent"], fg="white", font=FONTS["small"],
                  relief="flat", cursor="hand2").pack(side="right", padx=4)
        tk.Label(bar,
                 text=f"Logged in as: {self.user['full_name']}  (Manager)",
                 font=FONTS["small"], bg=COLORS["bg_header"],
                 fg=COLORS["text_muted"]).pack(side="right", padx=16)

    def _build_icon_panel(self, parent):
        hdr = tk.Frame(parent, bg=COLORS["accent"], padx=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Lab Reports", font=FONTS["heading"],
                 bg=COLORS["accent"], fg="white").pack(side="left", pady=6)

        # Search bar
        tk.Label(hdr, text="🔍", font=FONTS["body"],
                 bg=COLORS["accent"], fg="white").pack(side="right", padx=4)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *a: self._filter_icons())
        ttk.Entry(hdr, textvariable=self._search_var,
                  width=20).pack(side="right", padx=4, pady=6)

        # Canvas with scrollbar
        canvas_frame = tk.Frame(parent, bg=COLORS["bg_main"])
        canvas_frame.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(canvas_frame, orient="vertical")
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(canvas_frame, orient="horizontal")
        hsb.pack(side="bottom", fill="x")

        self.icon_canvas = tk.Canvas(
            canvas_frame, bg=COLORS["bg_main"],
            highlightthickness=0,
            yscrollcommand=vsb.set, xscrollcommand=hsb.set,
        )
        vsb.configure(command=self.icon_canvas.yview)
        hsb.configure(command=self.icon_canvas.xview)
        self.icon_canvas.pack(fill="both", expand=True)
        self.icon_canvas.bind("<Configure>", lambda e: self._draw_icons())
        self.icon_canvas.bind(
            "<MouseWheel>",
            lambda e: self.icon_canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

    # ------------------------------------------------------------------
    # Load / draw icons
    # ------------------------------------------------------------------

    def _load_reports(self):
        f = self._filter_var.get().lower()
        all_reports = db.get_all_reports()
        if f == "all":
            self._reports = all_reports
        else:
            self._reports = [r for r in all_reports if r["status"] == f]
        self._draw_icons()

    def _filter_icons(self):
        q = self._search_var.get().lower()
        f = self._filter_var.get().lower()
        all_reports = db.get_all_reports()
        if f != "all":
            all_reports = [r for r in all_reports if r["status"] == f]
        if q:
            all_reports = [r for r in all_reports
                           if q in (r["title"] or "").lower()
                           or q in (r.get("tech_name") or "").lower()
                           or q in (r.get("patient_name") or "").lower()]
        self._reports = all_reports
        self._draw_icons()

    def _draw_icons(self):
        c = self.icon_canvas
        c.delete("all")
        if not self._reports:
            c.create_text(
                c.winfo_width() // 2, 80,
                text="No reports to display.",
                font=FONTS["body"], fill=COLORS["text_muted"],
            )
            return

        cw = max(c.winfo_width(), 400)
        cols = max(1, (cw - ICON_PAD * 2) // (ICON_W + ICON_GAP))
        total_rows = (len(self._reports) + cols - 1) // cols

        for idx, report in enumerate(self._reports):
            col = idx % cols
            row = idx // cols
            x = ICON_PAD + col * (ICON_W + ICON_GAP)
            y = ICON_PAD + row * (ICON_H + ICON_GAP + 20)
            self._draw_single_icon(c, report, x, y)

        total_h = ICON_PAD + total_rows * (ICON_H + ICON_GAP + 20) + ICON_PAD
        c.configure(scrollregion=(0, 0, cw, total_h))

    def _draw_single_icon(self, c: tk.Canvas, report: dict,
                           x: int, y: int):
        rid   = report["id"]
        status = report["status"]
        sc = COLORS.get(status, COLORS["icon_bg"])
        tag  = f"icon_{rid}"
        sel  = (rid == self._selected_id)

        # Shadow
        c.create_rectangle(x + 4, y + 4, x + ICON_W + 4, y + ICON_H + 4,
                            fill="#cccccc", outline="", tags=tag)
        # Icon body
        body_color = COLORS["icon_selected"] if sel else "white"
        c.create_rectangle(x, y, x + ICON_W, y + ICON_H,
                           fill=body_color, outline=sc, width=2, tags=tag)
        # Top colour band
        c.create_rectangle(x, y, x + ICON_W, y + 22,
                           fill=sc, outline="", tags=tag)

        # Flask symbol (hand-drawn)
        mx = x + ICON_W // 2
        # Flask neck
        c.create_rectangle(mx - 8, y + 24, mx + 8, y + 44,
                           fill=sc, outline=sc, tags=tag)
        # Flask body (trapezoid)
        c.create_polygon(
            mx - 8,  y + 44,
            mx + 8,  y + 44,
            mx + 24, y + 82,
            mx - 24, y + 82,
            fill=sc, outline=sc, tags=tag,
        )
        # Bubbles
        for bx, by, br in [(mx - 10, y + 60, 4), (mx + 5, y + 68, 3)]:
            c.create_oval(bx - br, by - br, bx + br, by + br,
                          fill="white", outline="", tags=tag)

        # Attachment indicator
        attachments = db.get_attachments(rid)
        if attachments:
            c.create_text(x + ICON_W - 10, y + 10, text="📎",
                          font=("Helvetica", 9), fill="white", tags=tag)

        # Status badge bottom-right
        c.create_rectangle(x + ICON_W - 52, y + ICON_H - 16,
                           x + ICON_W - 2, y + ICON_H - 2,
                           fill=sc, outline="", tags=tag)
        c.create_text(x + ICON_W - 27, y + ICON_H - 9,
                      text=status.upper(), font=FONTS["tiny"],
                      fill="white", tags=tag)

        # Title below icon
        title = report["title"]
        if len(title) > 16:
            title = title[:14] + "…"
        c.create_text(x + ICON_W // 2, y + ICON_H + 10,
                      text=title, font=FONTS["icon_title"],
                      fill=COLORS["text_dark"], tags=tag,
                      width=ICON_W + 10)

        # Bind click
        c.tag_bind(tag, "<Button-1>",
                   lambda e, r=report: self._on_icon_click(r))
        c.tag_bind(tag, "<Enter>",
                   lambda e, t=tag, sc_=sc: c.itemconfig(t, ""))
        c.tag_bind(tag, "<Double-Button-1>",
                   lambda e, r=report: self._open_first_attachment(r))

    # ------------------------------------------------------------------
    # Icon click → detail panel
    # ------------------------------------------------------------------

    def _on_icon_click(self, report: dict):
        self._selected_id = report["id"]
        self._draw_icons()        # redraw to show selection
        self._show_detail(report["id"])

    def _show_placeholder(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        tk.Label(parent,
                 text="Click a lab report icon to view details.\n"
                      "Double-click to open the first attachment.",
                 font=FONTS["body"], bg=COLORS["bg_main"],
                 fg=COLORS["text_muted"], justify="center").pack(pady=80)

    def _show_detail(self, report_id: int):
        for w in self.detail_panel.winfo_children():
            w.destroy()

        details     = db.get_report_details(report_id)
        values      = db.get_report_values(report_id)
        attachments = db.get_attachments(report_id)

        # Scrollable canvas
        canvas = tk.Canvas(self.detail_panel, bg=COLORS["bg_main"],
                           highlightthickness=0)
        vsb = ttk.Scrollbar(self.detail_panel, orient="vertical",
                             command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        body = tk.Frame(canvas, bg=COLORS["bg_main"])
        win  = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: canvas.configure(
                      scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"),
        )

        # ── Report header ─────────────────────────────────────────────
        status = details["status"]
        sc = COLORS.get(status, COLORS["icon_bg"])
        hdr = tk.Frame(body, bg=sc, padx=12)
        hdr.pack(fill="x", padx=0, pady=0)
        tk.Label(hdr, text=f"⚗  {details['title']}",
                 font=FONTS["subtitle"], bg=sc, fg="white").pack(
            side="left", pady=8)
        tk.Label(hdr, text=status.upper(),
                 font=FONTS["small"], bg="white", fg=sc,
                 padx=8, pady=2).pack(side="right", padx=8, pady=10)

        # ── Meta ─────────────────────────────────────────────────────
        meta = tk.Frame(body, bg=COLORS["bg_panel"], padx=12, pady=8)
        meta.pack(fill="x", padx=8, pady=4)
        meta_data = [
            ("Patient",    details.get("patient_name") or "—"),
            ("Patient ID", details.get("patient_id")   or "—"),
            ("Sample ID",  details.get("sample_id")    or "—"),
            ("Technician", details.get("tech_name")    or "—"),
            ("Template",   details.get("template_name")or "—"),
            ("Date",       (details.get("created_at")  or "")[:10]),
            ("Audited by", details.get("auditor_name") or "—"),
        ]
        for i, (lbl, val) in enumerate(meta_data):
            r, col = divmod(i, 2)
            tk.Label(meta, text=f"{lbl}:", font=FONTS["small"],
                     bg=COLORS["bg_panel"], fg=COLORS["text_muted"],
                     anchor="e", width=12).grid(row=r, column=col*2,
                                                padx=4, pady=2, sticky="e")
            tk.Label(meta, text=val, font=FONTS["body"],
                     bg=COLORS["bg_panel"], fg=COLORS["text_dark"],
                     anchor="w").grid(row=r, column=col*2+1,
                                      padx=4, pady=2, sticky="w")

        # ── Audit notes ───────────────────────────────────────────────
        if details.get("audit_notes"):
            notes_f = tk.LabelFrame(body, text="Audit Notes",
                                     bg=COLORS["bg_panel"],
                                     font=FONTS["heading"], padx=8, pady=6)
            notes_f.pack(fill="x", padx=8, pady=4)
            tk.Label(notes_f, text=details["audit_notes"],
                     font=FONTS["body"], bg=COLORS["bg_panel"],
                     fg=COLORS["text_dark"], wraplength=380,
                     justify="left").pack(anchor="w")

        # ── Two-column test results ───────────────────────────────────
        results_frame = tk.LabelFrame(
            body, text="Test Results",
            bg=COLORS["bg_panel"], font=FONTS["heading"],
            padx=8, pady=8,
        )
        results_frame.pack(fill="x", padx=8, pady=4)
        self._render_two_column_results(results_frame, values)

        # ── Attachments ───────────────────────────────────────────────
        att_frame = tk.LabelFrame(
            body, text=f"Attachments  ({len(attachments)})",
            bg=COLORS["bg_panel"], font=FONTS["heading"],
            padx=8, pady=8,
        )
        att_frame.pack(fill="x", padx=8, pady=(4, 12))
        if not attachments:
            tk.Label(att_frame, text="No attachments.",
                     font=FONTS["small"], bg=COLORS["bg_panel"],
                     fg=COLORS["text_muted"]).pack(anchor="w")
        else:
            for att in attachments:
                r = tk.Frame(att_frame, bg=COLORS["highlight"], pady=2)
                r.pack(fill="x", pady=1)
                tk.Label(r, text="📄 " + att["filename"],
                         font=FONTS["small"], bg=COLORS["highlight"],
                         fg=COLORS["text_dark"]).pack(side="left", padx=8)
                tk.Button(
                    r, text="Open",
                    command=lambda a=att: _open_file(a["filepath"]),
                    bg=COLORS["accent"], fg="white", font=FONTS["tiny"],
                    relief="flat", cursor="hand2",
                ).pack(side="right", padx=6)

    # ------------------------------------------------------------------
    # Two-column results layout
    # ------------------------------------------------------------------

    def _render_two_column_results(self, parent, values: list):
        """Render test results in two columns:
        - Left column (60 %): variables WITH test status + colour-coded badge
        - Right column (40 %): informational variables WITHOUT test status
          (value spans both "value" and "status" sub-columns → merged look)
        """
        with_status    = [v for v in values if v["has_status"]]
        without_status = [v for v in values if not v["has_status"]]

        container = tk.Frame(parent, bg=COLORS["bg_panel"])
        container.pack(fill="x")
        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=2)

        # ── Column 1 header ───────────────────────────────────────────
        col1_hdr = tk.Frame(container, bg=COLORS["primary"])
        col1_hdr.grid(row=0, column=0, sticky="ew", padx=(0, 2), pady=(0, 4))
        tk.Label(col1_hdr, text="Test Results (PASS / FAIL)",
                 font=FONTS["small"], bg=COLORS["primary"],
                 fg="white").pack(pady=4, padx=6, anchor="w")

        # ── Column 2 header ───────────────────────────────────────────
        col2_hdr = tk.Frame(container, bg=COLORS["text_muted"])
        col2_hdr.grid(row=0, column=1, sticky="ew", padx=(2, 0), pady=(0, 4))
        tk.Label(col2_hdr, text="Informational Fields",
                 font=FONTS["small"], bg=COLORS["text_muted"],
                 fg="white").pack(pady=4, padx=6, anchor="w")

        # ── Column 1 rows ─────────────────────────────────────────────
        col1_body = tk.Frame(container, bg=COLORS["bg_panel"])
        col1_body.grid(row=1, column=0, sticky="nsew", padx=(0, 2))

        if not with_status:
            tk.Label(col1_body, text="No test values.",
                     font=FONTS["small"], bg=COLORS["bg_panel"],
                     fg=COLORS["text_muted"]).pack(anchor="w", padx=6)
        else:
            # Sub-header
            sh = tk.Frame(col1_body, bg=COLORS["highlight"])
            sh.pack(fill="x")
            for txt, w in [("Test", 18), ("Value", 10), ("Range", 14), ("Status", 8)]:
                tk.Label(sh, text=txt, font=FONTS["tiny"],
                         bg=COLORS["highlight"], fg=COLORS["text_muted"],
                         width=w, anchor="w").pack(side="left", padx=2, pady=2)

            for v in with_status:
                self._render_status_row(col1_body, v)

        # ── Column 2 rows ─────────────────────────────────────────────
        col2_body = tk.Frame(container, bg=COLORS["bg_panel"])
        col2_body.grid(row=1, column=1, sticky="nsew", padx=(2, 0))

        if not without_status:
            tk.Label(col2_body, text="No informational fields.",
                     font=FONTS["small"], bg=COLORS["bg_panel"],
                     fg=COLORS["text_muted"]).pack(anchor="w", padx=6)
        else:
            sh2 = tk.Frame(col2_body, bg=COLORS["highlight"])
            sh2.pack(fill="x")
            for txt, w in [("Field", 16), ("Value", 18)]:
                tk.Label(sh2, text=txt, font=FONTS["tiny"],
                         bg=COLORS["highlight"], fg=COLORS["text_muted"],
                         width=w, anchor="w").pack(side="left", padx=2, pady=2)

            for v in without_status:
                r = tk.Frame(col2_body, bg=COLORS["bg_panel"])
                r.pack(fill="x", pady=1)
                tk.Label(r, text=v["variable_name"],
                         font=FONTS["small"], bg=COLORS["bg_panel"],
                         fg=COLORS["text_dark"], width=16,
                         anchor="w").pack(side="left", padx=4)
                # Value spans full remaining width (merged look)
                tk.Label(r, text=v.get("value") or "—",
                         font=FONTS["body"], bg=COLORS["bg_panel"],
                         fg=COLORS["text_dark"],
                         anchor="w").pack(side="left", padx=4, fill="x",
                                          expand=True)

    def _render_status_row(self, parent, v: dict):
        status = v.get("test_status") or "pending"
        bg = {
            "pass":    COLORS["pass_bg"],
            "fail":    COLORS["fail_bg"],
            "pending": COLORS["pending_bg"],
        }.get(status, COLORS["bg_panel"])
        badge_bg = {
            "pass":    COLORS["pass"],
            "fail":    COLORS["fail"],
            "pending": COLORS["pending"],
        }.get(status, COLORS["text_muted"])

        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=1)

        # Left color bar
        tk.Frame(row, bg=badge_bg, width=4).pack(side="left", fill="y")
        tk.Label(row, text=v["variable_name"],
                 font=FONTS["small"], bg=bg, fg=COLORS["text_dark"],
                 width=18, anchor="w").pack(side="left", padx=2)
        tk.Label(row, text=v.get("value") or "—",
                 font=FONTS["body"], bg=bg, fg=COLORS["text_dark"],
                 width=10, anchor="w").pack(side="left", padx=2)
        tk.Label(row, text=v.get("normal_range") or "—",
                 font=FONTS["tiny"], bg=bg, fg=COLORS["text_muted"],
                 width=14, anchor="w").pack(side="left", padx=2)
        # Status badge
        tk.Label(row, text=status.upper(),
                 font=FONTS["tiny"], bg=badge_bg, fg="white",
                 padx=5, pady=1, width=8).pack(side="left", padx=4)

    # ------------------------------------------------------------------
    # Attachment opener
    # ------------------------------------------------------------------

    def _open_first_attachment(self, report: dict):
        attachments = db.get_attachments(report["id"])
        if attachments:
            _open_file(attachments[0]["filepath"])
        else:
            messagebox.showinfo("No attachments",
                                "This report has no attachments.")


# ──────────────────────────────────────────────────────────────────────────────
# Utility
# ──────────────────────────────────────────────────────────────────────────────

def _open_file(filepath: str):
    if not os.path.exists(filepath):
        messagebox.showerror("Not found", f"File not found:\n{filepath}")
        return
    if sys.platform.startswith("win"):
        try:
            os.startfile(filepath)  # type: ignore[attr-defined]
        except AttributeError:
            subprocess.Popen(["start", filepath], shell=True)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", filepath])
    else:
        subprocess.Popen(["xdg-open", filepath])
