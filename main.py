import sys
import keyboard
import pyautogui
from PyQt5.QtWidgets import QApplication

from config_manager import ConfigManager
from vision_core import VisionEngine
from input_controller import CombatInputController
from state_machine import BossFarmStateMachine
from gui_dashboard import MacroDashboardWindow

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.015

class EmergencyKillSwitch:
    def __init__(self, state_machine: BossFarmStateMachine, input_ctrl: CombatInputController):
        self.state_machine = state_machine
        self.input_ctrl = input_ctrl

    def register_hooks(self):
        try:
            keyboard.add_hotkey("f12", self.trigger_emergency_stop)
            keyboard.add_hotkey("f9", self.toggle_macro_state)
            print("[SAFETY] Hook registrati: Start/Stop=[F9] | Kill Switch=[F12]")
        except Exception as exc:
            print(f"[ERRORE HOOK] Esegui come Amministratore: {exc}")

    def trigger_emergency_stop(self):
        self.state_machine.stop()
        self.input_ctrl.release_all_keys()

    def toggle_macro_state(self):
        if self.state_machine.running:
            self.state_machine.stop()
            self.input_ctrl.release_all_keys()
        else:
            self.state_machine.start()

def main():
    config_mgr = ConfigManager("config.json")
    cfg = config_mgr.load_config()

    vision = VisionEngine(cfg)
    input_ctrl = CombatInputController(cfg)
    fsm = BossFarmStateMachine(cfg, vision, input_ctrl)

    safety = EmergencyKillSwitch(fsm, input_ctrl)
    safety.register_hooks()

    app = QApplication(sys.argv)
    dashboard = MacroDashboardWindow(cfg, config_mgr, fsm, vision, input_ctrl)
    dashboard.show()

    exit_code = app.exec_()

    fsm.stop()
    input_ctrl.release_all_keys()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()