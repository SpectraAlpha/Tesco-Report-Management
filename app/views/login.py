"""Login window – first screen the user sees."""

import tkinter as tk
from tkinter import ttk, messagebox

from app.utils.constants import COLORS, FONTS, ROLES
from app import database as db


class LoginWindow:
    """Simple username / password login that opens the role-appropriate view."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Lab Report Management – Login")
        self.root.resizable(False, False)
        self._center(400, 480)
        self._build()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self):
        self.root.configure(bg=COLORS["bg_main"])

        # ── Header ──────────────────────────────────────────────────────
        header = tk.Frame(self.root, bg=COLORS["bg_header"], height=120)
        header.pack(fill="x")
        tk.Label(
            header,
            text="⚗",
            font=("Helvetica", 36),
            bg=COLORS["bg_header"],
            fg="#3498db",
        ).pack(pady=(20, 0))
        tk.Label(
            header,
            text="Lab Report Management",
            font=FONTS["subtitle"],
            bg=COLORS["bg_header"],
            fg=COLORS["fg_header"],
        ).pack()

        # ── Card ─────────────────────────────────────────────────────────
        card = tk.Frame(self.root, bg=COLORS["bg_panel"], padx=40, pady=30,
                        relief="flat")
        card.pack(fill="both", expand=True, padx=30, pady=30)

        tk.Label(card, text="Sign In", font=FONTS["title"],
                 bg=COLORS["bg_panel"], fg=COLORS["text_dark"]).pack(anchor="w")
        tk.Label(card, text="Enter your credentials below",
                 font=FONTS["small"], bg=COLORS["bg_panel"],
                 fg=COLORS["text_muted"]).pack(anchor="w", pady=(0, 20))

        # Username
        tk.Label(card, text="Username", font=FONTS["body"],
                 bg=COLORS["bg_panel"], fg=COLORS["text_dark"]).pack(anchor="w")
        self.username_var = tk.StringVar()
        username_entry = ttk.Entry(card, textvariable=self.username_var,
                                   font=FONTS["body"], width=30)
        username_entry.pack(fill="x", pady=(2, 12))
        username_entry.focus_set()

        # Password
        tk.Label(card, text="Password", font=FONTS["body"],
                 bg=COLORS["bg_panel"], fg=COLORS["text_dark"]).pack(anchor="w")
        self.password_var = tk.StringVar()
        ttk.Entry(card, textvariable=self.password_var, show="•",
                  font=FONTS["body"], width=30).pack(fill="x", pady=(2, 20))

        # Login button
        login_btn = tk.Button(
            card, text="Sign In", command=self._login,
            bg=COLORS["accent"], fg="white", font=FONTS["heading"],
            relief="flat", cursor="hand2", padx=10, pady=8,
        )
        login_btn.pack(fill="x")

        # Demo hint
        tk.Label(
            card,
            text="Demo users: technician1 / labmanager1 / manager1\n(password: password)",
            font=FONTS["tiny"],
            bg=COLORS["bg_panel"],
            fg=COLORS["text_muted"],
            justify="center",
        ).pack(pady=(15, 0))

        # Bind Enter key
        self.root.bind("<Return>", lambda _e: self._login())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _login(self):
        username = self.username_var.get().strip()
        password = self.password_var.get()

        if not username or not password:
            messagebox.showwarning("Missing fields",
                                   "Please enter username and password.")
            return

        user = db.authenticate(username, password)
        if user is None:
            messagebox.showerror("Login failed",
                                 "Invalid username or password.")
            return

        self.root.destroy()
        self._open_role_view(user)

    def _open_role_view(self, user: dict):
        new_root = tk.Tk()
        role = user["role"]
        if role == "technician":
            from app.views.technician import TechnicianApp
            TechnicianApp(new_root, user)
        elif role == "lab_manager":
            from app.views.lab_manager import LabManagerApp
            LabManagerApp(new_root, user)
        elif role == "manager":
            from app.views.manager import ManagerApp
            ManagerApp(new_root, user)
        else:
            messagebox.showerror("Error", f"Unknown role: {role}")
            new_root.destroy()
            return
        new_root.mainloop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _center(self, w: int, h: int):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")
