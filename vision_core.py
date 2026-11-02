# ==============================================================================
# FILE: gpo_macro/vision_core.py
# ==============================================================================

"""
================================================================================
MODULO 2: CORE DI COMPUTER VISION & RILEVAMENTO (vision_core.py)
================================================================================
1. Riconoscimento Bersaglio 3D (es. True Demon Baal delle foto):
   Poiché un boss 3D ruota, salta e cambia dimensione in base alla distanza,
   un semplice ritaglio 2D statico fallirebbe. Usiamo una pipeline ibrida:
   - Segmentazione Colore HSV Primaria (Corpo Zucca Arancione di Baal)
   - Segmentazione Colore HSV Secondaria (Occhi/Fiamme Verde-Ciano Neon)
   - Calcolo dei Momenti Geometrici (cv2.moments) per trovare il baricentro (X, Y)
     esatto su cui spostare il mirino del mouse!
2. Lettura Visiva delle Mosse Disponibili (Skill Bar HUD in basso a destra):
   Analizza la luminosità (canale V in HSV) di ogni slot abilità [E, R, Z, X, C]
   per capire direttamente dallo schermo quali mosse sono pronte e quali sono
   scure (in cooldown).
"""

import os
import cv2
import mss
import numpy as np
from typing import Dict, Any, Optional, Tuple


