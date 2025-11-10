#                            ____     __      _____  ___   _______  ________
#  ___  ___  ___ ___ _    __|_  /____/ /__   /  _/ |/ / | / / __/ |/ /_  __/
# / _ \/ _ \/ -_) _ \ |/|/ //_ </ __/  '_/  _/ //    /| |/ / _//    / / /   
# \___/ .__/\__/_//_/__,__/____/_/ /_/\_\  /___/_/|_/ |___/___/_/|_/ /_/    
#    /_/                        o3DIAG - 6.0.1                                                                    
# ***************************************************************************
# o3DIAG in version Beta 6.0.1 / English 
# o3DIAG comes with ABSOLUTELY NO WARRANTY!
# *************************************************
# Copyright (c) openw3rk INVENT
# Licensed under MIT-LICENSE
# *************************************************
# https://o3diag.openw3rk.de (Help button btw.)
# https://openw3rk.de
# Syntax help:
# https://o3diag.openw3rk.de/help/develop/cobol
# https://o3diag.openw3rk.de/help/develop/o3script
# For Feedback:
# develop@openw3rk.de
# *************************************************
# 6.0.1 - FULL ENGLISH VERSION
# *************************************************
# Required Files:
# o3DIAG_Pcodes_list_english.o3script 
# log_export/o3DIAG_Log_Export_Manager.exe 
# COBOL requires the runtime libraries.
# -------------------------------------------------
# Required Folders:
# /log_export (o3DIAG Log Export Manager, COBOL)
# C:\Users\USER\.o3DIAG\logs (Auto create)
# -------------------------------------------------

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, PhotoImage
import serial
import serial.tools.list_ports
import threading
import queue
import time
import re
import sys
import os
import webbrowser
import subprocess

