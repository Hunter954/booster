import ctypes
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import psutil
import requests
import customtkinter as ctk


APP_DIR = Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "FRAMEBoost"
APP_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = Path(__file__).parent / "config.json"
SESSION_FILE = APP_DIR / "session.json"
REPORT_FILE = APP_DIR / "last_report.json"
NVIDIA_PRESET_FILE = APP_DIR / "nvidia_preset_pubg.json"

PUBG_PROCESS = "TslGame.exe"

# Não fecha navegador nem Discord automaticamente.
PROTECTED_PROCESSES = {
    "Discord.exe",
    "chrome.exe",
    "msedge.exe",
    "brave.exe",
    "opera.exe",
    "firefox.exe",
    "WhatsApp.exe",
    "Telegram.exe"
}

SAFE_SERVICES_DEFAULT = [
    "SysMain",
    "WSearch",
    "DiagTrack",
    "MapsBroker",
    "XblAuthManager",
    "XblGameSave",
    "XboxNetApiSvc"
]


def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {"API_BASE_URL": "http://127.0.0.1:8000", "APP_NAME": "FRAME Boost PUBG"}


CONFIG = load_config()
API_BASE_URL = CONFIG.get("API_BASE_URL", "http://127.0.0.1:8000")


def is_windows():
    return os.name == "nt"


def is_admin():
    if not is_windows():
        return False
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_cmd(command):
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), 1


def get_machine_guid():
    out, err, code = run_cmd(r'reg query "HKLM\SOFTWARE\Microsoft\Cryptography" /v MachineGuid')
    if code == 0 and "MachineGuid" in out:
        return out.split()[-1].strip()
    return str(uuid.getnode())


def get_bios_uuid():
    out, err, code = run_cmd("wmic csproduct get uuid")
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    if len(lines) >= 2 and "UUID" not in lines[1]:
        return lines[1]
    return "unknown-bios"


def get_hwid_hash():
    raw = f"{get_machine_guid()}|{get_bios_uuid()}|{platform.node()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def detect_gpu():
    out, err, code = run_cmd("nvidia-smi --query-gpu=name,driver_version --format=csv,noheader")
    if code == 0 and out:
        first = out.splitlines()[0]
        return first.split(",")[0].strip()

    out, err, code = run_cmd("wmic path win32_VideoController get name")
    lines = [x.strip() for x in out.splitlines() if x.strip() and "Name" not in x]
    if lines:
        return lines[0]
    return "GPU não detectada"


def snapshot():
    cpu = []
    for _ in range(4):
        cpu.append(psutil.cpu_percent(interval=0.35))

    ram = psutil.virtual_memory()
    return {
        "time": datetime.now().isoformat(),
        "cpu_avg": round(sum(cpu) / len(cpu), 1),
        "ram_percent": ram.percent,
        "ram_free_gb": round(ram.available / (1024 ** 3), 2),
        "process_count": len(psutil.pids())
    }


def activate_power_plan():
    high_perf = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
    out, err, code = run_cmd(f"powercfg /setactive {high_perf}")
    if code != 0:
        ultimate = "e9a42b02-d5df-448d-aa00-03f14749eb61"
        run_cmd(f"powercfg -duplicatescheme {ultimate}")
        out, err, code = run_cmd(f"powercfg /setactive {ultimate}")
    return code == 0


def disable_game_dvr_enable_game_mode():
    commands = [
        r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR" /v AppCaptureEnabled /t REG_DWORD /d 0 /f',
        r'reg add "HKCU\System\GameConfigStore" /v GameDVR_Enabled /t REG_DWORD /d 0 /f',
        r'reg add "HKCU\Software\Microsoft\GameBar" /v ShowStartupPanel /t REG_DWORD /d 0 /f',
        r'reg add "HKCU\Software\Microsoft\GameBar" /v AllowAutoGameMode /t REG_DWORD /d 1 /f',
        r'reg add "HKCU\Software\Microsoft\GameBar" /v AutoGameModeEnabled /t REG_DWORD /d 1 /f',
    ]
    for cmd in commands:
        run_cmd(cmd)


def stop_services(services):
    results = {}
    for service in services:
        out, err, code = run_cmd(f'sc stop "{service}"')
        results[service] = code
    return results


