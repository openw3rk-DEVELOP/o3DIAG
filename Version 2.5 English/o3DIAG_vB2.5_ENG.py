# -------------------------------------------
# o3DIAG in version Beta 2.5 / English 
# o3DIAG comes with ABSOLUTELY NO WARRANTY!
# -------------------------------------------
# Copyright (c) openw3rk INVENT
# Licensed under MIT-LICENSE
# -------------------------------------------
# https://o3diag.openw3rk.de
# https://openw3rk.de 
# -------------------------------------------
# Beta 2.5 - FULL ENGLISH VERSION
# -------------------------------------------

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

def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

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

class OBDCommunicator(threading.Thread):
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
class o3DIAG:
    ASCII_ART = r"""
                           ____     __      _____  ___   _______  ________
 ___  ___  ___ ___ _    __|_  /____/ /__   /  _/ |/ / | / / __/ |/ /_  __/
/ _ \/ _ \/ -_) _ \ |/|/ //_ </ __/  '_/  _/ //    /| |/ / _//    / / /   
\___/ .__/\__/_//_/__,__/____/_/ /_/\_\  /___/_/|_/ |___/___/_/|_/ /_/    
   /_/ o3DIAG Beta 2.5 - https://o3diag.openw3rk.de | https://openw3rk.de      
--------------------------------------------------------------------------

--> PLEASE NOTE THE INFO, WARN & DISCLAIMER BEFORE USING.   

"""
    def __init__(self, root):
        self.root = root
        root.title("o3DIAG (version Beta 2.5) (for OBD-II / ELM327)")
        root.geometry("1041x670")
        icon = tk.PhotoImage(file="o3DIAG_logo.png")
        root.iconphoto(True, icon)
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
        self.ent_baud.insert(0, "115200")
        ttk.Button(frm_conn, text="Refresh", command=self.refresh_ports).grid(row=0, column=4, padx=4)
        self.show_app_info = ttk.Button(frm_conn, text="Info & Warnings", command=self.info_warn)
        self.show_app_info.grid(row=0, column=5, padx=4)
        self.btn_connect = ttk.Button(frm_conn, text="Connect", command=self.toggle_connect)
        self.btn_connect.grid(row=0, column=6, padx=4)
        self.lbl_status = ttk.Label(frm_conn, text="Status: disconnected")
        self.lbl_status.grid(row=1, column=0, columnspan=7, sticky="w", pady=(6,0))
        frm_ctrl = ttk.Frame(root, padding=8)
        frm_ctrl.grid(row=1, column=0, sticky="ew")
        ttk.Button(frm_ctrl, text="Init Adapter", command=self.init_adapter).grid(row=0, column=0, padx=4, pady=2)
        ttk.Button(frm_ctrl, text="RPM", command=lambda: self.request_pid("010C")).grid(row=0, column=1, padx=4, pady=2)
        ttk.Button(frm_ctrl, text="Speed", command=lambda: self.request_pid("010D")).grid(row=0, column=2, padx=4, pady=2)
        ttk.Button(frm_ctrl, text="Temp", command=lambda: self.request_pid("0105")).grid(row=0, column=3, padx=4, pady=2)
        ttk.Button(frm_ctrl, text="Load", command=lambda: self.request_pid("0104")).grid(row=0, column=4, padx=4, pady=2)
        ttk.Button(frm_ctrl, text="Read Engine DTC", command=self.request_dtcs).grid(row=0, column=5, padx=4, pady=2)
        ttk.Button(frm_ctrl, text="Clear DTCs", command=self.clear_dtcs).grid(row=0, column=6, padx=4, pady=2)
        ttk.Button(frm_ctrl, text="Clear Log", command=self.clear_log).grid(row=0, column=7, padx=8, pady=2)
        ttk.Button(frm_ctrl, text="Reload P-Code List", command=self.load_dtc_map).grid(row=0, column=8, padx=4, pady=2)
        frm_log = ttk.Frame(root, padding=8)
        frm_log.grid(row=2, column=0, sticky="nsew")
        root.grid_rowconfigure(2, weight=1)
        root.grid_columnconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(frm_log, height=20, state="disabled", wrap="none")
        self.log_text.pack(expand=True, fill="both")
        self.show_ascii_art()
        frm_data = ttk.Frame(root, padding=8)
        frm_data.grid(row=3, column=0, sticky="ew")
        ttk.Label(frm_data, text="RPM:").grid(row=0, column=0, sticky="e")
        self.lbl_rpm = ttk.Label(frm_data, text="-"); self.lbl_rpm.grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(frm_data, text="Speed (km/h):").grid(row=0, column=2, sticky="e")
        self.lbl_speed = ttk.Label(frm_data, text="-"); self.lbl_speed.grid(row=0, column=3, sticky="w", padx=6)
        ttk.Label(frm_data, text="Coolant °C:").grid(row=0, column=4, sticky="e")
        self.lbl_temp = ttk.Label(frm_data, text="-"); self.lbl_temp.grid(row=0, column=5, sticky="w", padx=6)
        ttk.Label(frm_data, text="EngineLoad %:").grid(row=0, column=6, sticky="e")
        self.lbl_load = ttk.Label(frm_data, text="-"); self.lbl_load.grid(row=0, column=7, sticky="w", padx=6)
        self.rx_queue = queue.Queue()
        self.tx_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.thread = None
        self.connected = False
        self.dtc_map = {}
        self.o3script_filename = "o3DIAG_Pcodes_list_english.o3script"
        self.load_dtc_map()
        self.root.after(100, self.process_rx)
    def list_ports(self):
        return [p.device for p in serial.tools.list_ports.comports()]
    def refresh_ports(self):
        vals = self.list_ports()
        self.cmb_ports['values'] = vals
        if vals:
            self.cmb_ports.set(vals[0])
        self.log("Ports refreshed")

    def info_warn(self):
        self.log("\n\nINFO:\n-----\no3DIAG\nVersion Beta 2.5 / English\nCopyright (c) openw3rk INVENT\nFor OBD-II via. ELM327\n\n"
        "WARNING:\n--------\nActually developed for US vehicles, \nbut basically works with other OBD-capable vehicles as well.\n\n"
        "DISCLAIMER:\n-----------\nUSE AT YOUR OWN RISK!\nNO LIABILITY IS ASSUMED FOR ANY DAMAGES!\n"
        "o3DIAG comes with ABSOLUTELY NO WARRANTY!\n")

    def log(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state='normal')
        self.log_text.insert('end', f"[{ts}] {text}\n")
        self.log_text.see('end')
        self.log_text.configure(state='disabled')

    def clear_log(self):
        self.log_text.configure(state='normal')
        self.log_text.delete('1.0', tk.END)
        self.log_text.configure(state='disabled')
        self.show_ascii_art()

    def show_ascii_art(self):
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
            messagebox.showwarning("Baud PANIC", "Wrong Baudrate")
            return
        if not port:
            messagebox.showwarning("Port PANIC", "No port selected")
            return
        self.stop_event.clear()
        self.thread = OBDCommunicator(port, baud, self.rx_queue, self.tx_queue, self.stop_event)
        self.thread.start()
        self.connected = True
        self.btn_connect.config(text="Disconnect")
        self.lbl_status.config(text=f"Status: connected to {port} @ {baud}")
        self.log(f"Connecting to {port} @ {baud} ...")

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
        self.log(f">>> {cmd}")

    def init_adapter(self):
        if not self.connected:
            self.log("[PANIC] Not connected: please connect first.")
            return
        cmds = ["AT Z","AT E0","AT L0","AT S0","AT H0","AT SP 0","AT DP"]
        self.log("Init Adapter …")
        for c in cmds:
            self.send_command(c)
            time.sleep(0.2)

    def request_pid(self, pidcmd: str):
        self.send_command(pidcmd)

    def request_dtcs(self):
        self.send_command("03")

    def clear_dtcs(self):
        if messagebox.askyesno("WARNING", "Really clear stored trouble codes? (OBD-II Mode 04)"):
            self.send_command("04")

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
        self.log(f"<< {clean}")

        d = parse_pid_response(clean, "0C")
        if d:
            rpm = calc_rpm(d)
            if rpm is not None:
                self.lbl_rpm.config(text=f"{rpm:.0f}")

        d = parse_pid_response(clean, "0D")
        if d:
            sp = calc_speed(d)
            if sp is not None:
                self.lbl_speed.config(text=f"{sp:.0f}")

        d = parse_pid_response(clean, "05")
        if d:
            t = calc_temp(d)
            if t is not None:
                self.lbl_temp.config(text=f"{t:.0f}")

        d = parse_pid_response(clean, "04")
        if d:
            l = calc_engine_load(d)
            if l is not None:
                self.lbl_load.config(text=f"{l:.0f}")

        if "43" in clean:
            dtcs = extract_dtcs_from_response(clean)

            if not dtcs:
                dtcs = ["P0000"]  

            self.log("Error codes:")
            for code in dtcs:
                desc = self.lookup_dtc(code) or "(no description found)"
                self.log(f"  {code} – {desc}")

        if "NO DATA" in clean.upper():
            self.log("PANIC: NO DATA – PID/Mode not supported or no current values.")
    def load_dtc_map(self):
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
            self.log(f"P-Code list not found: {self.o3script_filename}")
            self.dtc_map = {}
            return
        except Exception as e:
            self.log(f"P-Code list could not be read, o3script syntax error?: {e}")
            self.dtc_map = {}
            return

        self.dtc_map = new_map
        self.log(f"P-Code list (English) loaded: {len(self.dtc_map)} lines\n")

    def lookup_dtc(self, code: str) -> str:
        return self.dtc_map.get(code.upper(), "")

if __name__ == "__main__":
    root = tk.Tk()
    app = o3DIAG(root)
    root.mainloop()
