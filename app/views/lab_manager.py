"""Lab Manager view – audit reports and build composite reports via drag-and-drop."""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from app.utils.constants import COLORS, FONTS, STATUS_LABELS
from app import database as db


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _status_badge(parent, status: str, **kwargs) -> tk.Label:
    color = COLORS.get(status, COLORS["text_muted"])
    return tk.Label(
        parent,
        text=STATUS_LABELS.get(status, status).upper(),
        font=FONTS["tiny"],
        bg=color,
        fg="white",
        padx=6,
        pady=2,
        **kwargs,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Main application window
# ──────────────────────────────────────────────────────────────────────────────

class LabManagerApp:
    """Main window for the Lab Manager role."""

    def __init__(self, root: tk.Tk, user: dict):
        self.root = root
        self.user = user
        self._build()
        self._load_pending()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        self.root.title(
            f"Lab Manager – {self.user['full_name']}  |  Lab Report Management"
        )
        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.attributes("-zoomed", True)
        self.root.configure(bg=COLORS["bg_main"])
        self._build_topbar()

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Tab 1 – Pending review
        self.pending_tab = tk.Frame(nb, bg=COLORS["bg_main"])
        nb.add(self.pending_tab, text="  ⏳ Pending Review  ")
        self._build_pending_tab(self.pending_tab)

        # Tab 2 – All reports
        self.all_tab = tk.Frame(nb, bg=COLORS["bg_main"])
        nb.add(self.all_tab, text="  📋 All Reports  ")
        self._build_all_tab(self.all_tab)

        # Tab 3 – Report Builder
        self.builder_tab = tk.Frame(nb, bg=COLORS["bg_main"])
        nb.add(self.builder_tab, text="  🔨 Report Builder  ")
        self._build_builder_tab(self.builder_tab)

        nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=COLORS["bg_header"], height=50)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="⚗  Lab Report Management", font=FONTS["subtitle"],
                 bg=COLORS["bg_header"], fg=COLORS["fg_header"]).pack(side="left", padx=16)
        tk.Label(bar,
                 text=f"Logged in as: {self.user['full_name']}  (Lab Manager)",
                 font=FONTS["small"], bg=COLORS["bg_header"],
                 fg=COLORS["text_muted"]).pack(side="right", padx=16)

    # ──────────────────────────────────────────────────────────────────
    # Tab 1 – Pending Review
    # ──────────────────────────────────────────────────────────────────

    def _build_pending_tab(self, parent):
        paned = tk.PanedWindow(parent, orient="horizontal",
                               sashwidth=6, bg=COLORS["border"])
        paned.pack(fill="both", expand=True, padx=8, pady=8)

        # Left list
        left = tk.Frame(paned, bg=COLORS["bg_panel"])
        paned.add(left, minsize=260)
        self._build_pending_list(left)

        # Right detail / audit panel
        right = tk.Frame(paned, bg=COLORS["bg_main"])
        paned.add(right, minsize=500)
        self.audit_panel = right
        self._show_audit_placeholder(right)

    def _build_pending_list(self, parent):
        hdr = tk.Frame(parent, bg=COLORS["submitted"], padx=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Awaiting Review", font=FONTS["heading"],
                 bg=COLORS["submitted"], fg="white").pack(side="left", pady=8)
        tk.Button(hdr, text="⟳", command=self._load_pending,
                  bg=COLORS["primary"], fg="white", font=FONTS["body"],
                  relief="flat", cursor="hand2").pack(side="right", padx=4, pady=6)

        cols = ("title", "tech", "date")
        self.pending_tree = ttk.Treeview(parent, columns=cols,
                                         show="headings", height=30)
        self.pending_tree.heading("title", text="Report Title")
        self.pending_tree.heading("tech",  text="Technician")
        self.pending_tree.heading("date",  text="Submitted")
        self.pending_tree.column("title", width=140)
        self.pending_tree.column("tech",  width=100)
        self.pending_tree.column("date",  width=80)
        sb = ttk.Scrollbar(parent, orient="vertical",
                           command=self.pending_tree.yview)
        self.pending_tree.configure(yscrollcommand=sb.set)
        self.pending_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.pending_tree.bind("<<TreeviewSelect>>", self._on_pending_select)

    def _show_audit_placeholder(self, parent):
        for w in parent.winfo_children():
            w.destroy()
        tk.Label(parent, text="Select a report on the left to review it.",
                 font=FONTS["body"], bg=COLORS["bg_main"],
                 fg=COLORS["text_muted"]).pack(pady=60)

    def _load_pending(self):
        self.pending_tree.delete(*self.pending_tree.get_children())
        for r in db.get_submitted_reports():
            date = (r.get("submitted_at") or r["created_at"] or "")[:10]
            self.pending_tree.insert(
                "", "end", iid=str(r["id"]),
                values=(r["title"], r.get("tech_name", ""), date),
            )

    def _on_pending_select(self, _e=None):
        sel = self.pending_tree.selection()
        if not sel:
            return
        self._show_audit_panel(int(sel[0]))

    def _show_audit_panel(self, report_id: int):
        for w in self.audit_panel.winfo_children():
            w.destroy()

        details = db.get_report_details(report_id)
        values  = db.get_report_values(report_id)
        attachments = db.get_attachments(report_id)

        # Canvas + scrollbar
        canvas = tk.Canvas(self.audit_panel, bg=COLORS["bg_main"],
                           highlightthickness=0)
        vsb = ttk.Scrollbar(self.audit_panel, orient="vertical",
                             command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        body = tk.Frame(canvas, bg=COLORS["bg_main"])
        win  = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))

        # Header
        hdr = tk.Frame(body, bg=COLORS["accent"], padx=12)
        hdr.pack(fill="x", padx=12, pady=(12, 0))
        tk.Label(hdr, text=f"📋  {details['title']}", font=FONTS["subtitle"],
                 bg=COLORS["accent"], fg="white").pack(side="left", pady=6)
        _status_badge(hdr, details["status"]).pack(side="right", padx=4, pady=8)

        # Meta
        meta = tk.Frame(body, bg=COLORS["bg_panel"], padx=12, pady=8)
        meta.pack(fill="x", padx=12, pady=4)
        meta_fields = [
            ("Technician",   details.get("tech_name", "")),
            ("Patient",      details.get("patient_name", "")),
            ("Patient ID",   details.get("patient_id", "")),
            ("Sample ID",    details.get("sample_id", "")),
            ("Template",     details.get("template_name", "")),
            ("Created",      (details.get("created_at") or "")[:10]),
            ("Submitted",    (details.get("submitted_at") or "")[:10]),
        ]
        for i, (lbl, val) in enumerate(meta_fields):
            r, c = divmod(i, 2)
            tk.Label(meta, text=f"{lbl}:", font=FONTS["small"],
                     bg=COLORS["bg_panel"], fg=COLORS["text_muted"],
                     anchor="e", width=12).grid(row=r, column=c*2, padx=4,
                                                pady=2, sticky="e")
            tk.Label(meta, text=val or "—", font=FONTS["body"],
                     bg=COLORS["bg_panel"], fg=COLORS["text_dark"],
                     anchor="w").grid(row=r, column=c*2+1, padx=4,
                                      pady=2, sticky="w")

        # Test results table
        tbl_frame = tk.LabelFrame(body, text="Test Results",
                                   bg=COLORS["bg_panel"], font=FONTS["heading"],
                                   padx=8, pady=8)
        tbl_frame.pack(fill="x", padx=12, pady=4)
        self._render_results_table(tbl_frame, values)

        # Attachments
        if attachments:
            att_frame = tk.LabelFrame(body, text="Attachments",
                                       bg=COLORS["bg_panel"], font=FONTS["heading"],
                                       padx=8, pady=8)
            att_frame.pack(fill="x", padx=12, pady=4)
            for att in attachments:
                r = tk.Frame(att_frame, bg=COLORS["highlight"])
                r.pack(fill="x", pady=1)
                tk.Label(r, text="📄 " + att["filename"], font=FONTS["small"],
                         bg=COLORS["highlight"],
                         fg=COLORS["text_dark"]).pack(side="left", padx=8, pady=3)
                tk.Button(r, text="Open",
                          command=lambda a=att: _open_file(a["filepath"]),
                          bg=COLORS["accent"], fg="white", font=FONTS["tiny"],
                          relief="flat", cursor="hand2").pack(side="right", padx=4)

        # Audit notes
        notes_frame = tk.LabelFrame(body, text="Audit Notes",
                                     bg=COLORS["bg_panel"], font=FONTS["heading"],
                                     padx=8, pady=8)
        notes_frame.pack(fill="x", padx=12, pady=4)
        self._notes_text = tk.Text(notes_frame, height=4, font=FONTS["body"],
                                   wrap="word")
        self._notes_text.pack(fill="x")
        if details.get("audit_notes"):
            self._notes_text.insert("1.0", details["audit_notes"])

        # Audit buttons
        btn_bar = tk.Frame(body, bg=COLORS["bg_main"])
        btn_bar.pack(fill="x", padx=12, pady=8)
        self._current_audit_id = report_id

        tk.Button(
            btn_bar, text="✅  Approve",
            command=lambda: self._audit("approved"),
            bg=COLORS["approved"], fg="white", font=FONTS["heading"],
            relief="flat", cursor="hand2", padx=12, pady=6,
        ).pack(side="left", padx=4)
        tk.Button(
            btn_bar, text="❌  Reject",
            command=lambda: self._audit("rejected"),
            bg=COLORS["rejected"], fg="white", font=FONTS["heading"],
            relief="flat", cursor="hand2", padx=12, pady=6,
        ).pack(side="left", padx=4)
        tk.Button(
            btn_bar, text="🔍  Audited (needs revision)",
            command=lambda: self._audit("audited"),
            bg=COLORS["audited"], fg="white", font=FONTS["heading"],
            relief="flat", cursor="hand2", padx=12, pady=6,
        ).pack(side="left", padx=4)

    def _render_results_table(self, parent, values: list):
        with_status    = [v for v in values if v["has_status"]]
        without_status = [v for v in values if not v["has_status"]]

        # Header
        hdr = tk.Frame(parent, bg=COLORS["primary"])
        hdr.pack(fill="x", pady=(0, 4))
        for col, w in [("Test", 22), ("Value", 12), ("Unit", 8),
                        ("Normal Range", 16), ("Status", 10)]:
            tk.Label(hdr, text=col, font=FONTS["small"], bg=COLORS["primary"],
                     fg="white", width=w, anchor="w",
                     ).pack(side="left", padx=3, pady=3)

        for v in with_status:
            self._render_result_row(parent, v)

        if without_status:
            sep = tk.Frame(parent, bg=COLORS["border"], height=1)
            sep.pack(fill="x", pady=6)
            tk.Label(parent, text="Informational Fields",
                     font=FONTS["small"], bg=COLORS["bg_panel"],
                     fg=COLORS["text_muted"]).pack(anchor="w")
            for v in without_status:
                r = tk.Frame(parent, bg=COLORS["bg_panel"])
                r.pack(fill="x", pady=1)
                tk.Label(r, text=v["variable_name"], font=FONTS["body"],
                         bg=COLORS["bg_panel"], width=22, anchor="w",
                         fg=COLORS["text_dark"]).pack(side="left", padx=6)
                tk.Label(r, text=v.get("value") or "—", font=FONTS["body"],
                         bg=COLORS["bg_panel"], width=30, anchor="w",
                         fg=COLORS["text_dark"]).pack(side="left", padx=4)

    def _render_result_row(self, parent, v: dict):
        status = v.get("test_status") or "pending"
        bg = {
            "pass":    COLORS["pass_bg"],
            "fail":    COLORS["fail_bg"],
            "pending": COLORS["pending_bg"],
        }.get(status, COLORS["bg_panel"])
        fg = {
            "pass":    COLORS["pass"],
            "fail":    COLORS["fail"],
            "pending": COLORS["pending"],
        }.get(status, COLORS["text_muted"])

        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=1)
        tk.Label(row, text=v["variable_name"], font=FONTS["body"],
                 bg=bg, width=22, anchor="w",
                 fg=COLORS["text_dark"]).pack(side="left", padx=6)
        tk.Label(row, text=v.get("value") or "—", font=FONTS["body"],
                 bg=bg, width=12, anchor="w",
                 fg=COLORS["text_dark"]).pack(side="left", padx=2)
        tk.Label(row, text=v.get("unit") or "", font=FONTS["small"],
                 bg=bg, width=8, anchor="w",
                 fg=COLORS["text_muted"]).pack(side="left")
        tk.Label(row, text=v.get("normal_range") or "—", font=FONTS["small"],
                 bg=bg, width=16, anchor="w",
                 fg=COLORS["text_muted"]).pack(side="left", padx=2)
        # Status badge
        tk.Label(row, text=status.upper(), font=FONTS["small"],
                 bg=fg, fg="white", width=10, anchor="center",
                 pady=1).pack(side="left", padx=4)

    def _audit(self, status: str):
        notes = self._notes_text.get("1.0", "end").strip()
        db.audit_report(self._current_audit_id, self.user["id"], status, notes)
        messagebox.showinfo("Audit saved",
                            f"Report marked as: {STATUS_LABELS[status]}")
        self._load_pending()
        self._show_audit_placeholder(self.audit_panel)

    # ──────────────────────────────────────────────────────────────────
    # Tab 2 – All Reports
    # ──────────────────────────────────────────────────────────────────

    def _build_all_tab(self, parent):
        hdr = tk.Frame(parent, bg=COLORS["primary"], padx=10)
        hdr.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(hdr, text="All Reports", font=FONTS["heading"],
                 bg=COLORS["primary"], fg="white").pack(side="left", pady=6)
        tk.Button(hdr, text="⟳ Refresh", command=self._load_all_reports,
                  bg=COLORS["accent"], fg="white", font=FONTS["small"],
                  relief="flat", cursor="hand2").pack(side="right", padx=4, pady=4)

        cols = ("id", "title", "tech", "template", "status", "date")
        self.all_tree = ttk.Treeview(parent, columns=cols,
                                     show="headings", height=30)
        self.all_tree.heading("id",       text="#")
        self.all_tree.heading("title",    text="Title")
        self.all_tree.heading("tech",     text="Technician")
        self.all_tree.heading("template", text="Template")
        self.all_tree.heading("status",   text="Status")
        self.all_tree.heading("date",     text="Created")
        self.all_tree.column("id",       width=40)
        self.all_tree.column("title",    width=200)
        self.all_tree.column("tech",     width=130)
        self.all_tree.column("template", width=150)
        self.all_tree.column("status",   width=80)
        self.all_tree.column("date",     width=90)

        for status, color in COLORS.items():
            if status in STATUS_LABELS:
                self.all_tree.tag_configure(status, foreground=color)

        sb = ttk.Scrollbar(parent, orient="vertical",
                           command=self.all_tree.yview)
        self.all_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.all_tree.pack(fill="both", expand=True, padx=(8, 0), pady=8)
        self._load_all_reports()

    def _load_all_reports(self):
        self.all_tree.delete(*self.all_tree.get_children())
        for r in db.get_all_reports():
            date = (r["created_at"] or "")[:10]
            self.all_tree.insert(
                "", "end", iid=str(r["id"]),
                values=(r["id"], r["title"], r.get("tech_name", ""),
                        r.get("template_name", ""), r["status"].capitalize(),
                        date),
                tags=(r["status"],),
            )

    # ──────────────────────────────────────────────────────────────────
    # Tab 3 – Report Builder (Drag & Drop)
    # ──────────────────────────────────────────────────────────────────

    def _build_builder_tab(self, parent):
        """Drag-and-drop report builder."""
        self._builder_dropped: list = []   # list of report dicts placed on canvas
        self._drag_data: dict = {}

        top_bar = tk.Frame(parent, bg=COLORS["primary"], padx=10)
        top_bar.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(top_bar, text="Report Builder – drag reports onto the canvas",
                 font=FONTS["heading"], bg=COLORS["primary"],
                 fg="white").pack(side="left", pady=6)
        tk.Button(top_bar, text="⟳ Refresh Reports",
                  command=self._refresh_builder_sources,
                  bg=COLORS["accent"], fg="white", font=FONTS["small"],
                  relief="flat", cursor="hand2").pack(side="right", padx=4, pady=4)
        tk.Button(top_bar, text="🗑 Clear Canvas",
                  command=self._clear_canvas,
                  bg=COLORS["fail"], fg="white", font=FONTS["small"],
                  relief="flat", cursor="hand2").pack(side="right", padx=4, pady=4)
        tk.Button(top_bar, text="📄 Generate Report",
                  command=self._generate_report,
                  bg=COLORS["approved"], fg="white", font=FONTS["small"],
                  relief="flat", cursor="hand2").pack(side="right", padx=4, pady=4)

        main = tk.Frame(parent, bg=COLORS["bg_main"])
        main.pack(fill="both", expand=True, padx=8, pady=4)

        # ── Left: source list ─────────────────────────────────────────────
        src_frame = tk.Frame(main, bg=COLORS["bg_panel"], width=260)
        src_frame.pack(side="left", fill="y", padx=(0, 4))
        src_frame.pack_propagate(False)

        tk.Label(src_frame, text="Available Reports",
                 font=FONTS["heading"], bg=COLORS["accent"],
                 fg="white", pady=6).pack(fill="x", padx=0)
        tk.Label(src_frame,
                 text="Drag a report card onto the canvas →",
                 font=FONTS["tiny"], bg=COLORS["bg_panel"],
                 fg=COLORS["text_muted"], wraplength=230).pack(pady=4, padx=8)

        src_scroll = tk.Frame(src_frame, bg=COLORS["bg_panel"])
        src_scroll.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(src_scroll, orient="vertical")
        vsb.pack(side="right", fill="y")
        src_canvas = tk.Canvas(src_scroll, bg=COLORS["bg_panel"],
                               highlightthickness=0, yscrollcommand=vsb.set)
        src_canvas.pack(fill="both", expand=True)
        vsb.configure(command=src_canvas.yview)
        self._src_inner = tk.Frame(src_canvas, bg=COLORS["bg_panel"])
        src_canvas.create_window((0, 0), window=self._src_inner, anchor="nw")
        self._src_inner.bind(
            "<Configure>",
            lambda e: src_canvas.configure(
                scrollregion=src_canvas.bbox("all")),
        )

        # ── Right: canvas drop zone ───────────────────────────────────────
        canvas_frame = tk.Frame(main, bg=COLORS["bg_main"])
        canvas_frame.pack(side="left", fill="both", expand=True)
        tk.Label(canvas_frame, text="Canvas – drop reports here",
                 font=FONTS["small"], bg=COLORS["bg_main"],
                 fg=COLORS["text_muted"]).pack(anchor="nw", padx=4)
        self._drop_canvas = tk.Canvas(
            canvas_frame, bg="#f7f7f7", relief="sunken",
            highlightthickness=2, highlightbackground=COLORS["border"],
        )
        self._drop_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self._drop_canvas.bind("<ButtonRelease-1>", self._on_canvas_drop)

        self._refresh_builder_sources()

    def _refresh_builder_sources(self):
        for w in self._src_inner.winfo_children():
            w.destroy()
        reports = db.get_all_reports()
        if not reports:
            tk.Label(self._src_inner, text="No reports available.",
                     font=FONTS["small"], bg=COLORS["bg_panel"],
                     fg=COLORS["text_muted"]).pack(pady=20)
            return
        for r in reports:
            self._make_source_card(r)

    def _make_source_card(self, report: dict):
        status = report["status"]
        status_color = COLORS.get(status, COLORS["text_muted"])

        card = tk.Frame(self._src_inner, bg=COLORS["bg_panel"],
                        relief="raised", bd=1, cursor="hand2")
        card.pack(fill="x", padx=6, pady=3)

        # Color strip
        tk.Frame(card, bg=status_color, width=5).pack(side="left", fill="y")

        body = tk.Frame(card, bg=COLORS["bg_panel"], padx=6, pady=4)
        body.pack(side="left", fill="x", expand=True)
        tk.Label(body, text=report["title"], font=FONTS["small"],
                 bg=COLORS["bg_panel"], fg=COLORS["text_dark"],
                 wraplength=200, anchor="w").pack(anchor="w")
        info = f"{report.get('tech_name','')[:20]}  •  {(report['created_at'] or '')[:10]}"
        tk.Label(body, text=info, font=FONTS["tiny"],
                 bg=COLORS["bg_panel"], fg=COLORS["text_muted"]).pack(anchor="w")
        tk.Label(body, text=status.upper(), font=FONTS["tiny"],
                 bg=status_color, fg="white",
                 padx=4, pady=1).pack(anchor="w", pady=2)

        # Bind drag events
        for widget in [card, body] + body.winfo_children():
            widget.bind("<ButtonPress-1>",
                        lambda e, r=report: self._start_drag(e, r))
            widget.bind("<B1-Motion>",    self._do_drag)
            widget.bind("<ButtonRelease-1>",
                        lambda e, r=report: self._end_drag(e, r))

    # ── Drag & Drop ──────────────────────────────────────────────────────

    def _start_drag(self, event, report: dict):
        self._drag_data = {
            "report": report,
            "x":      event.x_root,
            "y":      event.y_root,
        }
        # Ghost label
        self._ghost = tk.Toplevel(self.root)
        self._ghost.overrideredirect(True)
        self._ghost.attributes("-alpha", 0.75)
        self._ghost.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
        tk.Label(self._ghost, text=f"⚗  {report['title']}",
                 font=FONTS["small"], bg=COLORS["accent"], fg="white",
                 padx=10, pady=6).pack()

    def _do_drag(self, event):
        if hasattr(self, "_ghost") and self._ghost.winfo_exists():
            self._ghost.geometry(
                f"+{event.x_root + 10}+{event.y_root + 10}")

    def _end_drag(self, event, report: dict):
        if hasattr(self, "_ghost") and self._ghost.winfo_exists():
            self._ghost.destroy()
        # Check if dropped on the canvas
        cx = self._drop_canvas.winfo_rootx()
        cy = self._drop_canvas.winfo_rooty()
        cw = self._drop_canvas.winfo_width()
        ch = self._drop_canvas.winfo_height()
        if (cx <= event.x_root <= cx + cw and
                cy <= event.y_root <= cy + ch):
            x = event.x_root - cx
            y = event.y_root - cy
            self._place_report_on_canvas(report, x, y)

    def _on_canvas_drop(self, event):
        pass  # Handled by _end_drag

    def _place_report_on_canvas(self, report: dict, x: int, y: int):
        """Draw a report card on the drop canvas."""
        if any(r["id"] == report["id"] for r in self._builder_dropped):
            messagebox.showinfo("Already added",
                                f"'{report['title']}' is already on the canvas.")
            return
        self._builder_dropped.append(report)
        c = self._drop_canvas
        status = report["status"]
        sc = COLORS.get(status, COLORS["text_muted"])
        x = max(10, min(x, c.winfo_width() - 130))
        y = max(10, min(y, c.winfo_height() - 80))

        # Draw card background
        rid = report["id"]
        card_tag = f"card_{rid}"
        c.create_rectangle(x, y, x+180, y+70, fill="white",
                           outline=sc, width=2, tags=card_tag)
        c.create_rectangle(x, y, x+6, y+70, fill=sc, outline=sc,
                           tags=card_tag)
        c.create_text(x+16, y+15, text=report["title"][:22],
                      font=FONTS["icon_title"], anchor="nw",
                      fill=COLORS["text_dark"], tags=card_tag)
        c.create_text(x+16, y+32, text=status.upper(),
                      font=FONTS["tiny"], anchor="nw",
                      fill=sc, tags=card_tag)
        date = (report.get("created_at") or "")[:10]
        c.create_text(x+16, y+48, text=date, font=FONTS["tiny"],
                      anchor="nw", fill=COLORS["text_muted"], tags=card_tag)

        # Remove button (×)
        btn_x, btn_y = x + 160, y + 10
        c.create_oval(btn_x - 8, btn_y - 8, btn_x + 8, btn_y + 8,
                      fill=COLORS["fail"], outline="",
                      tags=(card_tag, f"rm_{rid}"))
        c.create_text(btn_x, btn_y, text="✕", font=FONTS["tiny"],
                      fill="white", tags=(card_tag, f"rm_{rid}"))

        c.tag_bind(f"rm_{rid}", "<Button-1>",
                   lambda e, r=report, t=card_tag: self._remove_canvas_card(r, t))

        # Draggable
        c.tag_bind(card_tag, "<ButtonPress-1>",
                   lambda e, t=card_tag: self._canvas_drag_start(e, t))
        c.tag_bind(card_tag, "<B1-Motion>",
                   lambda e, t=card_tag: self._canvas_drag_move(e, t))

        self._canvas_drag_pos = {}

    def _canvas_drag_start(self, event, tag):
        self._canvas_drag_pos = {"x": event.x, "y": event.y, "tag": tag}

    def _canvas_drag_move(self, event, tag):
        if not self._canvas_drag_pos:
            return
        dx = event.x - self._canvas_drag_pos["x"]
        dy = event.y - self._canvas_drag_pos["y"]
        self._drop_canvas.move(tag, dx, dy)
        self._canvas_drag_pos["x"] = event.x
        self._canvas_drag_pos["y"] = event.y

    def _remove_canvas_card(self, report: dict, tag: str):
        self._drop_canvas.delete(tag)
        self._builder_dropped = [r for r in self._builder_dropped
                                  if r["id"] != report["id"]]

    def _clear_canvas(self):
        self._drop_canvas.delete("all")
        self._builder_dropped.clear()

    def _generate_report(self):
        if not self._builder_dropped:
            messagebox.showwarning("Empty canvas",
                                   "Drag at least one report onto the canvas first.")
            return
        ReportGeneratorDialog(self.root, self._builder_dropped, self.user)

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def _on_tab_change(self, event):
        nb = event.widget
        tab_id = nb.select()
        tab_name = nb.tab(tab_id, "text")
        if "All Reports" in tab_name:
            self._load_all_reports()
        elif "Pending" in tab_name:
            self._load_pending()