def clean_temp():
    removed = 0
    for temp in [os.environ.get("TEMP"), os.environ.get("TMP"), r"C:\Windows\Temp"]:
        if not temp:
            continue
        path = Path(temp)
        if not path.exists():
            continue
        for item in path.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink()
                    removed += 1
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    removed += 1
            except Exception:
                pass
    return removed


def set_pubg_priority():
    applied = False
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] == PUBG_PROCESS:
                p = psutil.Process(proc.info["pid"])
                p.nice(psutil.HIGH_PRIORITY_CLASS)
                applied = True
        except Exception:
            pass
    return applied


def prepare_nvidia_preset(preset_config, gpu_name):
    nvidia = preset_config.get("nvidia", {})
    nvidia["detected_gpu"] = gpu_name
    nvidia["note"] = (
        "Preset preparado. A aplicação automática real via NVIDIA será adicionada em módulo separado. "
        "Este MVP não usa gambiarra no registro para evitar quebrar vídeo/resolução."
    )
    NVIDIA_PRESET_FILE.write_text(json.dumps(nvidia, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(NVIDIA_PRESET_FILE)


class BoostApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(CONFIG.get("APP_NAME", "FRAME Boost PUBG"))
        self.geometry("980x650")
        self.minsize(900, 600)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.token = None
        self.user = None
        self.license_info = None
        self.presets = []

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color="#09090b")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)

        self.logo = ctk.CTkLabel(
            self.sidebar,
            text="FRAME\nBOOST",
            font=ctk.CTkFont(size=30, weight="bold"),
            text_color="#ef233c"
        )
        self.logo.grid(row=0, column=0, padx=24, pady=(28, 10), sticky="w")

        self.status_label = ctk.CTkLabel(
            self.sidebar,
            text="Não autenticado",
            text_color="#a1a1aa",
            justify="left"
        )
        self.status_label.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="w")

        self.btn_login = ctk.CTkButton(self.sidebar, text="Login", command=self.show_login, fg_color="#ef233c")
        self.btn_login.grid(row=2, column=0, padx=24, pady=8, sticky="ew")

        self.btn_dashboard = ctk.CTkButton(self.sidebar, text="Dashboard", command=self.show_dashboard, fg_color="#27272f")
        self.btn_dashboard.grid(row=3, column=0, padx=24, pady=8, sticky="ew")

        self.btn_boost = ctk.CTkButton(self.sidebar, text="Aplicar Booster", command=self.apply_boost_thread, fg_color="#27272f")
        self.btn_boost.grid(row=4, column=0, padx=24, pady=8, sticky="ew")

        self.btn_report = ctk.CTkButton(self.sidebar, text="Relatório", command=self.show_report, fg_color="#27272f")
        self.btn_report.grid(row=5, column=0, padx=24, pady=8, sticky="ew")

        self.footer = ctk.CTkLabel(
            self.sidebar,
            text="Seguro: não fecha\nDiscord/navegador.",
            text_color="#71717a",
            justify="left"
        )
        self.footer.grid(row=9, column=0, padx=24, pady=24, sticky="sw")

        self.main = ctk.CTkFrame(self, fg_color="#0b0b0f")
        self.main.grid(row=0, column=1, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.show_login()

    def clear_main(self):
        for child in self.main.winfo_children():
            child.destroy()

    def log_box(self, parent):
        box = ctk.CTkTextbox(parent, height=260, fg_color="#101014", text_color="#e4e4e7")
        box.pack(fill="both", expand=True, padx=24, pady=16)
        return box

    def show_login(self):
        self.clear_main()
        frame = ctk.CTkFrame(self.main, fg_color="#0b0b0f")
        frame.pack(fill="both", expand=True, padx=40, pady=40)

        ctk.CTkLabel(frame, text="Entrar no FRAME Boost", font=ctk.CTkFont(size=32, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(frame, text="Use o login do cliente e a chave criada no painel admin.", text_color="#a1a1aa").pack(anchor="w", pady=(4, 26))

        self.email_entry = ctk.CTkEntry(frame, placeholder_text="E-mail", width=420, height=44)
        self.email_entry.pack(anchor="w", pady=8)

        self.password_entry = ctk.CTkEntry(frame, placeholder_text="Senha", show="*", width=420, height=44)
        self.password_entry.pack(anchor="w", pady=8)

        self.key_entry = ctk.CTkEntry(frame, placeholder_text="Chave de licença", width=420, height=44)
        self.key_entry.pack(anchor="w", pady=8)

        ctk.CTkButton(frame, text="Validar e desbloquear", command=self.login_thread, width=420, height=44, fg_color="#ef233c").pack(anchor="w", pady=18)

        self.login_log = ctk.CTkTextbox(frame, width=620, height=180, fg_color="#101014")
        self.login_log.pack(anchor="w", pady=8)
        self.login_log.insert("end", f"API: {API_BASE_URL}\n")
        self.login_log.insert("end", f"GPU detectada: {detect_gpu()}\n")
        self.login_log.insert("end", f"Administrador: {'Sim' if is_admin() else 'Não'}\n")

    def login_thread(self):
        threading.Thread(target=self.do_login, daemon=True).start()

    def do_login(self):
        email = self.email_entry.get().strip()
        password = self.password_entry.get().strip()
        key = self.key_entry.get().strip().upper()

        self.login_log.insert("end", "\nConectando...\n")

        try:
            r = requests.post(f"{API_BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
            if r.status_code != 200:
                self.login_log.insert("end", f"Erro login: {r.text}\n")
                return

            data = r.json()
            self.token = data["access_token"]
            self.user = data["user"]

            headers = {"Authorization": f"Bearer {self.token}"}
            payload = {
                "license_key": key,
                "hwid_hash": get_hwid_hash(),
                "machine_name": platform.node(),
                "gpu_name": detect_gpu()
            }
            r2 = requests.post(f"{API_BASE_URL}/api/client/activate", json=payload, headers=headers, timeout=15)
            if r2.status_code != 200:
                self.login_log.insert("end", f"Erro ativação: {r2.text}\n")
                return

            self.license_info = r2.json()
            SESSION_FILE.write_text(json.dumps({
                "token": self.token,
                "user": self.user,
                "license": self.license_info,
                "license_key": key,
                "api": API_BASE_URL
            }, indent=2), encoding="utf-8")

            self.login_log.insert("end", "Booster desbloqueado com sucesso.\n")
            self.status_label.configure(text=f"{self.user['name']}\nPlano: {self.license_info['plan']}")
            self.fetch_presets()
            self.show_dashboard()

        except Exception as e:
            self.login_log.insert("end", f"Falha: {e}\n")

    def fetch_presets(self):
        if not self.token:
            return
        headers = {"Authorization": f"Bearer {self.token}"}
        r = requests.get(f"{API_BASE_URL}/api/client/presets?game=pubg", headers=headers, timeout=15)
        if r.status_code == 200:
            self.presets = r.json().get("presets", [])

    def show_dashboard(self):
        self.clear_main()
        frame = ctk.CTkFrame(self.main, fg_color="#0b0b0f")
        frame.pack(fill="both", expand=True, padx=40, pady=40)

        ctk.CTkLabel(frame, text="Dashboard", font=ctk.CTkFont(size=32, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(frame, text="Resumo do PC e licença.", text_color="#a1a1aa").pack(anchor="w", pady=(4, 24))

        cards = ctk.CTkFrame(frame, fg_color="#0b0b0f")
        cards.pack(fill="x")

        info = [
            ("GPU", detect_gpu()),
            ("Windows", platform.platform()),
            ("Admin", "Sim" if is_admin() else "Não"),
            ("Plano", self.license_info.get("plan") if self.license_info else "Não ativado")
        ]

        for title, value in info:
            card = ctk.CTkFrame(cards, fg_color="#141418", corner_radius=18)
            card.pack(side="left", fill="both", expand=True, padx=8)
            ctk.CTkLabel(card, text=title, text_color="#a1a1aa").pack(anchor="w", padx=18, pady=(16, 4))
            ctk.CTkLabel(card, text=str(value)[:42], font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=18, pady=(0, 16))

        box = ctk.CTkTextbox(frame, height=260, fg_color="#101014")
        box.pack(fill="both", expand=True, pady=24)
        box.insert("end", "Presets disponíveis:\n\n")
        for p in self.presets:
            box.insert("end", f"- {p['name']} [{p['plan_required']}]\n  {p.get('description') or ''}\n\n")
        if not self.presets:
            box.insert("end", "Faça login para carregar os presets.\n")

    def apply_boost_thread(self):
        threading.Thread(target=self.apply_boost, daemon=True).start()

    def apply_boost(self):
        self.clear_main()
        frame = ctk.CTkFrame(self.main, fg_color="#0b0b0f")
        frame.pack(fill="both", expand=True, padx=40, pady=40)

        ctk.CTkLabel(frame, text="Aplicando Booster", font=ctk.CTkFont(size=32, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(frame, text="Modo seguro: não fecha navegador, Discord ou apps pessoais.", text_color="#a1a1aa").pack(anchor="w", pady=(4, 18))
        box = self.log_box(frame)

        def log(msg):
            box.insert("end", msg + "\n")
            box.see("end")
            self.update_idletasks()

        if not is_windows():
            log("Este app é apenas para Windows.")
            return

        if not is_admin():
            log("Abra o app como Administrador para aplicar todas as otimizações.")
            return

        if not self.token:
            log("Faça login antes de aplicar o booster.")
            return

        self.fetch_presets()
        if not self.presets:
            log("Nenhum preset disponível.")
            return

        preset = self.presets[0]
        config = preset.get("config", {})
        win = config.get("windows", {})

        log(f"Preset: {preset['name']}")
        log(f"GPU: {detect_gpu()}")
        log("Coletando performance antes...")
        before = snapshot()

        if win.get("power_plan"):
            log("Ativando plano de alto desempenho...")
            log("OK" if activate_power_plan() else "Não foi possível alterar o plano.")

        if win.get("disable_game_dvr") or win.get("enable_game_mode"):
            log("Desativando Game DVR e ativando Modo de Jogo...")
            disable_game_dvr_enable_game_mode()

        services = win.get("stop_services") or SAFE_SERVICES_DEFAULT
        log("Parando serviços temporários seguros...")
        service_results = stop_services(services)
        for service, code in service_results.items():
            log(f"- {service}: {'comando enviado' if code == 0 else 'ignorado/já parado'}")

        if win.get("clean_temp"):
            log("Limpando temporários...")
            removed = clean_temp()
            log(f"Itens limpos: {removed}")

        log("Aplicando prioridade no PUBG se estiver aberto...")
        if set_pubg_priority():
            log("PUBG encontrado. Prioridade alta aplicada.")
        else:
            log("PUBG não está aberto. Abra o jogo e rode novamente se quiser aplicar prioridade.")

        log("Preparando preset NVIDIA baseado na GPU detectada...")
        preset_path = prepare_nvidia_preset(config, detect_gpu())
        log(f"Preset NVIDIA salvo em: {preset_path}")

        log("Coletando performance depois...")
        after = snapshot()

        report = {
            "preset": preset["name"],
            "before": before,
            "after": after,
            "gpu": detect_gpu(),
            "windows": platform.platform(),
            "created_at": datetime.now().isoformat(),
            "note": "MVP seguro. Não fecha Discord/navegador. Não altera memória, anti-cheat ou arquivos do jogo."
        }
        REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        log("")
        log("Finalizado.")
        log(f"CPU antes: {before['cpu_avg']}% | depois: {after['cpu_avg']}%")
        log(f"RAM antes: {before['ram_percent']}% | depois: {after['ram_percent']}%")
        log(f"RAM livre antes: {before['ram_free_gb']} GB | depois: {after['ram_free_gb']} GB")
        log(f"Relatório salvo em: {REPORT_FILE}")

    def show_report(self):
        self.clear_main()
        frame = ctk.CTkFrame(self.main, fg_color="#0b0b0f")
        frame.pack(fill="both", expand=True, padx=40, pady=40)

        ctk.CTkLabel(frame, text="Relatório", font=ctk.CTkFont(size=32, weight="bold")).pack(anchor="w")
        box = self.log_box(frame)

        if REPORT_FILE.exists():
            box.insert("end", REPORT_FILE.read_text(encoding="utf-8"))
        else:
            box.insert("end", "Nenhum relatório gerado ainda.")


if __name__ == "__main__":
    app = BoostApp()
    app.mainloop()
