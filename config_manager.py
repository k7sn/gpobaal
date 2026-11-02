# ==============================================================================
# FILE: gpo_macro/config_manager.py
# ==============================================================================

"""
================================================================================
MODULO 1: GESTIONE CONFIGURAZIONI E PRESET JSON (config_manager.py)
================================================================================
Gestisce il salvataggio, caricamento e validazione dei parametri di combattimento,
coordinate ROI dello schermo, profili colore HSV del Boss e coordinate della
Skill Bar per la lettura visiva delle mosse disponibili.
"""

import json
import os
from typing import Dict, Any


class ConfigManager:
    def __init__(self, filepath: str = "config.json"):
        self.filepath = filepath
        self.default_config: Dict[str, Any] = {
            "profile_name": "True Demon Baal (Halloween Boss)",
            "target_boss": "True Demon Baal",
            "hotkeys": {
                "start_stop": "F9",
                "emergency_kill": "F12",
                "pause_toggle": "F10"
            },
            "combat": {
                "combat_radius_px": 420,
                "safe_distance_px": 185,
                "aim_offset_y": -22,
                "skill_global_delay_ms": 340,
                "camera_sensitivity": 0.7,
                "auto_shift_lock": True
            },
            "vision": {
                "match_threshold": 0.8,
                "capture_fps_limit": 30,
                "enable_visual_skillbar_read": True,
                "ready_brightness_threshold": 135,
                "boss_bar_roi": {
                    "top": 42,
                    "left": 590,
                    "width": 740,
                    "height": 68
                },
                "death_screen_roi": {
                    "top": 380,
                    "left": 660,
                    "width": 600,
                    "height": 220
                },
                "target_roi": {
                    "top": 150,
                    "left": 320,
                    "width": 1280,
                    "height": 740
                },
                "skill_bar_roi": {
                    "top": 760,
                    "left": 1620,
                    "width": 270,
                    "height": 290
                },
                "boss_hsv_primary": {
                    "label": "Corpo Zucca Arancione Baal (HSV)",
                    "lower": [8, 165, 130],
                    "upper": [24, 255, 255],
                    "min_area": 450
                },
                "boss_hsv_secondary": {
                    "label": "Occhi / Fiamma Verde-Ciano Neon Baal (HSV)",
                    "lower": [48, 170, 160],
                    "upper": [92, 255, 255],
                    "min_area": 90
                }
            },
            "server_hop": {
                "enabled": True,
                "max_idle_seconds": 50,
                "esc_menu_coords": [42, 42],
                "leave_button_coords": [820, 620],
                "confirm_leave_coords": [820, 560],
                "reconnect_button_coords": [960, 740]
            },
            "skills": {
            "e": {"name": "Raging Serpent (E)", "cooldown": 8.5, "delay_ms": 520, "min_range": 90, "max_range": 390, "enabled": True, "hud_coords": [1740, 795]},
            "r": {"name": "Dragon Claw (R)", "cooldown": 11.5, "delay_ms": 650, "min_range": 75, "max_range": 340, "enabled": True, "hud_coords": [1740, 840]},
            "z": {"name": "Light Ray / Hiken (Z)", "cooldown": 14.0, "delay_ms": 850, "min_range": 130, "max_range": 500, "enabled": True, "hud_coords": [1740, 885]},
            "x": {"name": "Light Kick / Pillar (X)", "cooldown": 17.0, "delay_ms": 680, "min_range": 100, "max_range": 380, "enabled": True, "hud_coords": [1740, 930]},
            "c": {"name": "Ultimate AoE (C)", "cooldown": 26.0, "delay_ms": 1150, "min_range": 140, "max_range": 520, "enabled": True, "hud_coords": [1740, 975]}
            },
            "death_waypoints": [
            {"key": "w", "duration": 4.8, "label": "Sentiero Cimitero Thriller Bark"},
            {"key": "d", "duration": 1.8, "label": "Ingresso Cratere Evocazione Baal"},
            {"key": "space", "duration": 0.5, "label": "Geppo Sopra Fiamme Rosse Pavimento"},
            {"key": "w", "duration": 3.0, "label": "Centro Arena True Demon Baal"}
            ]
        }

    def load_config(self) -> Dict[str, Any]:
        """Carica la configurazione dal file JSON o la crea se non esiste."""
        if not os.path.exists(self.filepath):
            print(f"[CONFIG] File {self.filepath} non trovato. Creazione configurazione predefinita...")
            self.save_config(self.default_config)
            return self.default_config.copy()

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[CONFIG] Profilo '{data.get('profile_name', 'Default')}' caricato correttamente.")
                return data
        except Exception as exc:
            print(f"[ERRORE CONFIG] File JSON corrotto ({exc}). Ripristino valori di default.")
            return self.default_config.copy()

    def save_config(self, config_data: Dict[str, Any], custom_path: str = None) -> bool:
        """Salva il dizionario di configurazione su disco in modo atomico."""
        target = custom_path or self.filepath
        try:
            with open(target, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            print(f"[CONFIG] Configurazione salvata in '{target}'.")
            return True
        except Exception as exc:
            print(f"[ERRORE SALVATAGGIO] Impossibile scrivere su {target}: {exc}")
            return False
