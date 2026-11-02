import time
import threading
import pyautogui
from enum import Enum
from typing import Callable, Optional, Dict, Any
from vision_core import VisionEngine
from input_controller import CombatInputController

class FarmState(Enum):
    IDLE_SEARCH = "STATO 1: IDLE / RICERCA BOSS"
    COMBAT = "STATO 2: COMBATTIMENTO ATTIVO"

class BossFarmStateMachine:
    def __init__(self, config: Dict[str, Any], vision: VisionEngine, input_ctrl: CombatInputController):
        self.config = config
        self.vision = vision
        self.input_ctrl = input_ctrl
        self.current_state: FarmState = FarmState.IDLE_SEARCH
        self.running: bool = False
        self._worker_thread: Optional[threading.Thread] = None
        self.on_status_update: Optional[Callable[[str, str, float, float], None]] = None

    def start(self):
        if self.running: return
        self.running = True
        self._worker_thread = threading.Thread(target=self._run_game_loop, daemon=True)
        self._worker_thread.start()

    def stop(self):
        self.running = False
        self.input_ctrl.release_all_keys()
        self._emit_update("MACRO FERMATA", "In attesa di avvio dall'utente", 0.0, 0.0)

    def _emit_update(self, state_label: str, action_detail: str, boss_hp: float, metric: float):
        if self.on_status_update:
            try:
                self.on_status_update(state_label, action_detail, boss_hp, metric)
            except Exception:
                pass

    def _run_game_loop(self):
        fps_limit = max(5, int(self.config["vision"].get("capture_fps_limit", 30)))
        frame_interval = 1.0 / float(fps_limit)
        try:
            while self.running:
                loop_start = time.time()
                if self.current_state == FarmState.IDLE_SEARCH:
                    self._handle_idle_state()
                elif self.current_state == FarmState.COMBAT:
                    self._handle_combat_state()
                elapsed = time.time() - loop_start
                time.sleep(max(0.01, frame_interval - elapsed))
        except pyautogui.FailSafeException:
            self.stop()
        except Exception:
            self.stop()

    def _handle_idle_state(self):
        boss_present, boss_hp = self.vision.detect_boss_presence_and_hp()
        target_found, _, _, _ = self.vision.locate_boss_target_on_screen()

        if (boss_present and boss_hp > 0) or target_found:
            self.current_state = FarmState.COMBAT
            return

        self.input_ctrl.rotate_camera_search()
        self._emit_update(self.current_state.value, "Scansione Boss in corso...", 0.0, 0.0)

    def _handle_combat_state(self):
        boss_present, boss_hp = self.vision.detect_boss_presence_and_hp()
        target_found, coords, offset_x, boss_area = self.vision.locate_boss_target_on_screen()

        if not boss_present and not target_found:
            self.input_ctrl.equipped_current_life = False
            self.current_state = FarmState.IDLE_SEARCH
            return

        self.input_ctrl.equip_selected_slot()

        target_dmg = float(self.config.get("player", {}).get("stop_at_damage_percent", 5.0))
        current_dmg = self.vision.get_player_damage_percentage()
        if current_dmg >= target_dmg:
            self.input_ctrl.release_all_keys()
            self._emit_update("TARGET DANNO RAGGIUNTO", f"Danno: {current_dmg:.2f}%. In attesa sconfitta...", boss_hp, boss_area)
            return

        if target_found and coords is not None:
            ready_hud_map = self.vision.scan_ready_skills_on_hud()
            self.input_ctrl.follow_boss_movement(coords, offset_x, boss_area)
            action_msg = self.input_ctrl.execute_available_skill(coords, ready_hud_map)
            self._emit_update(self.current_state.value, f"{action_msg} | Danno: {current_dmg:.2f}%", max(boss_hp, 10.0), boss_area)
        else:
            self.input_ctrl.rotate_camera_search()
            self._emit_update(self.current_state.value, "Rotazione verso il bersaglio...", boss_hp, 0.0)