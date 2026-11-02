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
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._configure_ocr()

    def _configure_ocr(self):
        if HAS_OCR:
            tess_path = self.config["vision"].get("tesseract_cmd", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
            if os.path.exists(tess_path):
                pytesseract.pytesseract.tesseract_cmd = tess_path

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

    def detect_boss_presence_and_hp(self) -> Tuple[bool, float]:
        roi_cfg = self.config["vision"]["boss_bar_roi"]
        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return False, 0.0

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array([0, 150, 120]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([170, 150, 120]), np.array([180, 255, 255]))
        hp_mask = cv2.bitwise_or(mask1, mask2)

        col_sums = np.sum(hp_mask > 0, axis=0)
        active_cols = np.count_nonzero(col_sums > 3)
        total_width = frame.shape[1]
        
        hp_percent = min(100.0, round((active_cols / max(1, total_width * 0.85)) * 100.0, 1))
        return hp_percent > 3.5, hp_percent

    def get_player_damage_percentage(self) -> float:
        if not HAS_OCR:
            return 0.0
        username = self.config.get("player", {}).get("username", "").strip()
        if not username:
            return 0.0
        roi_cfg = self.config["vision"].get("damage_progress_roi")
        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return 0.0

        try:
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
        except Exception:
            pass
        return 0.0

    def locate_boss_target_on_screen(self) -> Tuple[bool, Optional[Tuple[int, int]], float, float]:
        roi_cfg = self.config["vision"]["target_roi"]
        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return False, None, 0.0, 0.0

        screen_center_x = roi_cfg["width"] // 2
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        p_cfg = self.config["vision"]["boss_hsv_primary"]
        s_cfg = self.config["vision"]["boss_hsv_secondary"]

        mask_primary = cv2.inRange(hsv, np.array(p_cfg["lower"]), np.array(p_cfg["upper"]))
        mask_secondary = cv2.inRange(hsv, np.array(s_cfg["lower"]), np.array(s_cfg["upper"]))
        kernel = np.ones((7, 7), np.uint8)
        combined_mask = cv2.morphologyEx(cv2.bitwise_or(mask_primary, mask_secondary), cv2.MORPH_CLOSE, kernel)

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
                offset_x = float(cx - screen_center_x)
                return True, (abs_x, abs_y), offset_x, area

        return False, None, 0.0, 0.0

    def scan_ready_skills_on_hud(self) -> Dict[str, bool]:
        ready_status: Dict[str, bool] = {}
        skills_cfg = self.config.get("skills", {})
        try:
            with mss.mss() as sct:
                for key_bind, skill_data in skills_cfg.items():
                    if not skill_data.get("enabled", True):
                        ready_status[key_bind] = False
                        continue
                    coords = skill_data.get("hud_coords", [1865, 700])
                    patch_monitor = {
                        "top": max(0, int(coords[1] - 12)), "left": max(0, int(coords[0] - 12)),
                        "width": 24, "height": 24
                    }
                    sct_patch = np.array(sct.grab(patch_monitor))
                    bgr_patch = cv2.cvtColor(sct_patch, cv2.COLOR_BGRA2BGR)
                    hsv_patch = cv2.cvtColor(bgr_patch, cv2.COLOR_BGR2HSV)

                    red_mask = cv2.inRange(hsv_patch, np.array([0, 120, 100]), np.array([12, 255, 255]))
                    red_mask = cv2.bitwise_or(red_mask, cv2.inRange(hsv_patch, np.array([168, 120, 100]), np.array([180, 255, 255])))
                    white_mask = cv2.inRange(hsv_patch, np.array([0, 0, 165]), np.array([180, 65, 255]))

                    is_on_cooldown = np.count_nonzero(red_mask) > 35
                    is_white_ready = np.count_nonzero(white_mask) > 50
                    ready_status[key_bind] = (not is_on_cooldown) and is_white_ready
        except Exception:
            for k, v in skills_cfg.items():
                ready_status[k] = bool(v.get("enabled", True))
        return ready_status