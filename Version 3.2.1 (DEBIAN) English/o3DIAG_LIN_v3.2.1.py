#!/usr/bin/env python3

#                            ____     __      _____  ___   _______  ________
#  ___  ___  ___ ___ _    __|_  /____/ /__   /  _/ |/ / | / / __/ |/ /_  __/
# / _ \/ _ \/ -_) _ \ |/|/ //_ </ __/  '_/  _/ //    /| |/ / _//    / / /   
# \___/ .__/\__/_//_/__,__/____/_/ /_/\_\  /___/_/|_/ |___/___/_/|_/ /_/    
#    /_/                        o3DIAG - LINv3.2.1                                                                    
# ***************************************************************************
# o3DIAG in version LIN-3.2.1 / English
# o3DIAG comes with ABSOLUTELY NO WARRANTY!
# *************************************************
# Copyright (c) 2025 openw3rk INVENT
# Licensed under MIT-LICENSE
# *************************************************
# https://o3diag.openw3rk.de (Help button btw.)
# https://openw3rk.de
# Syntax help:
# https://o3diag.openw3rk.de/help/develop/o3script
# (o3script comes from intern use by openw3rk)
# -------------------------------------------------
# For Feedback and Request:
# develop@openw3rk.de
# *************************************************
# LIN-3.2.1 - FULL ENGLISH VERSION FOR LINUX/DEBIAN
# *************************************************
# Required Files:
# o3DIAG_Pcodes_list_english.o3script 
# Required Folders:
# /home/USER/.o3DIAG/logs (Auto create)
# -------------------------------------------------

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import queue
import time
import re
import sys
import os
import webbrowser
import glob
from datetime import datetime
import subprocess

# o3DIAG info
o3_NAME = "o3DIAG"
o3DIAG_VERSION = "LIN-3.2.1"

def check_o3DIAG_directories():
    user_home = os.path.expanduser("~")
    o3diag_base = os.path.join(user_home, ".o3DIAG")
    logs_dir = os.path.join(o3diag_base, "logs")
    temp_dir = os.path.join(o3diag_base, "temp_files")
    
    # Create directories in user home
    required_dirs = [o3diag_base, logs_dir, temp_dir]
    
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"\n[ OK ] Created o3DIAG directory:\n{dir_path}")
        else:
            print(f"\n[ OK ] o3DIAG Directory already exists:\n{dir_path}")

check_o3DIAG_directories()

def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_asset_path(filename: str) -> str:
    return resource_path(os.path.join("o3assets", filename))

def get_linux_serial_ports():
    ports = []
    
    # Common ELM327 / OBDII USB adapter devices (or "good" clones of ELM327)
    elm327_patterns = [
        '/dev/ttyUSB*',      # USB zu Serial Adapter
        '/dev/ttyACM*',      # CDC ACM devices
        '/dev/rfcomm*',      # Bluetooth devices
        '/dev/ttyS*',        # Standard serial ports
    ]
    
    for pattern in elm327_patterns:
        ports.extend(glob.glob(pattern))
    
    # Remove duplicates and sort
    ports = sorted(list(set(ports)))
    
    return ports

# port premission
def check_port_permissions(port):
    try:
        return os.access(port, os.R_OK | os.W_OK)
    except:
        return False

