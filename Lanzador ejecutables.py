# -*- coding: utf-8 -*-
"""
action_runner.py
Aplicación Windows (Tkinter) para lanzar ejecutables según acciones definidas en JSON,
con parámetros dinámicos, historial (últimas 5 llamadas) y ayuda por acción.

Ficheros que usa (mismos directorio del script):
 - actions.json   : definiciones de acciones
 - help.json      : textos de ayuda por id de acción
 - history.json   : historial de últimas 5 llamadas (creado por la app)
"""

import json
import os
import subprocess
import shlex
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
from collections import defaultdict

if getattr(sys, 'frozen', False):
    # carpeta donde está el exe
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(__file__)

CONFIG_FILE = os.path.join(base_path, "config.json")

APP_DIR = base_path
if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            cfg_dir = config.get("APP_DIR", "")
            if cfg_dir and os.path.exists(cfg_dir):
                APP_DIR = cfg_dir
    except Exception:
        APP_DIR = base_path

ACTIONS_FILE = os.path.join(APP_DIR, "actions.json")
HELP_FILE = os.path.join(APP_DIR, "help.json")
HISTORY_FILE = os.path.join(APP_DIR, "history.json")
MAX_HISTORY = 7

# ---------------------------
# Utilidades JSON / History
# ---------------------------

def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default if default is not None else {}
    except Exception as e:
        messagebox.showerror("Error lectura JSON", f"Error leyendo {path}:\n{e}")
        return default if default is not None else {}

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        messagebox.showerror("Error escritura JSON", f"Error guardando {path}:\n{e}")

def load_history():
    h = load_json(HISTORY_FILE, [])
    if not isinstance(h, list):
        return []
    return h

def load_history_by_action(action_id):
    full_history = load_history()
    filtered_history = [
        entry for entry in full_history 
        if str(entry.get("action_id")) == str(action_id)
    ]
    return filtered_history    

def save_history(history):
    save_json(HISTORY_FILE, history)

def push_history(entry):
    history = load_history()
    history.append(entry)

    grouped_history = defaultdict(list)
    for item in history:
        aid = item.get("action_id")
        if aid is not None:
            grouped_history[str(aid)].append(item)
    
    final_history = []
    for aid, items in grouped_history.items():
        truncated_items = items[-MAX_HISTORY:]
        final_history.extend(truncated_items)
        
    final_history.sort(key=lambda x: x.get("timestamp", ""))
    save_history(final_history)