def check_o3DIAG_directories():
    # Benutzer-Home-Verzeichnis für Logs
    user_home = os.path.expanduser("~")
    o3diag_base = os.path.join(user_home, ".o3DIAG")
    logs_dir = os.path.join(o3diag_base, "logs")
    temp_dir = os.path.join(o3diag_base, "temp_files")
    
    # Erstellen der Verzeichnisse in /User
    required_dirs = [o3diag_base, logs_dir, temp_dir]
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"\n[ OK ] Created o3DIAG directory:\n{dir_path}")
        else:
            print(f"\n[ OK ] o3DIAG Directory already exists:\n{dir_path}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    export_file = os.path.join(script_dir, "log_export", "o3DIAG_Log_Export_Manager.exe")
    if os.path.exists(export_file):
        print(f"\n[ OK ] Required o3DIAG Log Export Manager exists:\n{export_file}")
    else:
        print(f"\n[ PANIC ] Required o3DIAG Log Export Manager is missing:\n{export_file}")

check_o3DIAG_directories()

def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_asset_path(filename: str) -> str:
    return resource_path(os.path.join("o3assets", filename))

def clean_response(raw: str) -> str:
    if raw is None:
        return ""
    s = raw.replace('>', ' ').replace('\r', ' ').replace('\n', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s
def parse_pid_response(resp: str, pid_hex: str):
    if not resp:
        return None
    parts = resp.split(' ')
    parts = [p for p in parts if re.fullmatch(r'[0-9A-Fa-f]{2}', p)]
    for i in range(len(parts) - 1):
        if parts[i].upper() == '41' and parts[i+1].upper() == pid_hex.upper():
            data = parts[i+2:]
            return data
    return None
def calc_rpm(data):
    if data and len(data) >= 2:
        A = int(data[0], 16)
        B = int(data[1], 16)
        return ((A * 256) + B) / 4.0
    return None
def calc_speed(data):
    if data and len(data) >= 1:
        return int(data[0], 16)
    return None

def calc_temp(data):
    if data and len(data) >= 1:
        return int(data[0], 16) - 40
    return None

def calc_engine_load(data):
    if data and len(data) >= 1:
        return (int(data[0], 16) * 100.0) / 255.0
    return None

DTC_GROUPS = ['P', 'C', 'B', 'U']

def dtc_from_bytes(a: int, b: int) -> str:
    grp = (a & 0xC0) >> 6
    d1 = (a & 0x30) >> 4
    d2 = (a & 0x0F)
    d3 = (b & 0xF0) >> 4
    d4 = (b & 0x0F)
    return f"{DTC_GROUPS[grp]}{d1}{d2:X}{d3:X}{d4:X}"

def extract_dtcs_from_response(resp: str):
    tokens = re.findall(r'[0-9A-Fa-f]{2}', resp)
    dtcs = []
    if not tokens:
        return dtcs
    try:
        idx = [i for i, t in enumerate(tokens) if t.upper() == '43'][0]
    except IndexError:
        return dtcs
    i = idx + 1
    while i + 1 < len(tokens):
        A = int(tokens[i], 16)
        B = int(tokens[i+1], 16)
        if A == 0 and B == 0:
            break
        code = dtc_from_bytes(A, B)
        dtcs.append(code)
        i += 2
    return dtcs

class o3DIAGCommunicator(threading.Thread):
    def __init__(self, port, baudrate, rx_queue, tx_queue, stop_event):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.rx_queue = rx_queue
        self.tx_queue = tx_queue
        self.stop_event = stop_event
        self.ser = None

    def open(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(0.2)
            return True, ""
        except Exception as e:
            return False, str(e)

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except:
            pass

    def run(self):
        ok, err = self.open()
        if not ok:
            self.rx_queue.put(("__ERROR__", err))
            return
        read_buffer = ""
        try:
            while not self.stop_event.is_set():
                try:
                    cmd = self.tx_queue.get_nowait()
                except queue.Empty:
                    cmd = None
                if cmd:
                    try:
                        if self.ser and self.ser.is_open:
                            self.ser.write((cmd + "\r").encode())
                    except Exception as e:
                        self.rx_queue.put(("__ERROR__", f"Write failed: {e}"))
                try:
                    if self.ser and self.ser.in_waiting:
                        raw = self.ser.read(self.ser.in_waiting).decode(errors='ignore')
                        read_buffer += raw
                        if '>' in read_buffer or '\n' in read_buffer:
                            parts = re.split(r'>|\r\n|\n', read_buffer)
                            for p in parts[:-1]:
                                pclean = p.strip()
                                if pclean:
                                    self.rx_queue.put(("__DATA__", pclean))
                            read_buffer = parts[-1]
                except Exception as e:
                    self.rx_queue.put(("__ERROR__", f"Read failed: {e}"))
                time.sleep(0.05)
        finally:
            self.close()
            self.rx_queue.put(("__CLOSED__", "Serial closed"))
            
class o3DIAG: #v6.0.1 <-----
    @staticmethod
    def show_splash():
        splash = tk.Tk()
        splash.title("o3DIAG")
        splash.geometry("500x400")
        splash.configure(bg='white')
        splash.overrideredirect(True)
        
        # Center
        splash.update_idletasks()
        screen_width = splash.winfo_screenwidth()
        screen_height = splash.winfo_screenheight()
        x = (screen_width - 500) // 2
        y = (screen_height - 400) // 2
        splash.geometry(f"500x400+{x}+{y}")
        
        border_frame = tk.Frame(splash, bg='#e0e0e0', padx=2, pady=2)
        border_frame.pack(expand=True, fill='both', padx=10, pady=10)
        
        main_frame = tk.Frame(border_frame, bg='white', padx=20, pady=15)
        main_frame.pack(expand=True, fill='both')
        
        splash.image_ref = None
        
        try:
            logo_path = get_asset_path("o3I_VS_logo.png")
            print(f"Loading image from: {logo_path}")  # Debug
            print(f"File exists: {os.path.exists(logo_path)}")

            original_image = tk.PhotoImage(file=logo_path)

            width = original_image.width()
            height = original_image.height()
            resized_image = original_image.subsample(int(width / 243), int(height / (243 * height / width)))

            splash.image_ref = resized_image

            logo_label = tk.Label(main_frame, image=resized_image, bg='white')
            logo_label.pack(pady=20)
            print("Image loaded successfully")  # Debug
            
        except Exception as e:
            print(f"Splash image error: {e}")
            text_logo = tk.Label(
                main_frame, 
                text="o3DIAG", 
                font=("Arial", 24, "bold"), 
                fg="#2c3e50", 
                bg="white"
            )
            text_logo.pack(pady=25)
        
        title_label = tk.Label(
            main_frame, 
            text="o3DIAG", 
            font=("Arial", 14, "bold"), 
            fg="#2c3e50", 
            bg="white"
        )
        title_label.pack(pady=3)
        
        version_label = tk.Label(
            main_frame, 
            text="Version 6.0.1", 
            font=("Arial", 10), 
            fg="#7f8c8d", 
            bg="white"
        )
        version_label.pack(pady=1)
        
        separator = tk.Frame(main_frame, height=1, bg="#bdc3c7")
        separator.pack(fill='x', pady=15, padx=20)
        
        urls_frame = tk.Frame(main_frame, bg="white")
        urls_frame.pack(pady=12)
        
        url1_label = tk.Label(
            urls_frame, 
            text="https://o3diag.openw3rk.de", 
            font=("Arial", 9), 
            fg="#0f649d", 
            bg="white"
        )
        url1_label.pack(pady=1)
        
        url2_label = tk.Label(
            urls_frame, 
            text="https://openw3rk.de", 
            font=("Arial", 9), 
            fg="#0f649d", 
            bg="white"
        )
        url2_label.pack(pady=1)

        url3_label = tk.Label(
            urls_frame, 
            text="develop@openw3rk.de", 
            font=("Arial", 9), 
            fg="#0f649d", 
            bg="white"
        )
        url3_label.pack(pady=1)
        
        copyright_label = tk.Label(
            main_frame, 
            text="Copyright © 2025 openw3rk INVENT", 
            font=("Arial", 10), 
            fg="#000000", 
            bg="white"
        )
        copyright_label.pack(side='bottom', pady=10)

        def close_splash():
            splash.quit()  # WICHTIG: quit() vor destroy()
            splash.destroy()
            
        splash.after(3000, close_splash)
        splash.mainloop()

# ascii
    ASCII_ART = r"""
                           ____     __      _____  ___   _______  ________
 ___  ___  ___ ___ _    __|_  /____/ /__   /  _/ |/ / | / / __/ |/ /_  __/
/ _ \/ _ \/ -_) _ \ |/|/ //_ </ __/  '_/  _/ //    /| |/ / _//    / / /   
\___/ .__/\__/_//_/__,__/____/_/ /_/\_\  /___/_/|_/ |___/___/_/|_/ /_/    
   /_/ o3DIAG 6.0.1 - https://o3diag.openw3rk.de | https://openw3rk.de      
--------------------------------------------------------------------------

--> PLEASE NOTE THE INFO, WARN & DISCLAIMER BEFORE USING.   
--> Need help? Press the Help button and visit the o3DIAG website.

Log:
"""
    def __init__(self, root):
        self.root = root
        root.title("o3DIAG - Version 6.0.1 | for OBD-II / ELM327")
        root.geometry("1151x770")
        
        # Verwende ICO Datei für Fenster-Icon
        icon_path = get_asset_path("o3DIAG_ico.ico")
        try:
            root.iconbitmap(icon_path)
        except Exception as e:
            print(f"o3DIAG Icon not found: {e}")

        self.style = ttk.Style()
        self.darkmode = False
        self.set_theme()

        frm_conn = ttk.Frame(root, padding=8)
        frm_conn.grid(row=0, column=0, sticky="ew")
        ttk.Label(frm_conn, text="Port:").grid(row=0, column=0)
        self.cmb_ports = ttk.Combobox(frm_conn, width=18, values=self.list_ports())
        self.cmb_ports.grid(row=0, column=1, padx=4)
        if self.cmb_ports['values']:
            self.cmb_ports.set(self.cmb_ports['values'][0])

        ttk.Label(frm_conn, text="Baud:").grid(row=0, column=2)
        self.ent_baud = ttk.Entry(frm_conn, width=8)
        self.ent_baud.grid(row=0, column=3)
        self.ent_baud.insert(0, "115200")#115200 o3DIAG standard
        ttk.Button(frm_conn, text="Refresh", command=self.reload_com_ports).grid(row=0, column=4, padx=4)

        self.btn_connect = ttk.Button(frm_conn, text="Connect", command=self.toggle_connect)
        self.btn_connect.grid(row=0, column=5, padx=4)
        ttk.Label(frm_conn, text="-").grid(row=0, column=6)

        self.show_app_info = ttk.Button(frm_conn, text="Info & Warnings", command=self.info_warn)
        self.show_app_info.grid(row=0, column=7, padx=4)

#dark/light mode swap 
        self.btn_theme = ttk.Button(frm_conn, text="Switch to Darkmode", style="light_dark_swap.TButton", command=self.toggle_theme)
        self.btn_theme.grid(row=0, column=8, padx=4)

        self.lbl_status = ttk.Label(frm_conn, text="Status: disconnected")
        self.lbl_status.grid(row=1, column=0, columnspan=8, sticky="w", pady=(6,0))

        frm_ctrl = ttk.Frame(root, padding=8)
        frm_ctrl.grid(row=1, column=0, sticky="ew")
        root.grid_columnconfigure(0, weight=1)
        ttk.Label(frm_ctrl, text="Options:").grid(row=0, column=0, padx=4, pady=2, sticky="w")
        
#options for application and ECU
        btn_options = [
            ("Init Adapter", self.init_adapter),
            ("Clear DTCs", self.clear_dtcs),
            ("Clear Log", self.clear_log),
            ("Reload P-Code List", self.load_dtc_map),
            ("Export Log (.txt)", self.export_log_COBOL)
        ]

        for i, (text, cmd) in enumerate(btn_options, start=1):
            b = ttk.Button(frm_ctrl, text=text, command=cmd)
            b.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
            
#reading actions / get data with request codes
        ttk.Label(frm_ctrl, text="Actions:").grid(row=1, column=0, padx=4, pady=2, sticky="w")
        btn_reading = [
            ("Read Engine DTC", self.request_dtcs),
            ("Get RPM", lambda: self.request_pid("010C")),
            ("Get Speed", lambda: self.request_pid("010D")),
            ("Get Temp", lambda: self.request_pid("0105")),
            ("Get Load", lambda: self.request_pid("0104")),
            ("Get Voltage", lambda: self.request_pid("0142"))
        ]

        for i, (text, cmd) in enumerate(btn_reading, start=1):
            b = ttk.Button(frm_ctrl, text=text, command=cmd)
            b.grid(row=1, column=i, padx=2, pady=2, sticky="ew")

 
        frm_log = ttk.Frame(root, padding=8)
        frm_log.grid(row=2, column=0, sticky="nsew")
        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(frm_log, height=20, state="disabled", wrap="none")
        self.log_text.pack(expand=True, fill="both")
        self.make_text_colors()
        self.show_o3_INVENT_ascii_art()

        frm_data = ttk.Frame(root, padding=8)
        frm_data.grid(row=3, column=0, sticky="ew")

        ttk.Label(frm_data, text="RPM:").grid(row=0, column=0, sticky="e")
        self.lbl_rpm = ttk.Label(frm_data, text="-")
        self.lbl_rpm.grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(frm_data, text="Speed (km/h):").grid(row=0, column=2, sticky="e")
        self.lbl_speed = ttk.Label(frm_data, text="-")
        self.lbl_speed.grid(row=0, column=3, sticky="w", padx=6)

        ttk.Label(frm_data, text="CoolantTemp (°C):").grid(row=0, column=4, sticky="e")
        self.lbl_temp = ttk.Label(frm_data, text="-")
        self.lbl_temp.grid(row=0, column=5, sticky="w", padx=6)

        ttk.Label(frm_data, text="EngineLoad (%):").grid(row=0, column=6, sticky="e")
        self.lbl_load = ttk.Label(frm_data, text="-")
        self.lbl_load.grid(row=0, column=7, sticky="w", padx=6)

        ttk.Label(frm_data, text="Battery (V):").grid(row=0, column=8, sticky="e")
        self.lbl_voltage = ttk.Label(frm_data, text="-")
        self.lbl_voltage.grid(row=0, column=9, sticky="w", padx=6)

        frm_data.grid_columnconfigure(11, weight=1)

        self.btn_website = ttk.Button(
            frm_data,
            text="Help",
            command=lambda: (webbrowser.open("https://o3diag.openw3rk.de"),
                            self.log("Website requested: https://o3diag.openw3rk.de"))
        )
        self.btn_website.grid(row=0, column=11, sticky="e", padx=6)

        self.rx_queue = queue.Queue()
        self.tx_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None
        self.connected = False
        self.dtc_map = {}
        self.o3script_filename = "o3DIAG_Pcodes_list_english.o3script"#load o3Script PcodesList 
        self.load_dtc_map()
        self.root.after(100, self.process_rx)

    def set_theme(self):
        if self.darkmode:
            bg = "#1e1e1e"
            fg = "#d4d4d4"
            self.style.configure("TFrame", background=bg)
            self.style.configure("TLabel", background=bg, foreground="white")
            self.style.configure("TButton", background="black", foreground="black")  
            self.style.configure("Theme.TButton", background="white", foreground="black")  
            self.style.configure("light_dark_swap.TButton", background=bg, foreground="black") 
            self.style.configure("TEntry", fieldbackground="black", foreground="black")
            self.root.configure(bg=bg)
        else:
            bg = "#f0f0f0"
            fg = "#000000"
            self.style.configure("TFrame", background=bg)
            self.style.configure("TLabel", background=bg, foreground=fg)
            self.style.configure("TButton", background="#e0e0e0", foreground=fg)  
            self.style.configure("Theme.TButton", background="black", foreground="white") 
            self.style.configure("light_dark_swap.TButton", background="white", foreground="black") 
            self.style.configure("TEntry", fieldbackground="white", foreground=fg)
            self.root.configure(bg=bg)
        self.make_text_colors()

    def make_text_colors(self):
        if hasattr(self, "log_text"):
            if self.darkmode:
                self.log_text.configure(bg="#1e1e1e", fg="darkgray", insertbackground="white")
            else:
                self.log_text.configure(bg="white", fg="black", insertbackground="black")

    def toggle_theme(self):
        self.darkmode = not self.darkmode
        self.set_theme()
        self.btn_theme.config(
            text="Switch to Lightmode" if self.darkmode else "Switch to Darkmode",
            style="light_dark_swap.TButton"  
        )
    def list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]
    def reload_com_ports(self):
        vals = self.list_ports()
        self.cmb_ports['values'] = vals
        if vals:
            self.cmb_ports.set(vals[0])
        self.log("Ports refreshed")

    def info_warn(self):
        self.log(
        "\n\n****************************************************************\n"   
            "INFO:\n"
            "-----\n"
            "o3DIAG\nVersion 6.0.1 / English\n"
            "Copyright (c) openw3rk INVENT\n\n"

            "Web:\n"
            "----\n"
            "https://o3diag.openw3rk.de\n"
            "https://openw3rk.de\n"
            "develop@openw3rk.de\n\n"

            "Source Code:\n"
            "------------\n"
            "https://github.com/openw3rk-DEVELOP/o3DIAG\n\n"

            "Supported Vehicles:\n"
            "-------------------\n"
            "Actually developed for US vehicles,\n"
            "but basically works with other OBD-capable vehicles as well.\n\n"
  
            "DISCLAIMER:\n"
            "-----------\n"
            "USE AT YOUR OWN RISK!\nNO LIABILITY IS ASSUMED FOR ANY DAMAGES!\n"
            "o3DIAG comes with ABSOLUTELY NO WARRANTY!\n\n"
    
            "License:\n"
            "--------\n"
            "o3DIAG is licensed under MIT-License.\n"
            "Copyright (c) openw3rk INVENT\n"
            "****************************************************************\n")

#DATE TIME for LOG
    def log(self, text: str):
        ts_date = time.strftime("%Y/%m/%d")#date
        ts = time.strftime("%H:%M:%S")#time
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f"[{ts_date} {ts}] {text}\n")#date/time in log. text is log output
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', tk.END)
        self.log_text.configure(state='disabled')
        self.show_o3_INVENT_ascii_art()

    def export_log_COBOL(self): 
#see https://o3diag.openw3rk.de/help/develop/cobol

        try:
            log_text = self.log_text.get("1.0", "end-1c")

            # Pfade im User-Home-Verzeichnis
            user_home = os.path.expanduser("~")
            o3diag_base = os.path.join(user_home, ".o3DIAG")
            temp_dir = os.path.join(o3diag_base, "temp_files")
            logs_dir = os.path.join(o3diag_base, "logs")
            
            os.makedirs(temp_dir, exist_ok=True)
            
            input_file = os.path.join(temp_dir, "o3DIAG_INPUT_LOG.TXT")
            
            # Output-Log
            base_name = "o3DIAG_OUTPUT_LOG"
            ext = ".TXT"
            output_log_txt = os.path.join(logs_dir, base_name + ext)
            counter = 1
            while os.path.exists(output_log_txt):
                counter += 1
                output_log_txt = os.path.join(logs_dir, f"{base_name}_{counter:02d}{ext}")
                
            with open(input_file, "w", encoding="utf-8") as f:
                f.write(log_text)

            # Export-Manager
            script_dir = os.path.dirname(os.path.abspath(__file__))
            export_manager = os.path.join(script_dir, "log_export", "o3DIAG_Log_Export_Manager.exe")
            
            result = subprocess.run(
                [export_manager, input_file, output_log_txt],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                self.log(f"[PANIC] Log export failed: {result.stderr}")
                return
                
            try:
                os.remove(input_file)
            except Exception as e:
                self.log(f"[WARN] temp file could not be deleted: {e}")

            # Öffne nach Erstellung
            if os.path.exists(output_log_txt):
                if os.name == "nt":
                    os.startfile(output_log_txt)
                else:
                    subprocess.run(["xdg-open", output_log_txt])
                self.log(f"[EXPORT INFO] Log export completed successfully ({os.path.basename(output_log_txt)}).")
                self.log(f"[EXPORT PATH] {output_log_txt}")
            else:
                self.log(f"[PANIC] Output file not found: {output_log_txt}")

        except Exception as e:
            self.log(f"[PANIC] Export failed: {e}")

    def show_o3_INVENT_ascii_art(self):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', self.ASCII_ART + "\n")
        self.log_text.configure(state='disabled')

    def toggle_connect(self):#ELM adapter
        if self.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        port = self.cmb_ports.get().strip()
        try:
            baud = int(self.ent_baud.get().strip())
        except:
            messagebox.showwarning("Baud PANIC", "Wrong Baudrate")
            return
        if not port:
            messagebox.showwarning("Port PANIC", "No port selected")
            return
        self.stop_event.clear()
        self.thread = o3DIAGCommunicator(port, baud, self.rx_queue, self.tx_queue, self.stop_event)
        self.thread.start()
        self.connected = True
        self.btn_connect.config(text="Disconnect")
        self.lbl_status.config(text=f"Status: connected to {port} @ {baud}")
        self.log(f"Connecting to {port} @ {baud} ...")
        
        self.log("[ OK ] Connected - click 'Init Adapter' to initialize")

    def auto_initialize(self):
        if self.connected and not self.auto_init_performed:
            self.log("Initializing adapter...")
            self.auto_init_performed = True
            self.init_adapter_adaptive_direct()


    def send_and_wait(self, cmd: str, timeout: float = 1.0) -> bool:
        self.send_command(cmd)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                kind, payload = self.rx_queue.get_nowait()
            except queue.Empty:
                time.sleep(0.05)
                continue
                
            if kind == "__DATA__" and payload.strip():
                clean = payload.replace("SEARCHING...", "").strip()
                if clean and clean not in ["OK", ">"]:
                    self.log(f"Response: {clean}")
                return True
            elif kind == "__ERROR__":
                self.log(f"[ WARN ] {payload}")
                return True
                
        return False

    def disconnect(self):
        self.stop_event.set()
        self.connected = False
        self.btn_connect.config(text="Connect")
        self.lbl_status.config(text="Status: disconnected")
        self.log("Disconnected")

    def send_command(self, cmd: str):
        if not self.connected:
            self.log("[PANIC] Not connected – command not sent.")
            return
        self.tx_queue.put(cmd)
        self.log(f"Request >>> {cmd}") #OUT 

    def init_adapter(self):
        if not self.connected:
            self.log("[PANIC] Not connected: please connect first.")
            return
        self.log("Manual adapter initialization...")
        self.init_adapter_adaptive_direct()

    def init_adapter_adaptive_direct(self):
        if not self.connected:
            self.log("[PANIC] Not connected: please connect first.")
            return

        base_commands = [
            "ATZ",          # Reset
            "ATE0",         # Echo OFF
            "ATL0",         # Linefeeds OFF  
            "ATH0",         # Headers OFF
        ]
        
        advanced_commands = [
            "ATSP0",        # Auto-Protokoll
            "ATAT1",        # Adaptive Timing
            "ATSTFF",       # Max Timeout
            "ATAL",         # Long Messages
        ]
        
        test_commands = [
            "ATI",          # Adapter Info
            "0100"          # PID Support test
        ]

        self.log("Initializing Adapter (Adaptive Mode) ...")

        # Phase 1
        for cmd in base_commands:
            if self.send_and_wait(cmd, timeout=2.0):
                self.log(f"[ OK ] {cmd}")
            else:
                self.log(f"[ WARN ] {cmd} failed or no response")

        # Phase 2
        for cmd in advanced_commands:
            if self.send_and_wait(cmd, timeout=1.5):
                self.log(f"[ OK ] {cmd}")
            else:
                self.log(f"[ INFO ] {cmd} not supported")

        # Funktionalität testen
        for cmd in test_commands:
            if self.send_and_wait(cmd, timeout=2.0):
                self.log(f"[ OK ] {cmd} functional")
            else:
                self.log(f"[ WARN ] {cmd} not working")

        self.log("[ OK ] Adaptive initialization completed.")

    def request_pid(self, pidcmd: str):
        self.send_command(pidcmd)
        time.sleep(0.15) 

    def request_dtcs(self):
        self.send_command("03")
        time.sleep(0.15) 
        
    def clear_dtcs(self):#not compatible with o3DIAG E/EE 5.0 or earlier
        if messagebox.askyesno("WARNING", "Really clear stored trouble codes? (OBD-II Mode 04)"):
            self.send_command("04") #04/CLEAR

    def process_rx(self):
        try:
            while True:
                kind, payload = self.rx_queue.get_nowait()
                if kind == "__DATA__":
                    self.process_response(payload)
                elif kind == "__ERROR__":
                    self.log(f"[ERROR] {payload}")
                    self.lbl_status.config(text="Status: error")
                elif kind == "__CLOSED__":
                    self.log("Serial closed")
                    self.lbl_status.config(text="Status: disconnected")
                    self.connected = False
                    self.btn_connect.config(text="Connect")
        except queue.Empty:
            pass
        self.root.after(100, self.process_rx)

    def process_response(self, data: str):
        clean = clean_response(data).replace("SEARCHING...", "").strip()
        if not clean:
            return

        self.log(f"Response <<< {clean}")

        if "43" in clean:
            dtcs = extract_dtcs_from_response(clean)

            if not dtcs:
                dtcs = ["P0000"]#no dtc P0000 or 0000

            self.log("Error codes:")
            for code in dtcs:
                desc = self.lookup_dtc(code) or "(no description found)"
                self.log(f"  {code} – {desc}")

        d = parse_pid_response(clean, "0C")
        if d:
            rpm = calc_rpm(d)
            if rpm is not None:
                self.lbl_rpm.config(text=f"{rpm:.0f} |")
                self.log(f"RPM: {rpm:.0f} rpm")

        d = parse_pid_response(clean, "42")
        if d:
            try:
                A = int(d[0], 16)
                B = int(d[1], 16) if len(d) > 1 else 0
                voltage = (A * 256 + B) / 1000.0
                self.lbl_voltage.config(text=f"{voltage:.2f} V")
                self.log(f"BatteryVoltage: {voltage:.2f} V")
            except Exception as e:
                self.log(f"[PANIC] Voltage parse failed: {e}")

        d = parse_pid_response(clean, "0D")
        if d:
            sp = calc_speed(d)
            if sp is not None:
                self.lbl_speed.config(text=f"{sp:.0f} |")
                self.log(f"Speed: {sp:.0f} km/h")

        d = parse_pid_response(clean, "05")
        if d:
            t = calc_temp(d)
            if t is not None:
                self.lbl_temp.config(text=f"{t:.0f} |")
                self.log(f"CoolantTemp: {t:.0f} °C")

        d = parse_pid_response(clean, "04")
        if d:
            l = calc_engine_load(d)
            if l is not None:
                self.lbl_load.config(text=f"{l:.0f} |")
                self.log(f"EngineLoad: {l:.0f} %")

        if "NO DATA" in clean.upper():
            self.log("[PANIC] NO DATA – PID/Mode not supported or no current values.")

            
    def load_dtc_map(self):
        path = resource_path(self.o3script_filename)
        new_map = {}
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                reading = False
                for line in f:
                    s = line.strip()
                    if not s:
                        continue #o3Script syntax, see https://o3diag.openw3rk.de/help/develop/o3script
                    if s.startswith("<") and "START;READ" in s:
                        reading = True
                        continue
                    if s.startswith("<") and "END;READ" in s:
                        reading = False
                        continue
                    if not reading:
                        continue
                    if s.startswith("<") or s.startswith("-"):
                        continue
                    s = s.split("<")[0].strip()
                    if "\t" in s:
                        code, desc = s.split("\t", 1)
                    else:
                        parts = s.split(None, 1)
                        if len(parts) != 2:
                            continue
                        code, desc = parts
                    code = code.strip().upper()
                    desc = desc.strip()
                    if re.fullmatch(r'[PCBU]\d{4}', code):
                        new_map[code] = desc
        except FileNotFoundError:
            self.log(f"P-Code list not found: {self.o3script_filename}")
            self.dtc_map = {}
            return
        except Exception as e:
            self.log(f"P-Code list could not be read, o3Script syntax error?: {e}")
            self.dtc_map = {}
            return

        self.dtc_map = new_map
        self.log(f"P-Code list (English) loaded: {len(self.dtc_map)} lines\n")

    def lookup_dtc(self, code: str) -> str:
        return self.dtc_map.get(code.upper(), "")

if __name__ == "__main__":
    o3DIAG.show_splash()

    root = tk.Tk()
    app = o3DIAG(root)
    root.mainloop()
