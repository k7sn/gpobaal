# ==============================================================================
# FILE: gpo_macro/main.py
# ==============================================================================

"""
================================================================================
GPO EXTERNAL VISION MACRO - ENTRY POINT (main.py)
================================================================================
Architettura puramente esterna basata su Computer Vision (mss + OpenCV) e
simulazione hardware di input (PyAutoGUI + pynput + keyboard).
Supporta il compilatore PyInstaller (--onefile) tramite resource_path().

Autore: GPO External Vision Macro Studio
Profilo Attivo: True Demon Baal (Halloween Boss) (Boss: True Demon Baal)
================================================================================
"""

import os
import sys
import keyboard
import pyautogui
from PyQt5.QtWidgets import QApplication

from config_manager import ConfigManager
from vision_core import VisionEngine
from input_controller import CombatInputController
from state_machine import BossFarmStateMachine
from gui_dashboard import MacroDashboardWindow


# Configurazione di sicurezza globale PyAutoGUI
# Spostare il mouse nell'angolo superiore sinistro (0,0) interrompe istantaneamente tutto
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.015


def resource_path(relative_path: str) -> str:
    """
    Risolve il percorso reale dei file (es. assets/templates) sia durante
    l'esecuzione da codice sorgente (.py) sia dentro l'eseguibile compilato (.exe)
    creato da PyInstaller (che estrae i file in sys._MEIPASS).
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


class EmergencyKillSwitch:
    """
    Gestore hardware indipendente per l'arresto d'emergenza (F12).
    Gira su un hook a basso livello per fermare il loop anche se la finestra non ha il focus.
    """
    def __init__(self, state_machine: BossFarmStateMachine, input_ctrl: CombatInputController):
        self.state_machine = state_machine
        self.input_ctrl = input_ctrl
        self.kill_hotkey = "f12"
        self.toggle_hotkey = "f9"

    def register_hooks(self):
        try:
            keyboard.add_hotkey(self.kill_hotkey, self.trigger_emergency_stop)
            keyboard.add_hotkey(self.toggle_hotkey, self.toggle_macro_state)
            print(f"[SAFETY] Hook registrati: Start/Stop=[F9] | Kill Switch=[F12]")
        except Exception as exc:
            print(f"[ERRORE HOOK] Impossibile registrare gli hotkey globali (esegui come Amministratore): {exc}")

    def trigger_emergency_stop(self):
        print("\n[EMERGENZA] Kill-Switch attivato dall'utente! Rilascio immediato di tutti i tasti...")
        self.state_machine.stop()
        self.input_ctrl.release_all_keys()

    def toggle_macro_state(self):
        if self.state_machine.running:
            print("[HOTKEY] Pausa richiesta tramite tasto rapido.")
            self.state_machine.stop()
            self.input_ctrl.release_all_keys()
        else:
            print("[HOTKEY] Avvio macro richiesto tramite tasto rapido.")
            self.state_machine.start()


def main():
    # 1. Caricamento configurazione JSON
    config_mgr = ConfigManager("config.json")
    cfg = config_mgr.load_config()

    # 2. Inizializzazione moduli Core (Visione con supporto .exe, Input, Macchina a Stati)
    templates_dir = resource_path(os.path.join("assets", "templates"))
    vision = VisionEngine(cfg, assets_dir=templates_dir)
    input_ctrl = CombatInputController(cfg)
    fsm = BossFarmStateMachine(cfg, vision, input_ctrl)

    # 3. Registrazione Kill-Switch d'emergenza
    safety = EmergencyKillSwitch(fsm, input_ctrl)
    safety.register_hooks()

    # 4. Avvio Interfaccia Grafica PyQt5 nel Main Thread
    app = QApplication(sys.argv)
    dashboard = MacroDashboardWindow(cfg, config_mgr, fsm, vision, input_ctrl)
    dashboard.show()

    exit_code = app.exec_()

    # Pulizia di sicurezza alla chiusura dell'applicazione
    fsm.stop()
    input_ctrl.release_all_keys()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