# ---------------------------
# App GUI
# ---------------------------
class ActionRunnerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lanzador de Procesos y Ejecutables")
        self.geometry("1300x850")
        self.minsize(800, 500)

        self.apply_styles()

        # carga ficheros
        self.actions = load_json(ACTIONS_FILE, [])
        self.help_texts = load_json(HELP_FILE, {})
        self.history = load_history()

        # mapa id->action
        self.actions_by_id = {str(a.get("id")): a for a in self.actions}

        self.selected_category = tk.StringVar(value="Todas")
        self.selected_action_id = tk.StringVar()
        self.param_entries = []

        self.create_widgets()
        self.refresh_categories()
        self.refresh_actions_list()

    def apply_styles(self):
        style = ttk.Style()
        available_themes = style.theme_names()
        if "clam" in available_themes:
            style.theme_use("clam")

        # Color palette
        bg_main = "#f5f6f8"
        bg_card = "#ffffff"
        primary_color = "#2563eb"
        primary_hover = "#1d4ed8"
        text_dark = "#1e293b"

        self.configure(bg=bg_main)

        style.configure(".", font=("Segoe UI", 10), background=bg_main, foreground=text_dark)
        style.configure("TFrame", background=bg_main)
        style.configure("Card.TFrame", background=bg_card, relief="flat")

        style.configure("TLabelframe", background=bg_main, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground=primary_color, background=bg_main)

        style.configure("TLabel", background=bg_main, foreground=text_dark)
        style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"), foreground="#0f172a", background=bg_main)
        style.configure("ActionTitle.TLabel", font=("Segoe UI", 11, "bold"), foreground="#1e3a8a", background="#eff6ff", wraplength=1200, justify="left")

        style.configure("TButton", font=("Segoe UI", 9, "bold"), padding=(10, 5))
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background=primary_color, foreground="#ffffff", padding=(14, 6))
        style.map("Primary.TButton", background=[("active", primary_hover)])

        style.configure("TCombobox", padding=4)

    def attach_tooltip(self, widget, text):
        tip = {"win": None}

        def on_enter(event=None):
            if tip["win"] is not None:
                return
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + widget.winfo_height() + 6
            win = tk.Toplevel(self)
            win.wm_overrideredirect(True)
            win.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(
                win,
                text=text,
                bg="#fef3c7",
                fg="#92400e",
                relief="solid",
                borderwidth=1,
                padx=8,
                pady=4,
                font=("Segoe UI", 9)
            )
            lbl.pack()
            tip["win"] = win

        def on_leave(event=None):
            if tip["win"] is not None:
                tip["win"].destroy()
                tip["win"] = None

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def create_widgets(self):
        # Header Frame: Categoría, Selección de Acción, Ejecutar y Ayuda
        header_frame = ttk.LabelFrame(self, text=" Selección de Acción ", padding=10)
        header_frame.pack(fill="x", padx=12, pady=(10, 6))

        top_controls = ttk.Frame(header_frame)
        top_controls.pack(fill="x", pady=(0, 6))

        # Categoría
        ttk.Label(top_controls, text="Categoría:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 4))
        self.category_combo = ttk.Combobox(
            top_controls,
            textvariable=self.selected_category,
            state="readonly",
            width=18
        )
        self.category_combo.pack(side="left", padx=(0, 16))
        self.category_combo.bind("<<ComboboxSelected>>", self.on_category_selected)

        # Acción
        ttk.Label(top_controls, text="Acción:", font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 4))
        self.action_combo = ttk.Combobox(
            top_controls,
            textvariable=self.selected_action_id,
            state="readonly",
            width=50
        )
        self.action_combo.pack(side="left", padx=(0, 12), fill="x", expand=True)
        self.action_combo.bind("<<ComboboxSelected>>", self.on_action_selected)

        # Botones Ejecutar y Ayuda
        ttk.Button(top_controls, text="▶ Ejecutar", style="Primary.TButton", command=self.on_execute).pack(side="left", padx=4)
        ttk.Button(top_controls, text="❓ Ayuda", command=self.on_help).pack(side="left", padx=4)

        # Panel para mostrar el TEXTO COMPLETO de la Acción Seleccionada
        self.title_card = tk.Frame(header_frame, bg="#eff6ff", highlightbackground="#bfdbfe", highlightthickness=1, padx=10, pady=8)
        self.title_card.pack(fill="x", pady=(6, 2))

        ttk.Label(self.title_card, text="Acción seleccionada:", font=("Segoe UI", 9, "bold"), foreground="#1e40af", background="#eff6ff").pack(anchor="w")
        self.full_action_title_label = ttk.Label(
            self.title_card,
            text="Ninguna acción seleccionada",
            style="ActionTitle.TLabel"
        )
        self.full_action_title_label.pack(anchor="w", fill="x", pady=(2, 0))

        # Bind resize event to adjust wraplength of action title dynamically
        self.title_card.bind("<Configure>", self.on_title_card_resize)

        # Body Frame (Split Left & Right)
        center = ttk.Frame(self)
        center.pack(fill="both", expand=True, padx=12, pady=6)

        left = ttk.Frame(center)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Parámetros dinámicos
        self.params_container = ttk.LabelFrame(left, text=" Parámetros de la acción ", padding=10)
        self.params_container.pack(fill="both", expand=True, pady=(0, 6))

        # Historial de llamadas
        hist_frame = ttk.LabelFrame(left, text=" Historial de ejecuciones (recientes) ", padding=10)
        hist_frame.pack(fill="both", expand=True, pady=(6, 0))

        hist_content = ttk.Frame(hist_frame)
        hist_content.pack(fill="both", expand=True)

        self.history_list = tk.Listbox(
            hist_content,
            height=6,
            font=("Consolas", 9),
            bg="#ffffff",
            fg="#334155",
            selectbackground="#2563eb",
            selectforeground="#ffffff",
            borderwidth=1,
            relief="solid"
        )
        self.history_list.pack(side="left", fill="both", expand=True)
        self.history_list.bind("<Double-Button-1>", self.on_restore_history)

        hist_scroll = ttk.Scrollbar(hist_content, orient="vertical", command=self.history_list.yview)
        hist_scroll.pack(side="right", fill="y")
        self.history_list.config(yscrollcommand=hist_scroll.set)

        ttk.Button(hist_frame, text="↺ Restaurar selección de historial", command=self.on_restore_history).pack(anchor="e", pady=(6, 0))

        # Panel Derecho: Salida de comando
        right = ttk.Frame(center)
        right.pack(side="right", fill="both", expand=True, padx=(6, 0))

        out_frame = ttk.LabelFrame(right, text=" Salida / Consola ", padding=10)
        out_frame.pack(fill="both", expand=True)

        out_content = ttk.Frame(out_frame)
        out_content.pack(fill="both", expand=True)

        self.output_text = tk.Text(
            out_content,
            wrap="none",
            font=("Consolas", 10),
            bg="#0f172a",
            fg="#f8fafc",
            insertbackground="#ffffff",
            borderwidth=0
        )
        self.output_text.pack(side="left", fill="both", expand=True)

        out_scroll_y = ttk.Scrollbar(out_content, orient="vertical", command=self.output_text.yview)
        out_scroll_y.pack(side="right", fill="y")
        self.output_text.config(yscrollcommand=out_scroll_y.set)

        out_scroll_x = ttk.Scrollbar(out_frame, orient="horizontal", command=self.output_text.xview)
        out_scroll_x.pack(fill="x", side="bottom")
        self.output_text.config(xscrollcommand=out_scroll_x.set)

        # Bottom Bar: Estado y Utilidades
        bottom = ttk.Frame(self, padding=(12, 6))
        bottom.pack(fill="x", side="bottom")

        self.status_label = ttk.Label(bottom, text="Listo", font=("Segoe UI", 9, "italic"), foreground="#475569")
        self.status_label.pack(side="left")

        ttk.Button(bottom, text="📁 Ver carpeta JSON", command=self.open_app_folder).pack(side="right", padx=(4, 0))
        ttk.Button(bottom, text="🔄 Recargar JSON", command=self.reload_json).pack(side="right", padx=4)

    def on_title_card_resize(self, event):
        if event.width > 20:
            self.full_action_title_label.config(wraplength=event.width - 20)

    # ---------------------------
    # JSON / UI helpers
    # ---------------------------
    def refresh_categories(self):
        categories = set()
        for a in self.actions:
            cat = a.get("category", "Otros") or "Otros"
            categories.add(cat)

        sorted_cats = ["Todas"] + sorted(list(categories))
        self.category_combo['values'] = sorted_cats
        if self.selected_category.get() not in sorted_cats:
            self.selected_category.set("Todas")

    def refresh_actions_list(self):
        current_cat = self.selected_category.get()
        items = []
        for a in self.actions:
            cat = a.get("category", "Otros") or "Otros"
            if current_cat != "Todas" and cat != current_cat:
                continue
            aid = str(a.get("id"))
            name = a.get("name") or a.get("executable") or f"Acción {aid}"
            items.append(f"{aid} - {name}")

        self.action_combo['values'] = items
        if items:
            self.action_combo.current(0)
            self.on_action_selected()
        else:
            self.selected_action_id.set("")
            self.full_action_title_label.config(text="No hay acciones en esta categoría")
            self.clear_params()
            self.history_list.delete(0, tk.END)

    def on_category_selected(self, event=None):
        self.refresh_actions_list()

    def reload_json(self):
        self.actions = load_json(ACTIONS_FILE, [])
        self.help_texts = load_json(HELP_FILE, {})
        self.actions_by_id = {str(a.get("id")): a for a in self.actions}
        self.refresh_categories()
        self.refresh_actions_list()
        messagebox.showinfo("Recargado", "Ficheros JSON recargados exitosamente.")

    def open_app_folder(self):
        if hasattr(os, "startfile"):
            os.startfile(APP_DIR)
        else:
            subprocess.run(["explorer", APP_DIR] if os.name == "nt" else ["xdg-open", APP_DIR])

    def clear_params(self):
        for child in self.params_container.winfo_children():
            child.destroy()
        self.param_entries = []

    def on_action_selected(self, event=None):
        val = self.action_combo.get().strip()
        if not val:
            self.full_action_title_label.config(text="Ninguna acción seleccionada")
            self.clear_params()
            self.history_list.delete(0, tk.END)
            return

        aid = val.split(" - ", 1)[0].strip()
        action = self.actions_by_id.get(aid)
        if not action:
            messagebox.showerror("Error", f"No se ha encontrado la acción {aid}")
            return

        full_name = action.get("name") or f"Acción {aid}"
        cat = action.get("category", "Otros") or "Otros"
        self.full_action_title_label.config(text=f"[{cat}]  {aid}. {full_name}")

        self.populate_params(action)
        self.load_history_listbox(action.get("id"))

    def populate_params(self, action):
        self.clear_params()
        params = action.get("parameters", [])
        if not isinstance(params, list):
            params = []

        for i, p in enumerate(params):
            frm = ttk.Frame(self.params_container)
            frm.pack(fill="x", padx=4, pady=4)

            lbl_text = f"{i+1}. {p.get('name','param')}:"
            ttk.Label(frm, text=lbl_text, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))

            v = tk.StringVar()
            entry = ttk.Entry(frm, textvariable=v)
            entry.pack(side="left", fill="x", expand=True, padx=(0, 6))

            folder_mode = str(p.get("folder", "")).upper()
            if folder_mode in ("C", "F"):
                def make_browse_action(var, mode):
                    def _browse():
                        if mode == "C":
                            selected = filedialog.askdirectory(title="Seleccionar carpeta")
                        else:
                            selected = filedialog.askopenfilename(title="Seleccionar fichero")
                        if selected:
                            var.set(selected)
                    return _browse

                browse_btn = ttk.Button(
                    frm,
                    text="📁" if folder_mode == "C" else "📄",
                    width=3,
                    command=make_browse_action(v, folder_mode)
                )
                browse_btn.pack(side="left", padx=2)
                self.attach_tooltip(
                    browse_btn,
                    "Seleccionar carpeta" if folder_mode == "C" else "Seleccionar fichero"
                )

            help_txt = p.get("help", "")
            if help_txt:
                def make_help_action(text):
                    return lambda: messagebox.showinfo("Ayuda de parámetro", text)
                help_btn = ttk.Button(frm, text="?", width=2, command=make_help_action(help_txt))
                help_btn.pack(side="left", padx=2)
                self.attach_tooltip(help_btn, help_txt)

            example = p.get("example")
            if example:
                ex_lbl = ttk.Label(frm, text=f"Ej: {example}", foreground="#64748b", font=("Segoe UI", 8))
                ex_lbl.pack(side="left", padx=(4, 0))

            self.param_entries.append({
                "meta": p,
                "var": v,
                "widget": entry
            })

        if not params:
            ttk.Label(self.params_container, text="(No hay parámetros definidos para esta acción)", foreground="#64748b").pack(padx=6, pady=12)

    # ---------------------------
    # Historial
    # ---------------------------
    def load_history_listbox(self, action_id):
        self.history_list.delete(0, tk.END)
        h = load_history_by_action(action_id)
        for item in reversed(h):
            vals = item.get("params", [])
            ts = item.get("timestamp", "")
            time_str = ts.split("T")[1][:5] if "T" in ts else ""
            prefix = f"[{time_str}] " if time_str else ""
            summary = prefix + " | ".join(vals)
            self.history_list.insert(tk.END, summary)

    def on_restore_history(self, event=None):
        sel = self.history_list.curselection()
        if not sel:
            if self.history_list.size() == 0:
                return
            idx = 0
        else:
            idx = sel[0]

        val = self.action_combo.get().strip()
        if not val:
            return

        action_id = val.split(" - ", 1)[0].strip()
        hist = load_history_by_action(action_id)
        if not hist:
            return

        actual = len(hist) - 1 - idx
        entry = hist[actual]

        params = entry.get("params", [])
        for i, pval in enumerate(params):
            if i < len(self.param_entries):
                self.param_entries[i]["var"].set(pval)

        self.status_label.config(text="Valores del historial restaurados.")

    # ---------------------------
    # Ayuda
    # ---------------------------
    def on_help(self):
        val = self.action_combo.get().strip()
        if not val:
            messagebox.showinfo("Ayuda", "Selecciona primero una acción.")
            return

        aid = val.split(" - ", 1)[0].strip()
        action = self.actions_by_id.get(aid, {})
        action_name = action.get("name", f"Acción {aid}")
        help_text = self.help_texts.get(str(aid), "No hay texto de ayuda específico para esta acción.")

        win = tk.Toplevel(self)
        win.title(f"Ayuda - {action_name}")
        win.geometry("650x400")
        win.configure(bg="#f5f6f8")

        f = ttk.Frame(win, padding=12)
        f.pack(fill="both", expand=True)

        ttk.Label(f, text=f"Ayuda de la Acción {aid}", font=("Segoe UI", 12, "bold"), foreground="#1e3a8a").pack(anchor="w", pady=(0, 8))
        ttk.Label(f, text=action_name, font=("Segoe UI", 10, "italic"), foreground="#334155").pack(anchor="w", pady=(0, 12))

        txt = tk.Text(f, wrap="word", font=("Segoe UI", 10), bg="#ffffff", fg="#0f172a", borderwidth=1, relief="solid")
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", help_text)
        txt.config(state="disabled")

    # ---------------------------
    # Ejecución
    # ---------------------------
    def on_execute(self):
        val = self.action_combo.get().strip()
        if not val:
            messagebox.showwarning("Atención", "Selecciona una acción antes de ejecutar.")
            return

        aid = val.split(" - ", 1)[0].strip()
        action = self.actions_by_id.get(aid)
        if not action:
            messagebox.showerror("Error", f"Acción {aid} no encontrada")
            return

        assembled_params = ""
        lista_params = []
        for entry in self.param_entries:
            meta = entry["meta"]
            v = entry["var"].get().strip()
            lista_params.append(v)

            if v == "" and meta.get("required", False):
                messagebox.showwarning("Falta parámetro", f"Falta el parámetro obligatorio: {meta.get('name')}")
                return

            pref = meta.get("prefix", "")
            suf = meta.get("suffix", "")
            full = f"{pref}{v}{suf}"
            assembled_params = assembled_params + " " + full

        executable = action.get("executable")
        if not executable:
            messagebox.showerror("Error", "La acción no tiene 'executable' definido en JSON.")
            return

        fixed_args = action.get("fixed_args", "")
        command = fixed_args + assembled_params
        comando_completo = executable + " " + command

        try:
            self.status_label.config(text="Ejecutando comando...")
            self.output_text.delete("1.0", tk.END)

            proc = subprocess.run(
                comando_completo,
                capture_output=True,
                encoding='cp1252',
                check=True,
                shell=True
            )

            out = proc.stdout or ""
            err = proc.stderr or ""
            ret = proc.returncode

            display = f"--- Código de retorno: {ret} ---\n"
            if out:
                display += "\n--- SALIDA (STDOUT) ---\n" + out
            if err:
                display += "\n--- ERRORES (STDERR) ---\n" + err

            self.output_text.insert("1.0", display)
            self.status_label.config(text=f"Última ejecución completada (código {ret})")

            hist_entry = {
                "action_id": aid,
                "params": lista_params,
                "timestamp": __import__("datetime").datetime.now().isoformat()
            }
            push_history(hist_entry)
            self.load_history_listbox(action.get("id"))

        except FileNotFoundError as e:
            messagebox.showerror("Error ejecución", f"Ejecutable no encontrado:\n{e}")
            self.status_label.config(text="Error: ejecutable no encontrado")
        except Exception as e:
            messagebox.showerror("Error ejecución", f"Error al ejecutar el comando:\n{e}")
            self.status_label.config(text="Error durante la ejecución")


def main():
    if not os.path.exists(ACTIONS_FILE):
        sample_actions = [
            {
                "id": 1,
                "category": "Otros",
                "name": "Listar directorios (ejemplo)",
                "executable": "powershell.exe",
                "use_shell": True,
                "parameters": [
                    {
                        "name": "path",
                        "help": "Ruta del directorio a listar.",
                        "example": "C:\\\\Users\\\\Public",
                        "prefix": "-Command \"Get-ChildItem -Path '",
                        "suffix": "' -Force\"",
                        "required": True
                    }
                ]
            }
        ]
        save_json(ACTIONS_FILE, sample_actions)

    if not os.path.exists(HELP_FILE):
        sample_help = {
            "1": "Acción: Listar directorios.\n\nParámetros:\n - path: ruta del directorio a listar."
        }
        save_json(HELP_FILE, sample_help)

    app = ActionRunnerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
