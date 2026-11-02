import time
import ctypes
import pyautogui
from typing import Dict, Any, Tuple, List, Optional


class CombatInputController:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.last_used_timestamps: Dict[str, float] = {}
        self.last_dash_time: float = 0.0
        self.held_keys: set = set()
        self.equipped_current_life: bool = False

    def press_key_safe(self, key_str: str, hold_duration: float = 0.06):
        try:
            self.held_keys.add(key_str)
            pyautogui.keyDown(key_str)
            time.sleep(max(0.02, hold_duration))
            pyautogui.keyUp(key_str)
            self.held_keys.discard(key_str)
        except Exception:
            self.release_all_keys()

    def release_all_keys(self):
        emergency_keys = ["w", "a", "s", "d", "space", "shift", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "q", "e", "r", "t", "z", "x", "c", "f"]
        for k in list(self.held_keys) + emergency_keys:
            try:
                pyautogui.keyUp(k)
            except Exception:
                pass
        self.held_keys.clear()

    def equip_selected_slot(self):
        """Seleziona lo slot del frutto/arma impostato nella GUI (es. tasto '1')."""
        slot_key = str(self.config.get("player", {}).get("weapon_slot", "1")).strip()
        if slot_key and not self.equipped_current_life:
            self.press_key_safe(slot_key, hold_duration=0.08)
            self.equipped_current_life = True
            time.sleep(0.2)

    def aim_at_target(self, target_coords: Tuple[int, int]):
        """Sposta il cursore e ruota la visuale 3D di Roblox verso il Boss."""
        try:
            offset_y = int(self.config["combat"]["aim_offset_y"])
            sens = float(self.config["combat"]["camera_sensitivity"])
            tx = int(target_coords[0])
            ty = int(target_coords[1] + offset_y)

            cur_x, cur_y = pyautogui.position()
            dx = int((tx - cur_x) * sens)
            dy = int((ty - cur_y) * sens)

            # Movimento hardware relativo compatibile con telecamera 3D / Shift-Lock di Roblox
            ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)
            pyautogui.moveTo(tx, ty, duration=0.02)
        except Exception as exc:
            print(f"[ERRORE MIRA] {exc}")

    def follow_boss_movement(self, target_coords: Tuple[int, int], offset_x: float, boss_area: float):
        """
        Fa seguire il Boss dal player usando:
        - Mira continua + A/D per centrare il boss orizzontalmente
        - W per avanzare e W + Q (Dash) se il boss è lontano
        - S + Q (Back-dash) se il boss è troppo vicino
        """
        self.aim_at_target(target_coords)

        min_area_far = float(self.config["combat"].get("max_boss_area_far", 3500))
        max_area_close = float(self.config["combat"].get("min_boss_area_close", 18000))
        dash_cd = float(self.config["combat"].get("dash_cooldown_sec", 2.2))
        now = time.time()

        # 1. Correzione laterale (Strafe A / D) se il boss si sposta di lato
        if offset_x < -90:
            self.press_key_safe("a", hold_duration=0.12)
        elif offset_x > 90:
            self.press_key_safe("d", hold_duration=0.12)

        # 2. Gestione distanza tramite Area 3D del Boss + Dash (Q)
        if boss_area < min_area_far:
            # Boss lontano: avanza con W e usa Q (Dash) se disponibile
            pyautogui.keyDown("w")
            self.held_keys.add("w")
            if (now - self.last_dash_time) >= dash_cd:
                self.press_key_safe("q", hold_duration=0.05)
                self.last_dash_time = now
            time.sleep(0.18)
            pyautogui.keyUp("w")
            self.held_keys.discard("w")
        elif boss_area > max_area_close:
            # Boss troppo vicino: indietreggia con S
            self.press_key_safe("s", hold_duration=0.16)

    def execute_available_skill(
        self,
        target_coords: Tuple[int, int],
        visual_ready_map: Optional[Dict[str, bool]] = None
    ) -> str:
        """Lancia la prima mossa abilitata che non ha il cerchio rosso di cooldown."""
        now = time.time()
        skills_cfg: Dict[str, Dict[str, Any]] = self.config.get("skills", {})
        global_delay_sec = float(self.config["combat"]["skill_global_delay_ms"]) / 1000.0
        use_visual_hud = bool(self.config["vision"].get("enable_visual_skillbar_read", True))

        for key_bind, skill_data in skills_cfg.items():
            # Se la mossa è stata disattivata nella GUI, non premerla MAI
            if not skill_data.get("enabled", True):
                continue

            # Se il cerchio sullo schermo è rosso (in cooldown), salta la mossa
            if use_visual_hud and visual_ready_map is not None:
                if not visual_ready_map.get(key_bind, False):
                    continue

            cd = float(skill_data.get("cooldown", 5.0))
            cast_delay = float(skill_data.get("delay_ms", 300)) / 1000.0
            last_used = self.last_used_timestamps.get(key_bind, 0.0)

            # Se la lettura visiva è attiva, si fida del cerchio bianco; altrimenti usa il timer interno
            if use_visual_hud or (now - last_used) >= cd:
                self.aim_at_target(target_coords)
                self.press_key_safe(key_bind, hold_duration=0.09)
                pyautogui.click(button="left")
                self.last_used_timestamps[key_bind] = time.time()
                time.sleep(cast_delay + global_delay_sec)
                return f"Lanciata [{key_bind.upper()}] {skill_data.get('name', '')}"

        return "Inseguimento Boss / Attesa Cooldown Mosse"

    def rotate_camera_search(self):
        try:
            ctypes.windll.user32.mouse_event(0x0001, 120, 0, 0, 0)
            time.sleep(0.12)
        except Exception:
            pass

    def run_waypoint_recovery_path(self, waypoints: List[Dict[str, Any]]):
        self.equipped_current_life = False
        for step in waypoints:
            key = step.get("key", "w")
            duration = float(step.get("duration", 1.0))
            self.press_key_safe(key, hold_duration=duration)
            time.sleep(0.15)