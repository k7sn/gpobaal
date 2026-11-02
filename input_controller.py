# ==============================================================================
# FILE: gpo_macro/input_controller.py
# ==============================================================================

"""
================================================================================
MODULO 3: SISTEMA DI COMBATTIMENTO E INPUT SICURO (input_controller.py)
================================================================================
Simula gli input di tastiera e mouse tramite PyAutoGUI e Pynput.
Combina la lettura visiva della barra skill sullo schermo con i timer interni,
mira automaticamente al centroide del Boss e lancia l'hotkey assegnato.
"""

import time
import pyautogui
from pynput.keyboard import Controller as KeyController
from pynput.mouse import Controller as MouseController
from typing import Dict, Any, Tuple, List, Optional


class CombatInputController:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.keyboard = KeyController()
        self.mouse = MouseController()
        self.last_used_timestamps: Dict[str, float] = {}
        self.held_keys: set = set()

    def press_key_safe(self, key_str: str, hold_duration: float = 0.06):
        """Preme e rilascia un tasto in modo protetto registrando lo stato."""
        try:
            self.held_keys.add(key_str)
            pyautogui.keyDown(key_str)
            time.sleep(max(0.02, hold_duration))
            pyautogui.keyUp(key_str)
            self.held_keys.discard(key_str)
        except pyautogui.FailSafeException:
            self.release_all_keys()
            raise
        except Exception as exc:
            print(f"[ERRORE INPUT] Impossibile premere il tasto '{key_str}': {exc}")
            self.release_all_keys()

    def release_all_keys(self):
        """Rilascia forzatamente tutti i tasti di movimento e azione per sicurezza."""
        emergency_keys = ["w", "a", "s", "d", "space", "shift", "1", "2", "3", "4", "q", "e", "r", "z", "x", "c", "v"]
        for k in list(self.held_keys) + emergency_keys:
            try:
                pyautogui.keyUp(k)
            except Exception:
                pass
        self.held_keys.clear()

    def aim_at_target(self, target_coords: Tuple[int, int]):
        """
        Sposta il mirino del mouse direttamente sul baricentro del Boss (es. True Demon Baal)
        applicando l'offset verticale aim_offset_y prima di premere l'hotkey della mossa.
        """
        try:
            offset_y = int(self.config["combat"]["aim_offset_y"])
            sens = float(self.config["combat"]["camera_sensitivity"])
            tx = int(target_coords[0])
            ty = int(target_coords[1] + offset_y)

            cur_x, cur_y = pyautogui.position()
            dx = int((tx - cur_x) * sens)
            dy = int((ty - cur_y) * sens)

            pyautogui.moveRel(dx, dy, duration=0.04)
        except pyautogui.FailSafeException:
            self.release_all_keys()
            raise
        except Exception as exc:
            print(f"[ERRORE MIRA] {exc}")

    def adjust_spacing(self, current_distance_px: float):
        """Mantiene il personaggio all'interno del raggio ottimale."""
        combat_radius = float(self.config["combat"]["combat_radius_px"])
        safe_dist = float(self.config["combat"]["safe_distance_px"])

        if current_distance_px > combat_radius:
            self.press_key_safe("w", hold_duration=0.22)
        elif current_distance_px < safe_dist:
            self.press_key_safe("s", hold_duration=0.18)

    def execute_available_skill(
        self,
        current_distance_px: float,
        target_coords: Tuple[int, int],
        visual_ready_map: Optional[Dict[str, bool]] = None
    ) -> str:
        """
        1. Controlla quali mosse sono visivamente PRONTE sullo schermo (visual_ready_map)
           e hanno superato il tempo di ricarica.
        2. Verifica che la distanza del bersaglio sia nel range [min_range, max_range].
        3. Sposta la mira esattamente su target_coords e preme l'hotkey assegnato.
        """
        now = time.time()
        skills_cfg: Dict[str, Dict[str, Any]] = self.config.get("skills", {})
        global_delay_sec = float(self.config["combat"]["skill_global_delay_ms"]) / 1000.0
        use_visual_hud = bool(self.config["vision"].get("enable_visual_skillbar_read", True))

        for key_bind, skill_data in skills_cfg.items():
            if not skill_data.get("enabled", True):
                continue

            # Controllo visivo HUD: se lo slot sullo schermo è scuro (in cooldown), salta la mossa
            if use_visual_hud and visual_ready_map is not None:
                if not visual_ready_map.get(key_bind, True):
                    continue

            min_r = float(skill_data.get("min_range", 0))
            max_r = float(skill_data.get("max_range", 999))
            cd = float(skill_data.get("cooldown", 5.0))
            cast_delay = float(skill_data.get("delay_ms", 300)) / 1000.0

            last_used = self.last_used_timestamps.get(key_bind, 0.0)
            if (now - last_used) >= cd and (min_r <= current_distance_px <= max_r):
                # Ri-allinea la mira sul bersaglio un istante prima di lanciare la mossa
                self.aim_at_target(target_coords)
                self.press_key_safe(key_bind, hold_duration=0.09)
                pyautogui.click(button="left")
                self.last_used_timestamps[key_bind] = time.time()
                time.sleep(cast_delay + global_delay_sec)
                return f"Mossa HUD Pronta -> Hotkey [{key_bind.upper()}] {skill_data.get('name', 'Skill')} su ({target_coords[0]}, {target_coords[1]})"

        if current_distance_px <= 170:
            self.aim_at_target(target_coords)
            pyautogui.click(button="left")
            time.sleep(0.12)
            return "Combo M1 Base sul Bersaglio"

        return "Scansione HUD mosse / Allineamento distanza"

    def rotate_camera_search(self):
        """Ruota leggermente la visuale durante lo Stato 1 (Idle) per cercare il Boss."""
        try:
            pyautogui.keyDown("right")
            time.sleep(0.15)
            pyautogui.keyUp("right")
        except Exception:
            pass

    def run_waypoint_recovery_path(self, waypoints: List[Dict[str, Any]]):
        """Esegue la sequenza di movimenti pre-registrati post-respawn."""
        for step in waypoints:
            key = step.get("key", "w")
            duration = float(step.get("duration", 1.0))
            label = step.get("label", "Movimento")
            print(f"[RECOVERY] {label} -> Tasto [{key.upper()}] per {duration}s")
            self.press_key_safe(key, hold_duration=duration)
            time.sleep(0.15)

    def perform_roblox_server_hop(self):
        """Esegue la sequenza di coordinate per uscire dal server e riconnettersi."""
        hop_cfg = self.config["server_hop"]
        leave_x, leave_y = hop_cfg["leave_button_coords"]
        conf_x, conf_y = hop_cfg["confirm_leave_coords"]
        rec_x, rec_y = hop_cfg["reconnect_button_coords"]

        try:
            self.press_key_safe("esc", 0.1)
            time.sleep(0.8)
            pyautogui.moveTo(leave_x, leave_y, duration=0.25)
            pyautogui.click()
            time.sleep(0.8)
            pyautogui.moveTo(conf_x, conf_y, duration=0.25)
            pyautogui.click()
            time.sleep(4.5)
            pyautogui.moveTo(rec_x, rec_y, duration=0.3)
            pyautogui.click()
            time.sleep(8.0)
        except Exception as exc:
            print(f"[ERRORE SERVER HOP] {exc}")
