"""Entry point for the Lab Report Management application."""

import tkinter as tk

from app.database import init_db
from app.views.login import LoginWindow


def main():
    init_db()
    root = tk.Tk()
    root.withdraw()          # hide root; LoginWindow will show itself
    LoginWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