# ──────────────────────────────────────────────────────────────────────────────
# Report Generator Dialog
# ──────────────────────────────────────────────────────────────────────────────

class ReportGeneratorDialog(tk.Toplevel):
    """Modal dialog to configure and generate a composite report."""

    def __init__(self, parent, reports: list, user: dict):
        super().__init__(parent)
        self.reports = reports
        self.user    = user
        self.title("Generate Report")
        self.resizable(True, True)
        self.grab_set()
        w, h = 900, 680
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        self._build()

    def _build(self):
        self.configure(bg=COLORS["bg_main"])

        hdr = tk.Frame(self, bg=COLORS["bg_header"], padx=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📄  Report Generator",
                 font=FONTS["subtitle"], bg=COLORS["bg_header"],
                 fg=COLORS["fg_header"]).pack(side="left", pady=8)

        # Options bar
        opts = tk.Frame(self, bg=COLORS["bg_panel"], padx=12, pady=8)
        opts.pack(fill="x")
        tk.Label(opts, text="Report Name:", font=FONTS["body"],
                 bg=COLORS["bg_panel"]).pack(side="left")
        self._rpt_name = tk.StringVar(
            value=f"Composite Report – {len(self.reports)} reports")
        ttk.Entry(opts, textvariable=self._rpt_name,
                  width=40).pack(side="left", padx=8)
        tk.Button(opts, text="💾 Export to File",
                  command=self._export,
                  bg=COLORS["approved"], fg="white", font=FONTS["small"],
                  relief="flat", cursor="hand2").pack(side="right")

        # Preview
        preview_frame = tk.Frame(self, bg=COLORS["bg_main"])
        preview_frame.pack(fill="both", expand=True, padx=12, pady=8)
        tk.Label(preview_frame, text="Report Preview",
                 font=FONTS["heading"], bg=COLORS["bg_main"],
                 fg=COLORS["text_dark"]).pack(anchor="w")

        txt_frame = tk.Frame(preview_frame, bg=COLORS["bg_panel"])
        txt_frame.pack(fill="both", expand=True)
        vsb = ttk.Scrollbar(txt_frame, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._preview = tk.Text(txt_frame, wrap="word", font=FONTS["mono"],
                                yscrollcommand=vsb.set, bg="white",
                                state="disabled")
        vsb.configure(command=self._preview.yview)
        self._preview.pack(fill="both", expand=True)

        self._render_preview()

    def _render_preview(self):
        lines = []
        sep = "═" * 72
        lines.append(sep)
        lines.append(f"  COMPOSITE LAB REPORT")
        lines.append(f"  Generated by: {self.user['full_name']}")
        lines.append(f"  Reports included: {len(self.reports)}")
        lines.append(sep)
        lines.append("")

        for rep in self.reports:
            details = db.get_report_details(rep["id"])
            values  = db.get_report_values(rep["id"])
            lines.append("─" * 72)
            lines.append(f"  Report : {details['title']}")
            lines.append(f"  Patient: {details.get('patient_name','—')}  "
                         f"ID: {details.get('patient_id','—')}")
            lines.append(f"  Sample : {details.get('sample_id','—')}")
            lines.append(f"  Status : {details['status'].upper()}")
            lines.append(f"  Date   : {(details.get('created_at') or '')[:10]}")
            lines.append("")

            with_status    = [v for v in values if v["has_status"]]
            without_status = [v for v in values if not v["has_status"]]

            if with_status:
                lines.append(f"  {'Test':<25} {'Value':<12} {'Unit':<8} {'Range':<16} {'Status'}")
                lines.append("  " + "─" * 68)
                for v in with_status:
                    st = (v.get("test_status") or "pending").upper()
                    lines.append(
                        f"  {v['variable_name']:<25} "
                        f"{(v.get('value') or '—'):<12} "
                        f"{(v.get('unit') or ''):<8} "
                        f"{(v.get('normal_range') or '—'):<16} "
                        f"{st}"
                    )

            if without_status:
                lines.append("")
                lines.append(f"  {'Field':<25} {'Value'}")
                lines.append("  " + "─" * 40)
                for v in without_status:
                    lines.append(
                        f"  {v['variable_name']:<25} {v.get('value') or '—'}")
            lines.append("")

        lines.append(sep)
        lines.append("  END OF REPORT")
        lines.append(sep)

        content = "\n".join(lines)
        self._preview.configure(state="normal")
        self._preview.delete("1.0", "end")
        self._preview.insert("1.0", content)
        self._preview.configure(state="disabled")

    def _export(self):
        from tkinter import filedialog
        fp = filedialog.asksaveasfilename(
            title="Save report",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
        )
        if fp:
            content = self._preview.get("1.0", "end")
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(content)
            messagebox.showinfo("Saved", f"Report saved to:\n{fp}")


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
