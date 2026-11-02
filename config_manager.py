import json
import os
from typing import Dict, Any

class ConfigManager:
    def __init__(self, filepath: str = "config.json"):
        self.filepath = filepath
        self.default_config: Dict[str, Any] = {
            "profile_name": "True Demon Baal (No Images)",
            "target_boss": "True Demon Baal",
            "player": {
                "username": "IlTuoUsername",
                "stop_at_damage_percent": 5.0,
                "weapon_slot": "1"
            },
            "hotkeys": {
                "start_stop": "F9",
                "emergency_kill": "F12"
            },
            "combat": {
                "min_boss_area_close": 18000,
                "max_boss_area_far": 3500,
                "dash_cooldown_sec": 2.2,
                "aim_offset_y": -22,
                "skill_global_delay_ms": 340,
                "camera_sensitivity": 0.7
            },
            "vision": {
                "capture_fps_limit": 30,
                "enable_visual_skillbar_read": True,
                "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                "boss_bar_roi": {
                    "top": 35, "left": 450, "width": 1020, "height": 65
                },
                "damage_progress_roi": {
                    "top": 95, "left": 450, "width": 380, "height": 160
                },
                "target_roi": {
                    "top": 150, "left": 250, "width": 1420, "height": 760
                },
                "boss_hsv_primary": {
                    "label": "Zucca Arancione Baal",
                    "lower": [8, 165, 130], "upper": [24, 255, 255], "min_area": 450
                },
                "boss_hsv_secondary": {
                    "label": "Occhi Ciano Baal",
                    "lower": [48, 170, 160], "upper": [92, 255, 255]
                }
            },
            "skills": {
                "c": {"name": "Skill C", "cooldown": 15.0, "delay_ms": 800, "enabled": True, "hud_coords": [1865, 635]},
                "x": {"name": "Skill X", "cooldown": 15.0, "delay_ms": 680, "enabled": True, "hud_coords": [1865, 688]},
                "z": {"name": "Skill Z", "cooldown": 12.0, "delay_ms": 750, "enabled": True, "hud_coords": [1865, 742]},
                "t": {"name": "Flight (T)", "cooldown": 10.0, "delay_ms": 500, "enabled": False, "hud_coords": [1865, 795]},
                "r": {"name": "Skill R", "cooldown": 10.0, "delay_ms": 650, "enabled": True, "hud_coords": [1865, 848]},
                "e": {"name": "Skill E", "cooldown": 8.0, "delay_ms": 520, "enabled": True, "hud_coords": [1865, 902]},
                "f": {"name": "Block (F)", "cooldown": 3.0, "delay_ms": 300, "enabled": False, "hud_coords": [1865, 955]}
            }
        }

    def load_config(self) -> Dict[str, Any]:
        if not os.path.exists(self.filepath):
            self.save_config(self.default_config)
            return self.default_config.copy()
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in self.default_config.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return self.default_config.copy()

    def save_config(self, config_data: Dict[str, Any], custom_path: str = None) -> bool:
        target = custom_path or self.filepath
        try:
            with open(target, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception:
            return False