class VisionEngine:
    def __init__(self, config: Dict[str, Any], assets_dir: str = "assets/templates"):
        self.config = config
        self.assets_dir = assets_dir
        self.templates: Dict[str, np.ndarray] = {}
        self._load_reference_templates()

    def _load_reference_templates(self):
        """Carica le immagini di riferimento (.png) dalla cartella assets/templates/."""
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
                    print(f"[VISION] Template caricato: {filename} ({img.shape[1]}x{img.shape[0]}px)")

    def grab_roi(self, roi_dict: Dict[str, int]) -> Optional[np.ndarray]:
        """Cattura una Regione di Interesse (ROI) dallo schermo con mss."""
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
        except Exception as exc:
            print(f"[ERRORE MSS] Fallita cattura schermo ROI {roi_dict}: {exc}")
            return None

    def match_template_in_roi(
        self, roi_frame: np.ndarray, template_key: str, threshold: Optional[float] = None
    ) -> Tuple[bool, float, Optional[Tuple[int, int]]]:
        """Esegue Template Matching normalizzato (TM_CCOEFF_NORMED)."""
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
        except Exception as exc:
            print(f"[ERRORE OPENCV] {exc}")
            return False, 0.0, None

    def detect_boss_presence_and_hp(self) -> Tuple[bool, float]:
        """Verifica la barra HP del Boss in alto e calcola la percentuale rimanente."""
        roi_cfg = self.config["vision"]["boss_bar_roi"]
        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return False, 0.0

        found_tmpl, _, _ = self.match_template_in_roi(frame, "boss_bar")

        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask1 = cv2.inRange(hsv, np.array([0, 140, 120]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([170, 140, 120]), np.array([180, 255, 255]))
        hp_mask = cv2.bitwise_or(mask1, mask2)

        col_sums = np.sum(hp_mask > 0, axis=0)
        active_cols = np.count_nonzero(col_sums > 3)
        total_width = frame.shape[1]
        hp_percent = min(100.0, round((active_cols / max(1, total_width * 0.82)) * 100.0, 1))

        return (found_tmpl or hp_percent > 4.0), hp_percent

    def locate_boss_target_on_screen(self) -> Tuple[bool, Optional[Tuple[int, int]], float]:
        """
        COME CAPISCE QUAL È IL BERSAGLIO (es. True Demon Baal delle foto):
        1. Cattura l'area di gioco centrale (target_roi).
        2. Applica la maschera HSV Primaria (Arancione vivido del corpo a zucca di Baal)
           e la maschera HSV Secondaria (Verde/Ciano neon degli occhi e della bocca).
        3. Esclude il pavimento rosso scuro dell'arena filtrando per Tonalità (Hue) e Area minima.
        4. Calcola il baricentro (centroide) del contorno più grande e la distanza in pixel
           dal tuo personaggio (al centro dello schermo).
        """
        roi_cfg = self.config["vision"]["target_roi"]
        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return False, None, 9999.0

        screen_center_x = roi_cfg["left"] + (roi_cfg["width"] // 2)
        screen_center_y = roi_cfg["top"] + (roi_cfg["height"] // 2)

        # Tentativo 1: Template Matching se l'utente ha fornito boss_target_marker.png
        found, _, rel_pos = self.match_template_in_roi(frame, "boss_marker")
        if found and rel_pos is not None:
            abs_x = roi_cfg["left"] + rel_pos[0]
            abs_y = roi_cfg["top"] + rel_pos[1]
            dist = float(np.hypot(abs_x - screen_center_x, abs_y - screen_center_y))
            return True, (abs_x, abs_y), dist

        # Tentativo 2 (Principale per modelli 3D come Baal): Segmentazione HSV + Centroid Locking
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        p_cfg = self.config["vision"]["boss_hsv_primary"]
        s_cfg = self.config["vision"]["boss_hsv_secondary"]

        mask_primary = cv2.inRange(hsv, np.array(p_cfg["lower"]), np.array(p_cfg["upper"]))
        mask_secondary = cv2.inRange(hsv, np.array(s_cfg["lower"]), np.array(s_cfg["upper"]))

        # Operazione morfologica di chiusura per unire gli spicchi della zucca di Baal
        kernel = np.ones((5, 5), np.uint8)
        combined_mask = cv2.morphologyEx(
            cv2.bitwise_or(mask_primary, mask_secondary), cv2.MORPH_CLOSE, kernel
        )

        contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) >= float(p_cfg.get("min_area", 350)):
                moments = cv2.moments(largest)
                if moments["m00"] != 0:
                    cx = int(moments["m10"] / moments["m00"])
                    cy = int(moments["m01"] / moments["m00"])
                else:
                    x, y, w, h = cv2.boundingRect(largest)
                    cx, cy = x + (w // 2), y + (h // 2)

                abs_x = roi_cfg["left"] + cx
                abs_y = roi_cfg["top"] + cy
                dist = float(np.hypot(abs_x - screen_center_x, abs_y - screen_center_y))
                return True, (abs_x, abs_y), dist

        return False, None, 9999.0

    def scan_ready_skills_on_hud(self) -> Dict[str, bool]:
        """
        LEGGE DALLO SCHERMO LE MOSSE DISPONIBILI E IL RELATIVO HOTKEY:
        In Grand Piece Online, le mosse nell'interfaccia (in basso a destra) sono:
        - LUMINOSE / COLORATE quando la mossa è PRONTA all'uso.
        - SCURE / GRIGIE quando la mossa è in COOLDOWN.
        Cattura un quadratino 12x12 pixel attorno alle coordinate 'hud_coords' di
        ogni hotkey (E, R, Z, X, C) e verifica se la luminosità media supera la soglia.
        """
        ready_status: Dict[str, bool] = {}
        skills_cfg: Dict[str, Dict[str, Any]] = self.config.get("skills", {})
        brightness_thresh = float(self.config["vision"].get("ready_brightness_threshold", 135))

        try:
            with mss.mss() as sct:
                for key_bind, skill_data in skills_cfg.items():
                    if not skill_data.get("enabled", True):
                        ready_status[key_bind] = False
                        continue

                    coords = skill_data.get("hud_coords", [1740, 820])
                    patch_monitor = {
                        "top": max(0, int(coords[1] - 6)),
                        "left": max(0, int(coords[0] - 6)),
                        "width": 12,
                        "height": 12
                    }
                    sct_patch = np.array(sct.grab(patch_monitor))
                    bgr_patch = cv2.cvtColor(sct_patch, cv2.COLOR_BGRA2BGR)
                    hsv_patch = cv2.cvtColor(bgr_patch, cv2.COLOR_BGR2HSV)

                    # Canale V (Value / Luminosità) medio dello slot mossa
                    mean_brightness = float(np.mean(hsv_patch[:, :, 2]))
                    ready_status[key_bind] = mean_brightness >= brightness_thresh
        except Exception as exc:
            print(f"[VISION HUD WARNING] Errore scansione visiva barra skill: {exc}")
            for k in skills_cfg:
                ready_status[k] = True

        return ready_status

    def detect_character_death(self) -> bool:
        """Rileva se il personaggio è stato sconfitto analizzando la ROI di morte/respawn."""
        roi_cfg = self.config["vision"]["death_screen_roi"]
        frame = self.grab_roi(roi_cfg)
        if frame is None:
            return False
        found, _, _ = self.match_template_in_roi(frame, "death_screen")
        return found
