"""Lab Technician view – create and submit lab reports."""

import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from app.utils.constants import COLORS, FONTS, STATUS_LABELS
from app import database as db


class TechnicianApp:
    """Main window for the Lab Technician role."""

    ATTACH_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "attachments",
    )

    def __init__(self, root: tk.Tk, user: dict):
        self.root = root
        self.user = user
        self.current_report_id: int | None = None
        self.template_vars: list = []
        self.value_entries: list = []   # list of (var_dict, tk.StringVar)
        self.attachment_rows: list = [] # list of attachment dicts
        os.makedirs(self.ATTACH_DIR, exist_ok=True)
        self._build()
        self._load_report_list()

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build(self):
        self.root.title(
            f"Lab Technician – {self.user['full_name']}  |  Lab Report Management"
        )
        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.attributes("-zoomed", True)
        self.root.configure(bg=COLORS["bg_main"])

        # Top bar
        self._build_topbar()

        # Main paned window
        paned = tk.PanedWindow(self.root, orient="horizontal",
                               sashwidth=6, bg=COLORS["border"])
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Left: report list
        left = tk.Frame(paned, bg=COLORS["bg_panel"], width=280)
        paned.add(left, minsize=220)
        self._build_report_list(left)

        # Right: report form
        right = tk.Frame(paned, bg=COLORS["bg_main"])
        paned.add(right, minsize=500)
        self._build_report_form(right)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=COLORS["bg_header"], height=50)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="⚗  Lab Report Management", font=FONTS["subtitle"],
                 bg=COLORS["bg_header"], fg=COLORS["fg_header"]).pack(side="left", padx=16)
        tk.Label(bar, text=f"Logged in as: {self.user['full_name']}  (Lab Technician)",
                 font=FONTS["small"], bg=COLORS["bg_header"],
                 fg=COLORS["text_muted"]).pack(side="right", padx=16)

    def _build_report_list(self, parent):
        # Header
        hdr = tk.Frame(parent, bg=COLORS["accent"], padx=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="My Reports", font=FONTS["heading"],
                 bg=COLORS["accent"], fg="white").pack(side="left", pady=8)
        tk.Button(hdr, text="＋ New", command=self._new_report,
                  bg=COLORS["bg_header"], fg="white", font=FONTS["small"],
                  relief="flat", cursor="hand2").pack(side="right", padx=4, pady=6)

        # Treeview
        cols = ("title", "status", "date")
        self.report_tree = ttk.Treeview(parent, columns=cols, show="headings",
                                        selectmode="browse", height=30)
        self.report_tree.heading("title",  text="Report")
        self.report_tree.heading("status", text="Status")
        self.report_tree.heading("date",   text="Date")
        self.report_tree.column("title",  width=130)
        self.report_tree.column("status", width=70)
        self.report_tree.column("date",   width=80)

        sb = ttk.Scrollbar(parent, orient="vertical",
                           command=self.report_tree.yview)
        self.report_tree.configure(yscrollcommand=sb.set)
        self.report_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.report_tree.bind("<<TreeviewSelect>>", self._on_report_select)

        # Tag colours
        for status, color in [
            ("draft",     COLORS["draft"]),
            ("submitted", COLORS["submitted"]),
            ("approved",  COLORS["approved"]),
            ("rejected",  COLORS["rejected"]),
            ("audited",   COLORS["audited"]),
        ]:
            self.report_tree.tag_configure(status, foreground=color)

    def _build_report_form(self, parent):
        # Title bar
        self.form_title_var = tk.StringVar(value="Select or create a report")
        title_bar = tk.Frame(parent, bg=COLORS["accent"], padx=12)
        title_bar.pack(fill="x")
        tk.Label(title_bar, textvariable=self.form_title_var,
                 font=FONTS["heading"], bg=COLORS["accent"], fg="white"
                 ).pack(side="left", pady=8)
        self.submit_btn = tk.Button(
            title_bar, text="▶ Submit Report", command=self._submit_report,
            bg="#27ae60", fg="white", font=FONTS["small"],
            relief="flat", cursor="hand2",
        )
        self.submit_btn.pack(side="right", padx=4, pady=6)
        self.save_btn = tk.Button(
            title_bar, text="💾 Save Draft", command=self._save_draft,
            bg=COLORS["bg_header"], fg="white", font=FONTS["small"],
            relief="flat", cursor="hand2",
        )
        self.save_btn.pack(side="right", padx=4, pady=6)

        # Scrollable body
        canvas = tk.Canvas(parent, bg=COLORS["bg_main"], highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        self.form_body = tk.Frame(canvas, bg=COLORS["bg_main"])
        self._canvas_win = canvas.create_window(
            (0, 0), window=self.form_body, anchor="nw"
        )
        self.form_body.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(self._canvas_win, width=e.width),
        )
        # Mouse-wheel scroll
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"),
        )
        self._build_form_placeholder()

    def _build_form_placeholder(self):
        for w in self.form_body.winfo_children():
            w.destroy()
        tk.Label(
            self.form_body,
            text='Click "＋ New" to create a report\nor select one from the list.',
            font=FONTS["body"], bg=COLORS["bg_main"],
            fg=COLORS["text_muted"],
        ).pack(pady=60)

    def _build_form_widgets(self):
        """Render the form for the currently selected template."""
        for w in self.form_body.winfo_children():
            w.destroy()
        self.value_entries.clear()

        padding = {"padx": 16, "pady": 4}

        # ── Metadata section ─────────────────────────────────────────────
        meta = tk.LabelFrame(self.form_body, text="Report Information",
                              bg=COLORS["bg_panel"], font=FONTS["heading"],
                              padx=10, pady=10)
        meta.pack(fill="x", padx=16, pady=(16, 8))

        fields = [
            ("Report Title *", self.title_var),
            ("Patient Name",   self.patient_name_var),
            ("Patient ID",     self.patient_id_var),
            ("Sample ID",      self.sample_id_var),
        ]
        for label, var in fields:
            row = tk.Frame(meta, bg=COLORS["bg_panel"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, font=FONTS["body"], width=16, anchor="w",
                     bg=COLORS["bg_panel"], fg=COLORS["text_dark"]).pack(side="left")
            ttk.Entry(row, textvariable=var, font=FONTS["body"]).pack(
                side="left", fill="x", expand=True)

        # Template selector
        row = tk.Frame(meta, bg=COLORS["bg_panel"])
        row.pack(fill="x", pady=2)
        tk.Label(row, text="Template *", font=FONTS["body"], width=16, anchor="w",
                 bg=COLORS["bg_panel"], fg=COLORS["text_dark"]).pack(side="left")
        templates = db.get_templates()
        self._templates = {t["name"]: t for t in templates}
        self.template_combo = ttk.Combobox(
            row, values=[t["name"] for t in templates],
            font=FONTS["body"], state="readonly",
        )
        if self.current_template:
            self.template_combo.set(self.current_template)
        self.template_combo.pack(side="left", fill="x", expand=True)
        self.template_combo.bind("<<ComboboxSelected>>", self._on_template_change)

        # ── Test Variables section ────────────────────────────────────────
        test_frame = tk.LabelFrame(
            self.form_body, text="Test Results",
            bg=COLORS["bg_panel"], font=FONTS["heading"], padx=10, pady=10,
        )
        test_frame.pack(fill="x", padx=16, pady=8)

        if not self.template_vars:
            tk.Label(test_frame, text="Select a template to enter values.",
                     font=FONTS["body"], bg=COLORS["bg_panel"],
                     fg=COLORS["text_muted"]).pack()
        else:
            # Header row
            hdr = tk.Frame(test_frame, bg=COLORS["accent"])
            hdr.pack(fill="x", pady=(0, 4))
            for col, w in [("Test / Variable", 200), ("Value", 120),
                            ("Unit", 70), ("Normal Range", 130), ("Status", 80)]:
                tk.Label(hdr, text=col, font=FONTS["small"], bg=COLORS["accent"],
                         fg="white", width=w//8, anchor="w",
                         ).pack(side="left", padx=4, pady=3)

            status_vars_w_status = [v for v in self.template_vars if v["has_status"]]
            status_vars_no_status = [v for v in self.template_vars if not v["has_status"]]

            def _row(parent, v, existing_val="", existing_status=""):
                r = tk.Frame(parent, bg=COLORS["bg_panel"])
                r.pack(fill="x", pady=1)

                # Color bar on left based on has_status
                bar_color = COLORS["accent"] if v["has_status"] else COLORS["text_muted"]
                tk.Frame(r, bg=bar_color, width=4).pack(side="left", fill="y")

                tk.Label(r, text=v["name"], font=FONTS["body"],
                         bg=COLORS["bg_panel"], width=25, anchor="w",
                         fg=COLORS["text_dark"]).pack(side="left", padx=6)

                val_var = tk.StringVar(value=existing_val)
                ttk.Entry(r, textvariable=val_var, width=14,
                          font=FONTS["body"]).pack(side="left", padx=2)

                unit = v.get("unit") or ""
                tk.Label(r, text=unit, font=FONTS["small"],
                         bg=COLORS["bg_panel"], width=8,
                         fg=COLORS["text_muted"]).pack(side="left")

                # Normal range display
                lo, hi = v.get("normal_min"), v.get("normal_max")
                if lo is not None and hi is not None:
                    rng = f"{lo} – {hi}"
                elif lo is not None:
                    rng = f"≥ {lo}"
                elif hi is not None:
                    rng = f"≤ {hi}"
                else:
                    rng = "—"
                tk.Label(r, text=rng, font=FONTS["small"],
                         bg=COLORS["bg_panel"], width=16,
                         fg=COLORS["text_muted"]).pack(side="left", padx=2)

                if v["has_status"]:
                    status_var = tk.StringVar(value=existing_status or "pending")
                    status_combo = ttk.Combobox(
                        r, textvariable=status_var,
                        values=["pass", "fail", "pending"],
                        state="readonly", width=8, font=FONTS["small"],
                    )
                    status_combo.pack(side="left", padx=4)
                    status_var.trace_add(
                        "write",
                        lambda *a, sv=status_var, wr=r: self._color_row(sv, wr),
                    )
                    self._color_row(status_var, r)
                    self.value_entries.append((v, val_var, status_var))
                else:
                    self.value_entries.append((v, val_var, None))

            # Rows with status
            if status_vars_w_status:
                tk.Label(test_frame,
                         text="▸ Tests with PASS / FAIL evaluation",
                         font=FONTS["small"], bg=COLORS["bg_panel"],
                         fg=COLORS["accent"]).pack(anchor="w", pady=(4, 2))
                existing = {ev["variable_name"]: ev
                            for ev in self._existing_values
                            if ev["has_status"]}
                for v in status_vars_w_status:
                    ev = existing.get(v["name"], {})
                    _row(test_frame, v,
                         ev.get("value", ""),
                         ev.get("test_status", "pending"))

            # Rows without status
            if status_vars_no_status:
                sep = tk.Frame(test_frame, bg=COLORS["border"], height=1)
                sep.pack(fill="x", pady=8)
                tk.Label(test_frame,
                         text="▸ Informational fields (no pass/fail evaluation)",
                         font=FONTS["small"], bg=COLORS["bg_panel"],
                         fg=COLORS["text_muted"]).pack(anchor="w", pady=(0, 2))
                existing = {ev["variable_name"]: ev
                            for ev in self._existing_values
                            if not ev["has_status"]}
                for v in status_vars_no_status:
                    ev = existing.get(v["name"], {})
                    _row(test_frame, v, ev.get("value", ""))

        # ── Attachments section ───────────────────────────────────────────
        att_frame = tk.LabelFrame(
            self.form_body, text="Attachments",
            bg=COLORS["bg_panel"], font=FONTS["heading"], padx=10, pady=10,
        )
        att_frame.pack(fill="x", padx=16, pady=(8, 16))

        tk.Button(
            att_frame, text="📎 Attach File",
            command=self._attach_file,
            bg=COLORS["accent"], fg="white", font=FONTS["small"],
            relief="flat", cursor="hand2",
        ).pack(anchor="w", pady=(0, 6))

        self.attach_list_frame = tk.Frame(att_frame, bg=COLORS["bg_panel"])
        self.attach_list_frame.pack(fill="x")
        self._refresh_attachment_list()

    def _color_row(self, status_var: tk.StringVar, row: tk.Frame):
        s = status_var.get()
        bg = {
            "pass":    COLORS["pass_bg"],
            "fail":    COLORS["fail_bg"],
            "pending": COLORS["pending_bg"],
        }.get(s, COLORS["bg_panel"])
        row.configure(bg=bg)
        for child in row.winfo_children():
            try:
                child.configure(bg=bg)
            except tk.TclError:
                pass

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _load_report_list(self):
        self.report_tree.delete(*self.report_tree.get_children())
        for r in db.get_reports_by_user(self.user["id"]):
            date = (r["created_at"] or "")[:10]
            self.report_tree.insert(
                "", "end",
                iid=str(r["id"]),
                values=(r["title"], r["status"].capitalize(), date),
                tags=(r["status"],),
            )

    def _on_report_select(self, _event=None):
        sel = self.report_tree.selection()
        if not sel:
            return
        rid = int(sel[0])
        self._load_report(rid)

    def _load_report(self, report_id: int):
        self.current_report_id = report_id
        details = db.get_report_details(report_id)
        self._existing_values = db.get_report_values(report_id)
        self.attachment_rows = db.get_attachments(report_id)

        # Set form variables before building widgets
        self.title_var       = tk.StringVar(value=details["title"])
        self.patient_name_var= tk.StringVar(value=details.get("patient_name") or "")
        self.patient_id_var  = tk.StringVar(value=details.get("patient_id") or "")
        self.sample_id_var   = tk.StringVar(value=details.get("sample_id") or "")
        self.current_template = details.get("template_name") or ""

        tpl_id = details.get("template_id")
        self.template_vars = db.get_template_variables(tpl_id) if tpl_id else []

        self.form_title_var.set(f"Report: {details['title']}")
        self._build_form_widgets()

        # Lock submitted/approved reports
        if details["status"] not in ("draft", "rejected"):
            self._lock_form()

    def _lock_form(self):
        for w in self.form_body.winfo_descendants():
            try:
                w.configure(state="disabled")
            except tk.TclError:
                pass
        self.save_btn.configure(state="disabled")
        self.submit_btn.configure(state="disabled")

    def _on_template_change(self, _event=None):
        name = self.template_combo.get()
        t = self._templates.get(name)
        if t:
            self.template_vars = db.get_template_variables(t["id"])
        self._existing_values = []
        self._build_form_widgets()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _new_report(self):
        self.current_report_id = None
        self._existing_values = []
        self.attachment_rows = []
        self.template_vars = []
        self.current_template = ""

        self.title_var        = tk.StringVar(value="New Lab Report")
        self.patient_name_var = tk.StringVar()
        self.patient_id_var   = tk.StringVar()
        self.sample_id_var    = tk.StringVar()

        self.form_title_var.set("New Report")
        self._build_form_widgets()

    def _collect_values(self) -> list:
        rows = []
        for entry in self.value_entries:
            v, val_var = entry[0], entry[1]
            status_var = entry[2] if len(entry) > 2 else None
            lo, hi = v.get("normal_min"), v.get("normal_max")
            rng = f"{lo} – {hi}" if (lo is not None and hi is not None) else ""
            rows.append({
                "variable_name": v["name"],
                "value":         val_var.get(),
                "unit":          v.get("unit") or "",
                "test_status":   status_var.get() if status_var else None,
                "has_status":    1 if v["has_status"] else 0,
                "display_order": v.get("display_order", 0),
                "normal_range":  rng,
            })
        return rows

    def _ensure_report_saved(self) -> bool:
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning("Missing title", "Please enter a report title.")
            return False

        template_name = self.template_combo.get() if hasattr(self, "template_combo") else ""
        t = self._templates.get(template_name) if hasattr(self, "_templates") else None
        template_id = t["id"] if t else None

        if self.current_report_id is None:
            self.current_report_id = db.create_report(
                title, template_id, self.user["id"],
                self.sample_id_var.get(), self.patient_id_var.get(),
                self.patient_name_var.get(),
            )
        else:
            db.update_report_meta(
                self.current_report_id, title,
                self.sample_id_var.get(), self.patient_id_var.get(),
                self.patient_name_var.get(),
            )

        db.save_report_values(self.current_report_id, self._collect_values())
        return True

    def _save_draft(self):
        if self._ensure_report_saved():
            messagebox.showinfo("Saved", "Report saved as draft.")
            self._load_report_list()

    def _submit_report(self):
        if not self._ensure_report_saved():
            return
        if messagebox.askyesno("Submit Report",
                               "Submit this report for lab manager review?"):
            db.submit_report(self.current_report_id)
            messagebox.showinfo("Submitted",
                                "Report submitted for review.")
            self._load_report_list()
            self._load_report(self.current_report_id)

    def _attach_file(self):
        if self.current_report_id is None:
            if not self._ensure_report_saved():
                return

        paths = filedialog.askopenfilenames(
            title="Select file(s) to attach",
            filetypes=[
                ("All files", "*.*"),
                ("PDF files", "*.pdf"),
                ("Images", "*.png *.jpg *.jpeg *.tiff *.bmp"),
                ("Documents", "*.docx *.xlsx *.txt *.csv"),
            ],
        )
        for src in paths:
            fname = os.path.basename(src)
            dest = os.path.join(self.ATTACH_DIR,
                                f"{self.current_report_id}_{fname}")
            shutil.copy2(src, dest)
            ext = os.path.splitext(fname)[1].lower()
            db.add_attachment(self.current_report_id, fname, dest, ext)

        self.attachment_rows = db.get_attachments(self.current_report_id)
        self._refresh_attachment_list()

    def _refresh_attachment_list(self):
        for w in self.attach_list_frame.winfo_children():
            w.destroy()
        if not self.attachment_rows:
            tk.Label(self.attach_list_frame,
                     text="No attachments yet.",
                     font=FONTS["small"], bg=COLORS["bg_panel"],
                     fg=COLORS["text_muted"]).pack(anchor="w")
            return
        for att in self.attachment_rows:
            row = tk.Frame(self.attach_list_frame, bg=COLORS["highlight"],
                           pady=2)
            row.pack(fill="x", pady=1)
            tk.Label(row, text="📄", font=FONTS["body"],
                     bg=COLORS["highlight"]).pack(side="left", padx=4)
            tk.Label(row, text=att["filename"], font=FONTS["small"],
                     bg=COLORS["highlight"],
                     fg=COLORS["text_dark"]).pack(side="left", fill="x",
                                                   expand=True)
            tk.Button(
                row, text="Open", command=lambda a=att: self._open_attachment(a),
                bg=COLORS["accent"], fg="white", font=FONTS["tiny"],
                relief="flat", cursor="hand2",
            ).pack(side="right", padx=4)
            tk.Button(
                row, text="✕", command=lambda a=att: self._remove_attachment(a),
                bg=COLORS["fail"], fg="white", font=FONTS["tiny"],
                relief="flat", cursor="hand2",
            ).pack(side="right")

    def _open_attachment(self, att: dict):
        fp = att["filepath"]
        if not os.path.exists(fp):
            messagebox.showerror("Not found",
                                 f"File not found:\n{fp}")
            return
        if sys.platform.startswith("win"):
            try:
                os.startfile(fp)  # type: ignore[attr-defined]
            except AttributeError:
                subprocess.Popen(["start", fp], shell=True)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", fp])
        else:
            subprocess.Popen(["xdg-open", fp])

    def _remove_attachment(self, att: dict):
        if messagebox.askyesno("Remove attachment",
                               f"Remove '{att['filename']}'?"):
            db.delete_attachment(att["id"])
            self.attachment_rows = [a for a in self.attachment_rows
                                    if a["id"] != att["id"]]
            self._refresh_attachment_list()
