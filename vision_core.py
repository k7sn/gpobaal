import os
import re
import cv2
import mss
import numpy as np
from typing import Dict, Any, Optional, Tuple

try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


class VisionEngine:
    def __init__(self, config: Dict[str, Any], assets_dir: str = "assets/templates"):
        self.config = config
        self.assets_dir = assets_dir
        self.templates: Dict[str, np.ndarray] = {}
        self._configure_ocr()
        self._load_reference_templates()

    def _configure_ocr(self):
        if HAS_OCR:
            tess_path = self.config["vision"].get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
            if os.path.exists(tess_path):
                pytesseract.pytesseract.tesseract_cmd = tess_path

    def _load_reference_templates(self):
        required_files = {
            "boss_bar": "boss_hp_header.png",
            "boss_marker": "boss_target_marker.png",
            "death_screen": "death_respawn_banner.png",
            "reconnect_btn": "roblox_reconnect_btn.png"
        }
        os.makedirs(self.assets_dir, exist_ok=True)
        for key, filename in required_files.items():
            full_path = os.path.join(self.assets_dir, filename)
            if os.path.exists(full_path):
                img = cv2.imread(full_path, cv2.IMREAD_COLOR)
                if img is not None:
                    self.templates[key] = img

    def grab_roi(self, roi_dict: Dict[str, int]) -> Optional[np.ndarray]:
        try:
            with mss.mss() as sct:
                monitor = {
                    "top": int(roi_dict["top"]),
                    "left": int(roi_dict["left"]),
                    "width": int(roi_dict["width"]),
                    "height": int(roi_dict["height"])
                }
                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        except Exception:
            return None

    def match_template_in_roi(
        self, roi_frame: np.ndarray, template_key: str, threshold: Optional[float] = None
    ) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
        if roi_frame is None or template_key not in self.templates:
            return False, 0.0, None
        templ = self.templates[template_key]
        if roi_frame.shape[0] < templ.shape[0] or roi_frame.shape[1] < templ.shape[1]:
            return False, 0.0, None
        thresh = threshold or float(self.config["vision"]["match_threshold"])
        try:
            result = cv2.matchTemplate(roi_frame, templ, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val >= thresh:
                h, w = templ.shape[:2]
                return True, float(max_val), (int(max_loc[0] + w // 2), int(max_loc[1] + h // 2))
            return False, float(max_val), None
        except Exception:
            return False, 0.0, None

    def detect_boss_presence_and_hp(self) -> Tuple[bool, float]:
        """Rileva la barra rossa della vita di True Demon Ba'al in alto."""
        roi_cfg = self.config["vision"]["boss_bar_roi"]
        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return False, 0.0

        found_tmpl, _, _ = self.match_template_in_roi(frame, "boss_bar")

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array([0, 150, 120]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([170, 150, 120]), np.array([180, 255, 255]))
        hp_mask = cv2.bitwise_or(mask1, mask2)

        col_sums = np.sum(hp_mask > 0, axis=0)
        active_cols = np.count_nonzero(col_sums > 3)
        total_width = frame.shape[1]
        hp_percent = min(100.0, round((active_cols / max(1, total_width * 0.85)) * 100.0, 1))

        return (found_tmpl or hp_percent > 3.5), hp_percent

    def get_player_damage_percentage(self) -> float:
        """
        Legge tramite OCR l'area 'Damage Progress' sotto la barra HP del boss
        (es. 'FeNixbRoTop1: 1.57%') e restituisce la % del giocatore configurato.
        """
        if not HAS_OCR:
            return 0.0

        username = self.config.get("player", {}).get("username", "").strip()
        if not username:
            return 0.0

        roi_cfg = self.config["vision"].get("damage_progress_roi")
        if not roi_cfg:
            return 0.0

        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return 0.0

        try:
            # Ingrandisce l'immagine 2x e isola il testo bianco per migliorare la precisione OCR
            enlarged = cv2.resize(frame, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 185, 255, cv2.THRESH_BINARY)

            text = pytesseract.image_to_string(thresh, config="--psm 6")
            for line in text.splitlines():
                if username.lower() in line.lower():
                    match = re.search(r"(\d+[.,]\d+|\d+)\s*%", line)
                    if match:
                        val_str = match.group(1).replace(",", ".")
                        return float(val_str)
        except Exception as exc:
            print(f"[OCR WARNING] Lettura Damage Progress fallita: {exc}")

        return 0.0

    def locate_boss_target_on_screen(self) -> Tuple[bool, Optional[Tuple[int, int]], float, float]:
        """
        Individua True Demon Ba'al e restituisce:
        (trova_boss, (abs_x, abs_y), offset_orizzontale_dx, area_contorno_px)
        """
        roi_cfg = self.config["vision"]["target_roi"]
        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return False, None, 0.0, 0.0

        screen_center_x = roi_cfg["left"] + (roi_cfg["width"] // 2)

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        p_cfg = self.config["vision"]["boss_hsv_primary"]
        s_cfg = self.config["vision"]["boss_hsv_secondary"]

        mask_primary = cv2.inRange(hsv, np.array(p_cfg["lower"]), np.array(p_cfg["upper"]))
        mask_secondary = cv2.inRange(hsv, np.array(s_cfg["lower"]), np.array(s_cfg["upper"]))

        kernel = np.ones((7, 7), np.uint8)
        combined_mask = cv2.morphologyEx(
            cv2.bitwise_or(mask_primary, mask_secondary), cv2.MORPH_CLOSE, kernel
        )

        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            area = float(cv2.contourArea(largest))
            if area >= float(p_cfg.get("min_area", 450)):
                moments = cv2.moments(largest)
                if moments["m00"] != 0:
                    cx = int(moments["m10"] / moments["m00"])
                    cy = int(moments["m01"] / moments["m00"])
                else:
                    x, y, w, h = cv2.boundingRect(largest)
                    cx, cy = x + (w // 2), y + (h // 2)

                abs_x = roi_cfg["left"] + cx
                abs_y = roi_cfg["top"] + cy
                offset_x = float(abs_x - screen_center_x)
                return True, (abs_x, abs_y), offset_x, area

        return False, None, 0.0, 0.0

    def scan_ready_skills_on_hud(self) -> Dict[str, bool]:
        """
        Analizza i cerchi delle mosse a destra (C, X, Z, T, R, E, F).
        - Quando una mossa è IN COOLDOWN, il cerchio diventa ROSSO (alta componente Red, alta saturazione).
        - Quando è PRONTA, il cerchio è BIANCO (alta luminosità V, bassa saturazione S).
        """
        ready_status: Dict[str, bool] = {}
        skills_cfg: Dict[str, Dict[str, Any]] = self.config.get("skills", {})

        try:
            with mss.mss() as sct:
                for key_bind, skill_data in skills_cfg.items():
                    if not skill_data.get("enabled", True):
                        ready_status[key_bind] = False
                        continue

                    coords = skill_data.get("hud_coords", [1865, 700])
                    # Cattura un riquadro 24x24 sul cerchio del tasto
                    patch_monitor = {
                        "top": max(0, int(coords[1] - 12)),
                        "left": max(0, int(coords[0] - 12)),
                        "width": 24,
                        "height": 24
                    }
                    sct_patch = np.array(sct.grab(patch_monitor))
                    bgr_patch = cv2.cvtColor(sct_patch, cv2.COLOR_BGRA2BGR)
                    hsv_patch = cv2.cvtColor(bgr_patch, cv2.COLOR_BGR2HSV)

                    # 1. Rileva pixel ROSSI (cooldown attivo come in image_2e0a23.png)
                    red_mask1 = cv2.inRange(hsv_patch, np.array([0, 120, 100]), np.array([12, 255, 255]))
                    red_mask2 = cv2.inRange(hsv_patch, np.array([168, 120, 100]), np.array([180, 255, 255]))
                    red_pixels = np.count_nonzero(cv2.bitwise_or(red_mask1, red_mask2))

                    # 2. Rileva pixel BIANCHI del cerchio pronto (Saturazione bassa, Value alto)
                    white_mask = cv2.inRange(hsv_patch, np.array([0, 0, 165]), np.array([180, 65, 255]))
                    white_pixels = np.count_nonzero(white_mask)

                    # Se ci sono molti pixel rossi è in cooldown; se prevalgono i bianchi è pronta
                    is_on_cooldown = red_pixels > 35
                    is_white_ready = white_pixels > 50

                    ready_status[key_bind] = (not is_on_cooldown) and is_white_ready
        except Exception as exc:
            print(f"[VISION HUD WARNING] Errore scansione barra skill: {exc}")
            for k, v in skills_cfg.items():
                ready_status[k] = bool(v.get("enabled", True))

        return ready_status

    def detect_character_death(self) -> bool:
        roi_cfg = self.config["vision"]["death_screen_roi"]
        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return False
        found, _, _ = self.match_template_in_roi(frame, "death_screen")
        return found