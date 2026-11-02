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
    DEATH_RECOVERY = "STATO 3: GESTIONE MORTE & RITORNO"
    SERVER_HOP = "STATO 4: SERVER HOP AUTOMATICO"


class BossFarmStateMachine:
    def __init__(
        self,
        config: Dict[str, Any],
        vision: VisionEngine,
        input_ctrl: CombatInputController
    ):
        self.config = config
        self.vision = vision
        self.input_ctrl = input_ctrl

        self.current_state: FarmState = FarmState.IDLE_SEARCH
        self.running: bool = False
        self._worker_thread: Optional[threading.Thread] = None
        self.idle_start_time: float = time.time()
        self.boss_kills_count: int = 0
        self.on_status_update: Optional[Callable[[str, str, float, float], None]] = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.idle_start_time = time.time()
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

                if self.vision.detect_character_death():
                    self.current_state = FarmState.DEATH_RECOVERY

                if self.current_state == FarmState.IDLE_SEARCH:
                    self._handle_idle_state()
                elif self.current_state == FarmState.COMBAT:
                    self._handle_combat_state()
                elif self.current_state == FarmState.DEATH_RECOVERY:
                    self._handle_death_recovery_state()
                elif self.current_state == FarmState.SERVER_HOP:
                    self._handle_server_hop_state()

                elapsed = time.time() - loop_start
                time.sleep(max(0.01, frame_interval - elapsed))

        except pyautogui.FailSafeException:
            print("[FAILSAFE] Cursore nell'angolo di sicurezza (0,0)! Arresto immediato.")
            self.stop()
        except Exception as exc:
            print(f"[ERRORE CRITICO LOOP] Eccezione catturata: {exc}")
            self.stop()

    def _handle_idle_state(self):
        boss_present, boss_hp = self.vision.detect_boss_presence_and_hp()
        target_found, coords, offset_x, boss_area = self.vision.locate_boss_target_on_screen()

        if (boss_present and boss_hp > 0) or target_found:
            self.current_state = FarmState.COMBAT
            return

        idle_elapsed = time.time() - self.idle_start_time
        max_idle = float(self.config["server_hop"]["max_idle_seconds"])

        if self.config["server_hop"]["enabled"] and idle_elapsed >= max_idle:
            self.current_state = FarmState.SERVER_HOP
            return

        self.input_ctrl.rotate_camera_search()
        self._emit_update(
            self.current_state.value,
            f"Scansione Boss (True Demon Baal) in corso ({int(idle_elapsed)}s / {int(max_idle)}s)",
            0.0,
            0.0
        )

    def _handle_combat_state(self):
        boss_present, boss_hp = self.vision.detect_boss_presence_and_hp()
        target_found, coords, offset_x, boss_area = self.vision.locate_boss_target_on_screen()

        if not boss_present and not target_found:
            self.boss_kills_count += 1
            self.input_ctrl.equipped_current_life = False
            self.idle_start_time = time.time()
            self.current_state = FarmState.IDLE_SEARCH
            return

        # 1. Equipaggia lo slot Frutto/Arma selezionato nella GUI
        self.input_ctrl.equip_selected_slot()

        # 2. Controllo "Damage Progress" tramite OCR (Stop automatico al 5% o soglia scelta)
        target_dmg = float(self.config.get("player", {}).get("stop_at_damage_percent", 5.0))
        current_dmg = self.vision.get_player_damage_percentage()
        if current_dmg >= target_dmg:
            self.input_ctrl.release_all_keys()
            self._emit_update(
                "TARGET DANNO RAGGIUNTO",
                f"Danno attuale: {current_dmg:.2f}% (Soglia: {target_dmg:.1f}%). In attesa sconfitta Boss...",
                boss_hp,
                boss_area
            )
            # Mettiamo in pausa gli attacchi ma non fermiamo la macro del tutto,
            # così alla morte del boss ricomincia automaticamente l'IDLE_SEARCH.
            return

        if target_found and coords is not None:
            # 3. Legge quali mosse sono pronte (non rosse in cooldown)
            ready_hud_map = self.vision.scan_ready_skills_on_hud()

            # 4. Insegue il Boss (A/D laterale, W per avvicinarsi, Q per Dash)
            self.input_ctrl.follow_boss_movement(coords, offset_x, boss_area)

            # 5. Lancia la prima mossa disponibile
            action_msg = self.input_ctrl.execute_available_skill(coords, ready_hud_map)
            self._emit_update(
                self.current_state.value,
                f"{action_msg} | Tuo Danno: {current_dmg:.2f}%",
                max(boss_hp, 10.0),
                boss_area
            )
        else:
            self.input_ctrl.rotate_camera_search()
            self._emit_update(
                self.current_state.value,
                "Boss attivo ma fuori visuale: rotazione telecamera verso il bersaglio...",
                boss_hp,
                0.0
            )

    def _handle_death_recovery_state(self):
        self._emit_update(self.current_state.value, "Attesa completamento respawn (6.5s)...", 0.0, 0.0)
        self.input_ctrl.release_all_keys()
        time.sleep(6.5)

        waypoints = self.config.get("death_waypoints", [])
        self._emit_update(self.current_state.value, f"Esecuzione {len(waypoints)} waypoints verso l'arena...", 0.0, 0.0)
        self.input_ctrl.run_waypoint_recovery_path(waypoints)

        self.idle_start_time = time.time()
        self.current_state = FarmState.IDLE_SEARCH

    def _handle_server_hop_state(self):
        self._emit_update(self.current_state.value, "Esecuzione sequenza cambio server Roblox...", 0.0, 0.0)
        self.input_ctrl.release_all_keys()
        self.input_ctrl.perform_roblox_server_hop()
        self.idle_start_time = time.time()
        self.current_state = FarmState.IDLE_SEARCH