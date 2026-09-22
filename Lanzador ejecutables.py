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

#APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0] if '__file__' not in globals() else __file__))
#APP_DIR = r'D:\Datos\DATA PAPA\5-Proyectos\Python\Lanzador ejectutables'
if getattr(sys, 'frozen', False):
    # carpeta donde está el exe
    base_path = os.path.dirname(sys.executable)
else:
    base_path = os.path.dirname(__file__)

CONFIG_FILE = os.path.join(base_path, "config.json")


with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

APP_DIR = config["APP_DIR"]
###print("Directorio configurado:", APP_DIR)

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
    
    # 1. Cargar el historial completo
    full_history = load_history()
    
    # 2. Filtrar las filas usando una comprensión de lista.
    #    Se comprueba que el 'action_id' de la entrada coincida con el ID buscado.
    filtered_history = [
        entry for entry in full_history 
        if int(entry.get("action_id")) == int(action_id)
    ]
    
    return filtered_history    

def save_history(history):
    # keep only most recent MAX_HISTORY
    #history = history[-MAX_HISTORY:]
    save_json(HISTORY_FILE, history)

def push_history(entry):
    history = load_history()
    history.append(entry)
    # 1. Agrupar las entradas por action_id
    grouped_history = defaultdict(list)
    for item in history:
        aid = item.get("action_id")
        if aid:
            grouped_history[aid].append(item)
    
    # 2. Truncar cada grupo individualmente por action_id
    final_history = []
    
    for aid, items in grouped_history.items():
        # Mantener solo los MAX_HISTORY más recientes de cada grupo
        # Dado que las listas se construyen en orden cronológico,
        # el slicing [-MAX_HISTORY:] toma los más recientes.
        truncated_items = items[-MAX_HISTORY:]
        final_history.extend(truncated_items)
        
    # 3. Ordenar la lista final por 'timestamp'
    # Es crucial reordenar la lista completa ya que el agrupamiento rompe el orden.
    final_history.sort(key=lambda x: x.get("timestamp", ""))
    
    # 4. Guardar el historial limpio y ordenado
    save_history(final_history)