def fix_port_permissions(port):
    try:
        # Try to set permissions with sudo, user must be superuser.
        result = subprocess.run(
            ['sudo', 'chmod', '666', port],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except:
        return False

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

def calc_voltage(data):
    if data and len(data) >= 2:
        A = int(data[0], 16)
        B = int(data[1], 16)
        return (A * 256 + B) / 1000.0
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
        self.elm327_initialized = False

    def open(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                xonxoff=False,
                rtscts=False,
                dsrdtr=False
            )
            
            # Clear buffers
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            time.sleep(2)  # Important: Give ELM327 time to initialize
            return True, ""
            
        except Exception as e:
            return False, str(e)

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except:
            pass

    def initialize_elm327(self):
        if not self.ser or not self.ser.is_open:
            return False
            
        initialization_commands = [
            "ATZ",      # Reset
            "ATE0",     # Echo off
            "ATL0",     # Linefeeds off
            "ATH0",     # Headers off
            "ATSP0",    # Auto protocol detection
            "ATAT1",    # Adaptive timing
            "ATSTFF",   # Maximum timeout
        ]
        
        for cmd in initialization_commands:
            try:
                self.ser.write((cmd + "\r").encode())
                time.sleep(0.5)
                response = self.ser.read_all().decode('ascii', errors='ignore')
                if "OK" not in response and "ELM327" not in response:
                    print(f"Warning: {cmd} response: {response}")
            except Exception as e:
                print(f"Error during {cmd}: {e}")
                return False
                
        self.elm327_initialized = True
        return True

    def run(self):
        ok, err = self.open()
        if not ok:
            self.rx_queue.put(("__ERROR__", f"Failed to open port: {err}"))
            return
            
        # Initialize ELM327
        if not self.initialize_elm327():
            self.rx_queue.put(("__ERROR__", "ELM327 initialization failed"))
            self.close()
            return
            
        self.rx_queue.put(("__INFO__", "ELM327 adapter initialized successfully"))
        
        read_buffer = ""
        try:
            while not self.stop_event.is_set():
                # Send commands
                try:
                    cmd = self.tx_queue.get_nowait()
                    if cmd:
                        try:
                            self.ser.write((cmd + "\r").encode())
                            self.rx_queue.put(("__SENT__", cmd))
                        except Exception as e:
                            self.rx_queue.put(("__ERROR__", f"Write failed: {e}"))
                except queue.Empty:
                    pass

                # Read responses
                try:
                    if self.ser.in_waiting:
                        raw = self.ser.read(self.ser.in_waiting).decode('ascii', errors='ignore')
                        read_buffer += raw
                        
                        # Process complete lines
                        while '\r' in read_buffer or '>' in read_buffer:
                            if '\r' in read_buffer:
                                line, read_buffer = read_buffer.split('\r', 1)
                            elif '>' in read_buffer:
                                line, read_buffer = read_buffer.split('>', 1)
                            else:
                                break
                                
                            line = line.strip()
                            if line and line not in ['', 'OK']:
                                self.rx_queue.put(("__DATA__", line))
                                
                except Exception as e:
                    self.rx_queue.put(("__ERROR__", f"Read failed: {e}"))
                    
                time.sleep(0.1)
                
        finally:
            self.close()
            self.rx_queue.put(("__CLOSED__", "Serial connection closed"))

class o3DIAG:
# splash
    @staticmethod
    def show_splash():
        splash = tk.Tk()
        splash.title(o3_NAME)
        splash.geometry("500x400")
        splash.configure(bg='white')
        splash.overrideredirect(True)
        
        # Center window
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
        
        try:
            logo_path = get_asset_path("o3I_VS_logo.png")
            if os.path.exists(logo_path):
                original_image = tk.PhotoImage(file=logo_path)
                width = original_image.width()
                height = original_image.height()
                resized_image = original_image.subsample(int(width / 243), int(height / (243 * height / width)))
                splash.image_ref = resized_image
                logo_label = tk.Label(main_frame, image=resized_image, bg='white')
                logo_label.pack(pady=20)
            else:
                raise FileNotFoundError("Logo not found")
                
        except Exception as e:
            print(f"Splash image error: {e}")
            text_logo = tk.Label(
                main_frame, 
                text=o3_NAME, 
                font=("Arial", 24, "bold"), 
                fg="#2c3e50", 
                bg="white"
            )
            text_logo.pack(pady=25)
        
        title_label = tk.Label(
            main_frame, 
            text=o3_NAME, 
            font=("Arial", 14, "bold"), 
            fg="#2c3e50", 
            bg="white"
        )
        title_label.pack(pady=3)
        
        version_label = tk.Label(
            main_frame, 
            text=f"Version {o3DIAG_VERSION}", 
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
            splash.quit()
            splash.destroy()
            
        splash.after(3000, close_splash)
        splash.mainloop()

    ASCII_ART = f"""
                           ____     __      _____  ___   _______  ________
 ___  ___  ___ ___ _    __|_  /____/ /__   /  _/ |/ / | / / __/ |/ /_  __/
/ _ \\/ _ \\/ -_) _ \\ |/|/ //_ </ __/  '_/  _/ //    /| |/ / _//    / / /   
\\___/ .__/\\__/_//_/__,__/____/_/ /_/\\_\\  /___/_/|_/ |___/___/_/|_/ /_/    
   /_/ {o3_NAME} {o3DIAG_VERSION} - https://o3diag.openw3rk.de | https://openw3rk.de      
--------------------------------------------------------------------------

--> PLEASE NOTE THE INFO, WARN & DISCLAIMER BEFORE USING.   
--> Need help? Press the Help button and visit the o3DIAG website or press 'Info & Warnings'.

Log:
"""

    def __init__(self, root):
        self.root = root
        root.title(f"{o3_NAME} - Version {o3DIAG_VERSION} | OBD-II Diagnostic")
        root.geometry("1151x770")
        
        # Set window icon
        icon_path = get_asset_path("o3DIAG_ico.ico")
        try:
            root.iconbitmap(icon_path)
        except Exception as e:
            print(f"{o3_NAME} Icon not found: {e}")

        self.style = ttk.Style()
        self.darkmode = False
        self.set_theme()

        # Connection frame
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
        self.ent_baud.insert(0, "115200")  # o3DIAG standard baudrate
        
        ttk.Button(frm_conn, text="Refresh", command=self.reload_com_ports).grid(row=0, column=4, padx=4)

        self.btn_connect = ttk.Button(frm_conn, text="Connect", command=self.toggle_connect)
        self.btn_connect.grid(row=0, column=5, padx=4)
        ttk.Label(frm_conn, text="-").grid(row=0, column=6)

        self.btn_fix_permissions = ttk.Button(frm_conn, text="Fix Permissions", command=self.fix_permissions_dialog)
        self.btn_fix_permissions.grid(row=0, column=7, padx=4)

        self.show_app_info = ttk.Button(frm_conn, text="Info & Warnings", command=self.info_warn)
        self.show_app_info.grid(row=0, column=8, padx=4)

        # Dark/Light mode toggle
        self.btn_theme = ttk.Button(frm_conn, text="Switch to Darkmode", command=self.toggle_theme)
        self.btn_theme.grid(row=0, column=9, padx=4)

        self.lbl_status = ttk.Label(frm_conn, text="Status: disconnected")
        self.lbl_status.grid(row=1, column=0, columnspan=10, sticky="w", pady=(6,0))

        # Control frame
        frm_ctrl = ttk.Frame(root, padding=8)
        frm_ctrl.grid(row=1, column=0, sticky="ew")
        root.grid_columnconfigure(0, weight=1)
        ttk.Label(frm_ctrl, text="Options:").grid(row=0, column=0, padx=4, pady=2, sticky="w")
        
        # Application and ECU options
        btn_options = [
            ("Init Adapter", self.init_adapter),
            ("Clear DTCs", self.clear_dtcs),
            ("Clear Log", self.clear_log),
            ("Reload P-Code List", self.load_dtc_map),
            ("Export Log", self.export_log)
        ]

        for i, (text, cmd) in enumerate(btn_options, start=1):
            b = ttk.Button(frm_ctrl, text=text, command=cmd)
            b.grid(row=0, column=i, padx=2, pady=2, sticky="ew")
            
        # Reading actions / get data with request codes
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

        # Log frame
        frm_log = ttk.Frame(root, padding=8)
        frm_log.grid(row=2, column=0, sticky="nsew")
        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(frm_log, height=20, state="disabled", wrap="none")
        self.log_text.pack(expand=True, fill="both")
        self.make_text_colors()
        self.show_o3_INVENT_ascii_art()

        # Data display frame
        frm_data = ttk.Frame(root, padding=8)
        frm_data.grid(row=3, column=0, sticky="ew")

        # Initialize data labels properly
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

        frm_data.grid_columnconfigure(10, weight=1)

        self.btn_website = ttk.Button(
            frm_data,
            text="Help",
            command=lambda: webbrowser.open("https://o3diag.openw3rk.de")
        )
        self.btn_website.grid(row=0, column=10, sticky="e", padx=6)

        # Communication setup
        self.rx_queue = queue.Queue()
        self.tx_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None
        self.connected = False
        self.dtc_map = {}
        # Get the o3script Pcodes list (DTC map). (written in o3script (o3script comes from intern use))
        # The file works like a normal file, no runtime required.
        self.o3script_filename = "o3DIAG_Pcodes_list_english.o3script"
        self.load_dtc_map()
        self.root.after(100, self.process_rx)

    def set_theme(self):
        if self.darkmode:
            bg = "#1e1e1e"
            fg = "#2dcfa7"
            self.style.configure("TFrame", background=bg)
            self.style.configure("TLabel", background=bg, foreground=fg)
            self.style.configure("TButton", background="#555555", foreground=fg)
            self.style.configure("TCombobox", fieldbackground=bg, foreground=fg)
            self.style.configure("TEntry", fieldbackground=bg, foreground=fg)
            self.root.configure(bg=bg)
        else:
            bg = "#f0f0f0"
            fg = "#000000"
            self.style.configure("TFrame", background=bg)
            self.style.configure("TLabel", background=bg, foreground=fg)
            self.style.configure("TButton", background="#e0e0e0", foreground=fg)
            self.style.configure("TCombobox", fieldbackground="white", foreground=fg)
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
            text="Switch to Lightmode" if self.darkmode else "Switch to Darkmode"
        )

    def list_ports(self):
        return get_linux_serial_ports()

    def reload_com_ports(self):
        vals = self.list_ports()
        self.cmb_ports['values'] = vals
        if vals:
            self.cmb_ports.set(vals[0])
        self.log("Ports refreshed")

    def fix_permissions_dialog(self):
        current_port = self.cmb_ports.get()
        if not current_port:
            messagebox.showwarning("No Port", "Please select a port first")
            return
            
        if messagebox.askyesno("Fix Permissions", 
                              f"This will try to fix permissions for:\n{current_port}\n\n"
                              "This requires sudo privileges and will ask for your password (Terminal).\n\n"
                              "Continue?"):
            self.fix_port_permissions(current_port)

    def fix_port_permissions(self, port):
        self.log(f"Attempting to fix permissions for {port}...")
        
        if fix_port_permissions(port):
            self.log(f"[SUCCESS] Permissions fixed for {port}")
            messagebox.showinfo("Success", f"Permissions fixed for {port}\nYou can now try to connect.")
            self.reload_com_ports()
        else:
            self.log(f"[ERROR] Failed to fix permissions for {port}")
            messagebox.showerror("Error", 
                               f"Failed to fix permissions for {port}\n\n"
                               "Manual solution:\n"
                               "1. Run in terminal: sudo chmod 666 {port}\n"
                               "2. Or run o3DIAG from terminal as root")

    def info_warn(self):
# infos and warn
        self.log(
        "\n\n****************************************************************\n"   
            "INFO:\n"
            "-----\n"
            f"{o3_NAME}\nVersion {o3DIAG_VERSION} / English\n"
            "Copyright (c) 2025 openw3rk INVENT\n\n"

            "Web:\n"
            "----\n"
            "https://o3diag.openw3rk.de\n"
            "https://openw3rk.de\n"
            "https://github.com/openw3rk-DEVELOP/o3DIAG\n"
            "develop@openw3rk.de\n\n"

            "Supported Vehicles:\n"
            "-------------------\n"
            "Actually developed for US vehicles,\n"
            "but basically works with other OBD-capable vehicles as well.\n\n"

            "Usage:\n"
            "------\n"
            "1. Connect your ELM327 adapter to your device.\n"
            "2. Select the tty/USB port.\n"
            "3. Choose the baud rate (default: 115200) and press 'Connect'.\n"
            "4. Press 'Init Adapter'.\n"
            "5. Now you are ready to go.\n\n"

            "DISCLAIMER:\n"
            "-----------\n"
            "USE AT YOUR OWN RISK!\nNO LIABILITY IS ASSUMED FOR ANY DAMAGES!\n"
            "o3DIAG comes with ABSOLUTELY NO WARRANTY!\n\n"
    
            "License:\n"
            "--------\n"
            "o3DIAG is licensed under MIT-License.\n"
            "Copyright (c) 2025 openw3rk INVENT\n"
            "****************************************************************\n")

    def log(self, text: str):
        ts_date = time.strftime("%Y/%m/%d")
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f"[{ts_date} {ts}] {text}\n")
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', tk.END)
        self.log_text.configure(state='disabled')
        self.show_o3_INVENT_ascii_art()

    def export_log(self):
        try:
            default_filename = f"o3DIAG_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=default_filename,
                title="Save o3DIAG Log As"
            )
            
            if file_path:
                log_content = self.log_text.get("1.0", "end-1c")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(log_content)
                
                self.log(f"Log saved successfully to: {file_path}")
                messagebox.showinfo("Success", f"Log saved to:\n{file_path}")
                
        except Exception as e:
            self.log(f"[ERROR] Failed to save log: {e}")
            messagebox.showerror("Error", f"Failed to save log:\n{e}")

    def show_o3_INVENT_ascii_art(self):
        self.log_text.configure(state='normal')
        self.log_text.insert('end', self.ASCII_ART + "\n")
        self.log_text.configure(state='disabled')

    def toggle_connect(self):
        if self.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        port = self.cmb_ports.get().strip()
        try:
            baud = int(self.ent_baud.get().strip())
        except:
            messagebox.showwarning("Invalid Baudrate", "Please enter a valid baudrate (115200)")
            return
            
        if not port:
            messagebox.showwarning("No Port Selected", "Please select a serial port")
            return
            
        # Check permissions before connecting
        if not check_port_permissions(port):
            if messagebox.askyesno("Permission Error", 
                                  f"No permission to access {port}\n\n"
                                  "Do you want to try to fix permissions now?"):
                self.fix_port_permissions(port)
                return
            else:
                return
        
        self.stop_event.clear()
        self.thread = o3DIAGCommunicator(port, baud, self.rx_queue, self.tx_queue, self.stop_event)
        self.thread.start()
        self.connected = True
        self.btn_connect.config(text="Disconnect")
        self.lbl_status.config(text=f"Status: Connecting to {port} @ {baud}...")
        self.log(f"Attempting connection to {port} @ {baud} baud")

    def disconnect(self):
        self.stop_event.set()
        self.connected = False
        self.btn_connect.config(text="Connect")
        self.lbl_status.config(text="Status: Disconnected")
        self.log("Disconnected from ELM327-Adapter")

    def send_command(self, cmd: str):
        if not self.connected:
            self.log("[ERROR] Not connected - please connect first")
            return
        self.tx_queue.put(cmd)

    def init_adapter(self):
        if not self.connected:
            self.log("[ERROR] Not connected - please connect first")
            return
            
        self.log("Initializing Adapter...")
        # Enhanced initialization sequence
        init_commands = [
            "ATZ",      # Reset
            "ATE0",     # Echo off
            "ATL0",     # Linefeeds off
            "ATH0",     # Headers off
            "ATSP0",    # Auto protocol detection
            "ATDP",     # Describe protocol
        ]
        
        for cmd in init_commands:
            self.send_command(cmd)
            time.sleep(0.5)

    def request_pid(self, pidcmd: str):
        self.send_command(pidcmd)

    def request_dtcs(self):
        self.send_command("03")

    def clear_dtcs(self):
        if messagebox.askyesno("Clear DTCs", 
                              "WARNING: This will clear all stored trouble codes.\n\n"
                              "Ensure this is what you want to do.\n\n"
                              "Clear DTCs now?"):
            self.send_command("04")
            self.log("Clearing diagnostic trouble codes...")

    def process_rx(self):
        try:
            while True:
                kind, payload = self.rx_queue.get_nowait()
                
                if kind == "__DATA__":
                    self.process_response(payload)
                elif kind == "__ERROR__":
                    self.log(f"[ERROR] {payload}")
                    self.lbl_status.config(text=f"Status: Error - {payload}")
                elif kind == "__INFO__":
                    self.log(f"[INFO] {payload}")
                    self.lbl_status.config(text=f"Status: Connected - {payload}")
                elif kind == "__SENT__":
                    self.log(f"Sent >>> {payload}")
                elif kind == "__CLOSED__":
                    self.log("[INFO] Serial connection closed")
                    self.connected = False
                    self.btn_connect.config(text="Connect")
                    self.lbl_status.config(text="Status: Disconnected")
                    
        except queue.Empty:
            pass
        self.root.after(100, self.process_rx)

    def process_response(self, data: str):
        clean = clean_response(data)
        if not clean:
            return

        self.log(f"Received <<< {clean}")

        # Process DTC codes
        if "43" in clean:
            dtcs = extract_dtcs_from_response(clean)
            if dtcs:
                self.log("Error codes:")
                for code in dtcs:
                    desc = self.lookup_dtc(code) or "(no description found)"
                    self.log(f"  {code} - {desc}")
            else:
                self.log("No diagnostic trouble codes found")

        # Process PID responses
        if "41" in clean:
            self.process_pid_data(clean)

        # Process adapter info
        if "ELM327" in clean.upper():
            self.log(f"Adapter identified: {clean}")
            self.lbl_status.config(text=f"Status: Connected - {clean}")

        # Handle common responses
        if "OK" in clean:
            self.log("Command executed successfully")
        elif "NO DATA" in clean.upper():
            self.log("[WARNING] No data received - vehicle may be off or PID not supported")
        elif "UNABLE TO CONNECT" in clean.upper():
            self.log("[ERROR] Unable to connect to vehicle - check ignition and connection")
        elif "ERROR" in clean.upper():
            self.log(f"[ERROR] Adapter reported error: {clean}")

    def process_pid_data(self, data: str):
        # RPM (PID 0C)
        d = parse_pid_response(data, "0C")
        if d:
            rpm = calc_rpm(d)
            if rpm is not None:
                self.lbl_rpm.config(text=f"{rpm:.0f}")
                self.log(f"RPM: {rpm:.0f} rpm")

        # Vehicle Speed (PID 0D)
        d = parse_pid_response(data, "0D")
        if d:
            speed = calc_speed(d)
            if speed is not None:
                self.lbl_speed.config(text=f"{speed:.0f}")
                self.log(f"Speed: {speed:.0f} km/h")

        # Coolant Temperature (PID 05)
        d = parse_pid_response(data, "05")
        if d:
            temp = calc_temp(d)
            if temp is not None:
                self.lbl_temp.config(text=f"{temp:.0f}")
                self.log(f"CoolantTemp: {temp:.0f} °C")

        # Engine Load (PID 04)
        d = parse_pid_response(data, "04")
        if d:
            load = calc_engine_load(d)
            if load is not None:
                self.lbl_load.config(text=f"{load:.0f}")
                self.log(f"EngineLoad: {load:.0f} %")

        # Battery Voltage (PID 42)
        d = parse_pid_response(data, "42")
        if d:
            voltage = calc_voltage(d)
            if voltage is not None:
                self.lbl_voltage.config(text=f"{voltage:.2f}")
                self.log(f"Control Module Voltage: {voltage:.2f} V")

    def load_dtc_map(self):
# DTCs from Pcodes list (format: o3script)
        path = resource_path(self.o3script_filename)
        new_map = {}
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                reading = False
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
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
            self.log(f"[WARNING] DTC code list not found: {self.o3script_filename}")
            self.dtc_map = {}
            return
        except Exception as e:
            self.log(f"[WARNING] Failed to load DTC codes: {e}")
            self.dtc_map = {}
            return

        self.dtc_map = new_map
        self.log(f"DTC code list loaded: {len(self.dtc_map)} codes available")

    def lookup_dtc(self, code: str) -> str:
        return self.dtc_map.get(code.upper(), "")

if __name__ == "__main__":
    o3DIAG.show_splash()

    root = tk.Tk()
    app = o3DIAG(root)
    root.mainloop()

    