# ---------------------------
# App GUI
# ---------------------------
class ActionRunnerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lanzador de Procesos")
        self.geometry("1400x900")
        self.minsize(700, 450)

        # carga ficheros
        self.actions = load_json(ACTIONS_FILE, [])
        ###print("actions=", self.actions)
        self.help_texts = load_json(HELP_FILE, {})
        self.history = load_history()

        # mapa id->action
        self.actions_by_id = {str(a.get("id")): a for a in self.actions}

        self.selected_action_id = tk.StringVar()
        # estructura para entradas dinámicas: lista de dicts {meta, var, widget}
        self.param_entries = []

        self.create_widgets()
        self.refresh_actions_list()

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
                bg="#ffffe0",
                relief="solid",
                borderwidth=1,
                padx=6,
                pady=3
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
        # Top frame: acción + botones ayuda / ejecutar
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)

        ttk.Label(top, text="Acción:").pack(side="left")
        self.action_combo = ttk.Combobox(top, textvariable=self.selected_action_id, state="readonly", width=45)
        self.action_combo.pack(side="left", padx=6)
        self.action_combo.bind("<<ComboboxSelected>>", self.on_action_selected)

        ttk.Button(top, text="Ejecutar", command=self.on_execute).pack(side="left", padx=4)
        ttk.Button(top, text="Ayuda", command=self.on_help).pack(side="left", padx=4)
        
        # Centro: parámetros dinámicos y botones auxiliares
        center = ttk.Frame(self)
        center.pack(fill="both", expand=True, padx=8, pady=6)

        left = ttk.Frame(center)
        left.pack(side="left", fill="y", padx=(0,8))

        # Área donde se añadirán los parámetros
        self.params_container = ttk.LabelFrame(left, text="Parámetros de la acción")
        self.params_container.pack(fill="both", expand=False, pady=4)

        # Historial (últimas 5 llamadas)
        hist_frame = ttk.LabelFrame(left, text="Últimas llamadas (historial)")
        hist_frame.pack(fill="both", expand=True, pady=6)

        self.history_list = tk.Listbox(hist_frame, height=8)
        self.history_list.pack(side="left", fill="both", expand=True, padx=(4,0), pady=4)
        self.history_list.bind("<Double-Button-1>", self.on_restore_history)
        hist_scroll = ttk.Scrollbar(hist_frame, orient="vertical", command=self.history_list.yview)
        hist_scroll.pack(side="right", fill="y")
        self.history_list.config(yscrollcommand=hist_scroll.set)

        ttk.Button(left, text="Restaurar selección", command=self.on_restore_history).pack(fill="x", pady=(4,0))

        # Right: Salida y opciones
        right = ttk.Frame(center)
        right.pack(side="right", fill="both", expand=True)

        out_frame = ttk.LabelFrame(right, text="Salida")
        out_frame.pack(fill="both", expand=True, pady=4)
        self.output_text = tk.Text(out_frame, wrap="none")
        self.output_text.pack(fill="both", expand=True)
        out_scroll_y = ttk.Scrollbar(out_frame, orient="vertical", command=self.output_text.yview)
        out_scroll_y.pack(side="right", fill="y")
        self.output_text.config(yscrollcommand=out_scroll_y.set)

        # bottom: estado y botones auxiliares
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=4)
        self.status_label = ttk.Label(bottom, text="Listo")
        self.status_label.pack(side="left")

        ttk.Button(bottom, text="Recargar JSON", command=self.reload_json).pack(side="right", padx=4)
        ttk.Button(bottom, text="Ver carpeta JSON", command=self.open_app_folder).pack(side="right", padx=4)

        # rellena historial visual
        # self.load_history_listbox()

    # ---------------------------
    # JSON / UI helpers
    # ---------------------------
    def refresh_actions_list(self):
        # rellenar combobox con "id - nombre" si existe nombre, sino id
        items = []
        for a in self.actions:
            aid = str(a.get("id"))
            name = a.get("name") or a.get("executable") or f"Acción {aid}"
            items.append(f"{aid} - {name}")
        self.action_combo['values'] = items
        # limpiar parámetros
        self.clear_params()

    def reload_json(self):
        self.actions = load_json(ACTIONS_FILE, [])
        self.help_texts = load_json(HELP_FILE, {})
        self.actions_by_id = {str(a.get("id")): a for a in self.actions}
        self.refresh_actions_list()
        messagebox.showinfo("Recargado", "Ficheros JSON recargados.")

    def open_app_folder(self):
        # abre el explorador en la carpeta del script
        os.startfile(APP_DIR)

    def clear_params(self):
        for child in self.params_container.winfo_children():
            child.destroy()
        self.param_entries = []

    def on_action_selected(self, event=None):
        val = self.action_combo.get().strip()
        if not val:
            return
        # combobox value is "id - name", extraer id
        aid = val.split(" - ", 1)[0].strip()
        action = self.actions_by_id.get(aid)
        if not action:
            messagebox.showerror("Error", f"No se ha encontrado la acción {aid}")
            return
        self.populate_params(action)
        self.load_history_listbox(action.get("id"))

    def populate_params(self, action):
        self.clear_params()
        params = action.get("parameters", [])
        if not isinstance(params, list):
            params = []
        for i, p in enumerate(params):
            frm = ttk.Frame(self.params_container)
            frm.pack(fill="x", padx=6, pady=4)

            lbl_text = f"{i+1}. {p.get('name','param')}"
            ttk.Label(frm, text=lbl_text).pack(side="left")

            v = tk.StringVar()
            entry = ttk.Entry(frm, textvariable=v, width=55)
            entry.pack(side="left", padx=(8,4))

            # botón selector opcional por parámetro:
            # folder = "C" => carpeta, folder = "F" => fichero
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

                browse_button = ttk.Button(
                    frm,
                    text="📁" if folder_mode == "C" else "📄",
                    width=3,
                    command=make_browse_action(v, folder_mode)
                )
                browse_button.pack(side="left", padx=2)
                self.attach_tooltip(
                    browse_button,
                    "Seleccionar carpeta" if folder_mode == "C" else "Seleccionar fichero"
                )

            # botón de ayuda pequeñita para el parámetro
            def make_help_action(text):
                return lambda: messagebox.showinfo("Ayuda parámetro", text or "Sin ayuda")
            ttk.Button(frm, text="?", width=2, command=make_help_action(p.get("help",""))).pack(side="left", padx=2)

            # ejemplo como etiqueta
            example = p.get("example")
            if example:
                ttk.Label(frm, text=f"Ej: {example}").pack(side="left", padx=(6,0))

            # store metadata
            self.param_entries.append({
                "meta": p,
                "var": v,
                "widget": entry
            })

        # si no hay parámetros, mostrar nota
        if not params:
            ttk.Label(self.params_container, text="(No hay parámetros definidos para esta acción)").pack(padx=6, pady=6)

    # ---------------------------
    # Historial
    # ---------------------------
    def load_history_listbox(self, action_id):
        self.history_list.delete(0, tk.END)
        h = load_history_by_action(action_id)
        for item in reversed(h):  # mostrar más reciente arriba
            # representación breve: "id - valores..."
            aid = item.get("action_id")
            ###print("action=", action_id)
            ###print("aid=", aid)
            vals = item.get("params", [])
            #summary = f"{aid} | " + " | ".join(vals)
            summary = f" | ".join(vals)

            self.history_list.insert(tk.END, summary)

    def on_restore_history(self, event=None):
        sel = self.history_list.curselection()
        if not sel:
            # si no seleccionado, usar primero (más reciente)
            if self.history_list.size() == 0:
                return
            idx = 0
        else:
            idx = sel[0]
        # item index in listbox is reversed order, so translate
        # listbox 0 == most recent; we stored history with most recent at end, reversed while showing
        # compute actual history index:
        val = self.action_combo.get().strip()
        if not val:
            return
        # combobox value is "id - name", extraer id
        action_id = val.split(" - ", 1)[0].strip()
        hist = load_history_by_action(action_id)
        if not hist:
            return
        actual = len(hist) - 1 - idx
        entry = hist[actual]
        aid = str(entry.get("action_id"))
        # select action in combobox
        # find combobox index
        values = self.action_combo['values']
        found_index = None
        for i, v in enumerate(values):
            if v.startswith(f"{aid} " ) or v.startswith(f"{aid}-") or v.startswith(f"{aid} -"):
                found_index = i
                break
        if found_index is not None:
            self.action_combo.current(found_index)
            self.on_action_selected()
            # rellenar parámetros
            params = entry.get("params", [])
            for i, val in enumerate(params):
                if i < len(self.param_entries):
                    self.param_entries[i]["var"].set(val)
            messagebox.showinfo("Restaurado", "Valores del historial restaurados como punto de partida.")
        else:
            messagebox.showwarning("No encontrada", f"Acción {aid} del historial no encontrada en acciones actuales.")

    # ---------------------------
    # Ayuda
    # ---------------------------
    def on_help(self):
        val = self.action_combo.get().strip()
        if not val:
            messagebox.showinfo("Ayuda", "Selecciona primero una acción.")
            return
        aid = val.split(" - ", 1)[0].strip()
        help_text = self.help_texts.get(str(aid))
        if not help_text:
            messagebox.showinfo("Ayuda", "No hay texto de ayuda para esta acción.")
            return
        # mostrar en ventana nueva
        win = tk.Toplevel(self)
        win.title(f"Ayuda - Acción {aid}")
        txt = tk.Text(win, wrap="word", width=80, height=20)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", help_text)
        txt.config(state="disabled")

    # ---------------------------
    # Ejecución
    # ---------------------------
    def on_execute(self):
        ###print("Ejecuta comando")
        val = self.action_combo.get().strip()
        if not val:
            messagebox.showwarning("Atención", "Selecciona una acción antes de ejecutar.")
            return
        aid = val.split(" - ", 1)[0].strip()
        action = self.actions_by_id.get(aid)
        if not action:
            messagebox.showerror("Error", f"Acción {aid} no encontrada")
            return

        # construir lista de parámetros en el orden definido
        assembled_params = ""
        lista_params = []
        for entry in self.param_entries:
            meta = entry["meta"]
            ##print ("meta=", meta)
            v = entry["var"].get().strip()
            lista_params.append(v)
            # si está vacío y no obligatorio, pasarlo como vacío. Podemos comprobar optional flag
            if v == "" and meta.get("required", False):
                messagebox.showwarning("Falta parámetro", f"Falta el parámetro: {meta.get('name')}")
                return
            # añadir prefijo/sufijo si existen (concatenar)
            ##print("parametro=" , v)

            pref = meta.get("prefix", "")
            suf = meta.get("suffix", "")
            ##print("pref=" , pref)
            ##print("suf=" , suf)
            full = f"{pref}{v}{suf}"
            ##print("full=" , full)
            assembled_params = assembled_params + " " + full

        # Preparar el comando
        executable = action.get("executable")
        if not executable:
            messagebox.showerror("Error", "Acción no tiene 'executable' definido en JSON.")
            return

        #use_shell = action.get("use_shell", False)

        # Si action define 'fixed_args' (lista) los incorporamos antes de los parámetros
        fixed_args = action.get("fixed_args", "")

        ##print (fixed_args)
        ##print (assembled_params)

        #command = list(map(str, fixed_args)) + list(map(str, assembled_params))
        command = fixed_args + assembled_params
       
        comando_completo = executable + " " + command

        ##print ("Comando completo=", comando_completo)

        # Si use_shell True construiremos una cadena de comando y ejecutaremos shell=True
        try:
            self.status_label.config(text="Ejecutando...")
            self.output_text.delete("1.0", tk.END)

            proc = subprocess.run(
                comando_completo,
                capture_output=True,  # Captura stdout y stderr
                encoding='cp1252',
                #text=True,            # Decodifica la salida como texto (usando la codificación predeterminada)
                check=True,           # Lanza una excepción CalledProcessError si el código de retorno no es 0
                shell=True           # Recomendado: ejecuta el comando directamente sin un shell intermediario
            )
            

            out = proc.stdout or ""
            err = proc.stderr or ""
            ret = proc.returncode

            display = f"--- Return code: {ret} ---\n"
            if out:
                display += "\n--- STDOUT ---\n" + out
            if err:
                display += "\n--- STDERR ---\n" + err

            self.output_text.insert("1.0", display)
            self.status_label.config(text=f"Última ejecución: código {ret}")

            # guardar en historial (action id + param values como lista)
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
            messagebox.showerror("Error ejecución", f"Error al ejecutar:\n{e}")
            self.status_label.config(text="Error durante la ejecución")

# ---------------------------
# Run app
# ---------------------------
def main():
    # create placeholder files if missing (ejemplo)
    if not os.path.exists(ACTIONS_FILE):
        sample_actions = [
            {
                "id": 1,
                "name": "Listar directorios (ejemplo)",
                # Para el ejemplo usamos PowerShell y construimos un -Command con prefijo/sufijo para el parámetro path
                "executable": "powershell.exe",
                "use_shell": True,
                # parámetros: en este caso 1 parámetro: path
                "parameters": [
                    {
                        "name": "path",
                        "help": "Ruta del directorio a listar. Puede ser absoluta o relativa.",
                        "example": "C:\\\\Users\\\\Public",
                        # prefix/suffix se concatenarán con el valor: producirá algo como:
                        # powershell.exe -Command "Get-ChildItem -Path 'C:\Users\Public' -Force"
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
            "1": "Acción: Listar directorios.\n\nParámetros:\n - path: ruta del directorio a listar.\n\nEjemplo: C:\\\\Users\\\\Public\n\nEsta acción usa PowerShell para listar contenidos del directorio."
        }
        save_json(HELP_FILE, sample_help)

    app = ActionRunnerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
