# ==============================================================================
# FILE: gpo_macro/gui_dashboard.py
# ==============================================================================

import re
from typing import Dict, Any
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QRectF
from PyQt5.QtGui import (
    QFont, QPainter, QColor, QPen, QLinearGradient, QConicalGradient
)
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QDoubleSpinBox, QCheckBox, QLineEdit,
    QComboBox, QSlider, QFrame, QGraphicsDropShadowEffect
)

from config_manager import ConfigManager
from state_machine import BossFarmStateMachine
from vision_core import VisionEngine
from input_controller import CombatInputController


class StatusBridge(QObject):
    status_changed = pyqtSignal(str, str, float, float)


class CircularGauge(QWidget):
    """
    Widget circolare (stile anelli 45% / 60% / 75% del design di riferimento)
    disegnato via QPainter con gradiente fluido.
    """
    def __init__(self, title: str, color_start: str, color_end: str, max_val: float = 100.0):
        super().__init__()
        self.title = title
        self.color_start = QColor(color_start)
        self.color_end = QColor(color_end)
        self.max_val = max_val
        self.value = 0.0
        self.display_text = "0%"
        self.setFixedSize(115, 135)

    def set_value(self, val: float, custom_text: str = None):
        self.value = max(0.0, min(self.max_val, val))
        self.display_text = custom_text if custom_text is not None else f"{int(self.value)}%"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(14, 10, 86, 86)

        # Traccia di sfondo scura dell'anello
        bg_pen = QPen(QColor("#151238"), 10, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Arco di progresso con gradiente
        if self.value > 0:
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            grad.setColorAt(0.0, self.color_start)
            grad.setColorAt(1.0, self.color_end)

            prog_pen = QPen(grad, 10, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(prog_pen)
            span_angle = int(-(self.value / self.max_val) * 360 * 16)
            painter.drawArc(rect, 90 * 16, span_angle)

        # Testo percentuale al centro dell'anello
        painter.setPen(QColor("#e2e8f0"))
        painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, self.display_text)

        # Etichetta sotto l'anello
        lbl_rect = QRectF(0, 102, 115, 25)
        painter.setPen(QColor("#a5b4fc"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(lbl_rect, Qt.AlignCenter, self.title.upper())


class GradientCard(QFrame):
    """Contenitore Card con sfumatura Indigo-Viola e ombra morbida 3D."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GradientCard")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(8, 6, 24, 190))
        self.setGraphicsEffect(shadow)


class MacroDashboardWindow(QMainWindow):
    def __init__(
        self,
        config: Dict[str, Any],
        config_mgr: ConfigManager,
        fsm: BossFarmStateMachine,
        vision: VisionEngine,
        input_ctrl: CombatInputController
    ):
        super().__init__()
        self.config = config
        self.config_mgr = config_mgr
        self.fsm = fsm
        self.vision = vision
        self.input_ctrl = input_ctrl

        self.bridge = StatusBridge()
        self.bridge.status_changed.connect(self._update_telemetry_labels)
        self.fsm.on_status_update = self.bridge.status_changed.emit

        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("GPO Vision Macro — True Demon Ba'al")
        self.setMinimumSize(860, 620)

        # FOGLIO DI STILE ISPIRATO AL DESIGN FLAT GRADIENT UI/UX
        self.setStyleSheet("""
            QMainWindow, QWidget#CentralBg {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #231d58, stop:0.45 #17143a, stop:1 #0f0d26
                );
                color: #f1f5f9;
                font-family: 'Segoe UI', sans-serif;
            }

            QFrame#GradientCard {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #3d358b, stop:0.6 #282360, stop:1 #1d1947
                );
                border: 1px solid #574eb8;
                border-radius: 22px;
            }

            QLabel#CardTitle {
                color: #c7d2fe;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1.5px;
            }

            QLabel#BadgePill {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f6b76c, stop:1 #eb6e88
                );
                color: #ffffff;
                font-weight: bold;
                font-size: 12px;
                border-radius: 14px;
                padding: 5px 14px;
            }

            /* Campi Input Ovale stile USERNAME / PASSWORD */
            QLineEdit, QComboBox, QDoubleSpinBox {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #352f78, stop:1 #211d52
                );
                border: 1.5px solid #6359c7;
                border-radius: 18px;
                padding: 8px 16px;
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
                border: 1.5px solid #f59e0b;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }

            /* Pulsante Principale stile LOGIN (Gradiente Pesca-Corallo) */
            QPushButton#PrimaryGradientBtn {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f6b96d, stop:0.5 #f18f79, stop:1 #ea698b
                );
                color: #ffffff;
                border: 1px solid #fcd34d;
                border-radius: 19px;
                padding: 11px 20px;
                font-size: 13px;
                font-weight: bold;
                letter-spacing: 1.5px;
            }
            QPushButton#PrimaryGradientBtn:hover {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #fbd38d, stop:1 #f472b6
                );
            }

            /* Pulsante Secondario Viola-Blu */
            QPushButton#SecondaryBtn {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #4c43a8, stop:1 #2c2669
                );
                color: #e0e7ff;
                border: 1px solid #6b60d6;
                border-radius: 17px;
                padding: 9px 18px;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton#SecondaryBtn:hover {
                background-color: #564cc0;
            }

            /* Tasti Quadrati Neumorfici per le Mosse (C, X, Z, T, R, E, F) */
            QPushButton#SkillSquareBtn {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #272258, stop:1 #18153a
                );
                color: #64748b;
                border: 1px solid #383178;
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#SkillSquareBtn:checked {
                background-color: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #6257d4, stop:1 #362e82
                );
                color: #ffffff;
                border: 1.5px solid #93c5fd;
            }

            /* Slider Orizzontale con Traccia Sfumata Pesca-Viola */
            QSlider::groove:horizontal {
                border: none;
                height: 10px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #f6b76c, stop:0.65 #ec6e87, stop:1 #1e1945
                );
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: qradialgradient(
                    cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                    stop:0 #818cf8, stop:0.45 #818cf8, stop:0.5 #ffffff, stop:1 #ffffff
                );
                border: 2px solid #ffffff;
                width: 22px;
                height: 22px;
                margin: -6px 0;
                border-radius: 11px;
            }

            QCheckBox {
                color: #cbd5e1;
                font-size: 11px;
                font-weight: bold;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 6px;
                border: 1.5px solid #6359c7;
                background-color: #1e1a4a;
            }
            QCheckBox::indicator:checked {
                background-color: #f1887c;
                border: 1.5px solid #fde68a;
            }
        """)

        central = QWidget()
        central.setObjectName("CentralBg")
        self.setCentralWidget(central)

        grid = QGridLayout(central)
        grid.setContentsMargins(24, 24, 24, 24)
        grid.setSpacing(20)

        # ======================================================================
        # CARD 1 (Alto-Sinistra): TELEMETRIA & STATO MACCHINA
        # ======================================================================
        telemetry_card = GradientCard()
        t_layout = QVBoxLayout(telemetry_card)
        t_layout.setContentsMargins(22, 20, 22, 20)

        top_bar = QHBoxLayout()
        lbl_t_title = QLabel("LIVE TELEMETRY & BOSS STATUS")
        lbl_t_title.setObjectName("CardTitle")

        self.lbl_badge = QLabel("IDLE • F9")
        self.lbl_badge.setObjectName("BadgePill")

        top_bar.addWidget(lbl_t_title)
        top_bar.addStretch()
        top_bar.addWidget(self.lbl_badge)
        t_layout.addLayout(top_bar)

        t_layout.addSpacing(10)

        self.lbl_state = QLabel("STATO: INATTIVO")
        self.lbl_state.setFont(QFont("Segoe UI", 15, QFont.Bold))
        self.lbl_state.setStyleSheet("color: #ffffff;")

        self.lbl_action = QLabel("Premi F9 o clicca AVVIA MACRO per iniziare la scansione HSV.")
        self.lbl_action.setWordWrap(True)
        self.lbl_action.setStyleSheet("color: #a5b4fc; font-size: 12px;")

        t_layout.addWidget(self.lbl_state)
        t_layout.addWidget(self.lbl_action)
        t_layout.addStretch()

        # Indicatori Circolari (Donut Charts)
        gauges_card = GradientCard()
        g_layout = QHBoxLayout(gauges_card)
        g_layout.setContentsMargins(18, 14, 18, 10)

        self.gauge_hp = CircularGauge("Boss HP", "#f6b76c", "#ea698b", 100.0)
        self.gauge_dmg = CircularGauge("Tuo Danno", "#a855f7", "#38bdf8", 10.0)
        self.gauge_prox = CircularGauge("Prossimità", "#38bdf8", "#818cf8", 100.0)

        g_layout.addWidget(self.gauge_hp)
        g_layout.addWidget(self.gauge_dmg)
        g_layout.addWidget(self.gauge_prox)

        # ======================================================================
        # CARD 2 (Alto-Destra): INPUT GIOCATORE & PULSANTI AZIONE (Stile Login)
        # ======================================================================
        login_card = GradientCard()
        l_layout = QVBoxLayout(login_card)
        l_layout.setContentsMargins(22, 20, 22, 20)
        l_layout.setSpacing(12)

        lbl_l_title = QLabel("PROFILO GIOCATORE & CONTROLLO")
        lbl_l_title.setObjectName("CardTitle")
        l_layout.addWidget(lbl_l_title)

        # Input Username stile pillola "USERNAME"
        self.txt_username = QLineEdit(self.config.get("player", {}).get("username", ""))
        self.txt_username.setPlaceholderText("USERNAME ROBLOX")
        self.txt_username.setAlignment(Qt.AlignCenter)
        self.txt_username.textChanged.connect(self._sync_parameters)
        l_layout.addWidget(self.txt_username)

        # Riga Slot Arma + Soglia Danno 5%
        row_inputs = QHBoxLayout()
        self.combo_slot = QComboBox()
        for s in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"]:
            self.combo_slot.addItem(f"SLOT ARMA: {s}", s)
        cur_slot = str(self.config.get("player", {}).get("weapon_slot", "1"))
        idx = self.combo_slot.findData(cur_slot)
        if idx >= 0:
            self.combo_slot.setCurrentIndex(idx)
        self.combo_slot.currentIndexChanged.connect(self._sync_parameters)

        self.spin_dmg_stop = QDoubleSpinBox()
        self.spin_dmg_stop.setRange(0.5, 100.0)
        self.spin_dmg_stop.setSingleStep(0.5)
        self.spin_dmg_stop.setPrefix("STOP: ")
        self.spin_dmg_stop.setSuffix(" %")
        self.spin_dmg_stop.setAlignment(Qt.AlignCenter)
        self.spin_dmg_stop.setValue(float(self.config.get("player", {}).get("stop_at_damage_percent", 5.0)))
        self.spin_dmg_stop.valueChanged.connect(self._sync_parameters)

        row_inputs.addWidget(self.combo_slot, 1)
        row_inputs.addWidget(self.spin_dmg_stop, 1)
        l_layout.addLayout(row_inputs)

        # Pulsante Principale Gradiente Pesca-Corallo (stile LOGIN)
        self.btn_toggle = QPushButton("AVVIA MACRO (F9)")
        self.btn_toggle.setObjectName("PrimaryGradientBtn")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.clicked.connect(self._on_toggle_clicked)
        l_layout.addWidget(self.btn_toggle)

        # Riga Pulsanti Secondari (Kill Switch & Salva Config)
        sec_row = QHBoxLayout()
        self.btn_kill = QPushButton("STOP EMERGENZA (F12)")
        self.btn_kill.setObjectName("SecondaryBtn")
        self.btn_kill.setCursor(Qt.PointingHandCursor)
        self.btn_kill.clicked.connect(self._on_emergency_clicked)

        self.btn_save = QPushButton("SALVA CONFIG")
        self.btn_save.setObjectName("SecondaryBtn")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_current_json)

        sec_row.addWidget(self.btn_kill)
        sec_row.addWidget(self.btn_save)
        l_layout.addLayout(sec_row)

        # ======================================================================
        # CARD 3 (Basso-Destra): TASTI MOSSA QUADRATI & SLIDER MIRA
        # ======================================================================
        skills_card = GradientCard()
        s_layout = QVBoxLayout(skills_card)
        s_layout.setContentsMargins(22, 18, 22, 18)
        s_layout.setSpacing(12)

        lbl_s_title = QLabel("ABILITÀ ATTIVE (CLICCA PER ESCLUDERE MOSSE)")
        lbl_s_title.setObjectName("CardTitle")
        s_layout.addWidget(lbl_s_title)

        # Griglia di bottoni quadrati neumorfici (C, X, Z, T, R, E, F)
        skills_row = QHBoxLayout()
        skills_row.setSpacing(10)
        self.skill_buttons: Dict[str, QPushButton] = {}
        for key_bind in ["c", "x", "z", "t", "r", "e", "f"]:
            btn = QPushButton(key_bind.upper())
            btn.setObjectName("SkillSquareBtn")
            btn.setCheckable(True)
            btn.setFixedSize(46, 46)
            btn.setCursor(Qt.PointingHandCursor)
            is_enabled = self.config.get("skills", {}).get(key_bind, {}).get("enabled", True)
            btn.setChecked(bool(is_enabled))
            btn.toggled.connect(self._sync_parameters)
            self.skill_buttons[key_bind] = btn
            skills_row.addWidget(btn)
        s_layout.addLayout(skills_row)

        # Slider con gradiente (Altezza di mira Offset Y)
        slider_header = QHBoxLayout()
        lbl_aim = QLabel("ALTEZZA DI MIRA (OFFSET Y)")
        lbl_aim.setObjectName("CardTitle")
        self.lbl_aim_val = QLabel(f"{self.config['combat']['aim_offset_y']} px")
        self.lbl_aim_val.setStyleSheet("color: #f6b76c; font-weight: bold; font-size: 12px;")
        slider_header.addWidget(lbl_aim)
        slider_header.addStretch()
        slider_header.addWidget(self.lbl_aim_val)
        s_layout.addLayout(slider_header)

        slider_row = QHBoxLayout()
        lbl_minus = QLabel("−")
        lbl_minus.setStyleSheet("color: #818cf8; font-size: 18px; font-weight: bold;")
        lbl_plus = QLabel("+")
        lbl_plus.setStyleSheet("color: #818cf8; font-size: 18px; font-weight: bold;")

        self.slider_aim = QSlider(Qt.Horizontal)
        self.slider_aim.setRange(-200, 200)
        self.slider_aim.setValue(int(self.config["combat"]["aim_offset_y"]))
        self.slider_aim.valueChanged.connect(self._on_slider_changed)

        slider_row.addWidget(lbl_minus)
        slider_row.addWidget(self.slider_aim)
        slider_row.addWidget(lbl_plus)
        s_layout.addLayout(slider_row)

        self.chk_visual_hud = QCheckBox("LETTURA VISIVA COOLDOWN ROSSO SULLA SKILL BAR")
        self.chk_visual_hud.setChecked(bool(self.config["vision"].get("enable_visual_skillbar_read", True)))
        self.chk_visual_hud.stateChanged.connect(self._sync_parameters)
        s_layout.addWidget(self.chk_visual_hud)

        # Posizionamento nella griglia 2x2
        grid.addWidget(telemetry_card, 0, 0)
        grid.addWidget(login_card, 0, 1)
        grid.addWidget(gauges_card, 1, 0)
        grid.addWidget(skills_card, 1, 1)
        grid.setColumnStretch(0, 11)
        grid.setColumnStretch(1, 10)

    def _on_slider_changed(self, val: int):
        self.lbl_aim_val.setText(f"{val} px")
        self._sync_parameters()

    def _sync_parameters(self):
        self.config.setdefault("player", {})
        self.config["player"]["username"] = self.txt_username.text().strip()
        self.config["player"]["stop_at_damage_percent"] = self.spin_dmg_stop.value()
        self.config["player"]["weapon_slot"] = str(self.combo_slot.currentData() or "1")
        self.config["combat"]["aim_offset_y"] = self.slider_aim.value()
        self.config["vision"]["enable_visual_skillbar_read"] = self.chk_visual_hud.isChecked()

        for key_bind, btn in self.skill_buttons.items():
            if key_bind in self.config.get("skills", {}):
                self.config["skills"][key_bind]["enabled"] = btn.isChecked()

    def _on_toggle_clicked(self):
        if self.fsm.running:
            self.fsm.stop()
            self.btn_toggle.setText("AVVIA MACRO (F9)")
            self.lbl_badge.setText("PAUSA • F9")
        else:
            self.fsm.start()
            self.btn_toggle.setText("FERMA MACRO (F9)")
            self.lbl_badge.setText("ATTIVO • F9")

    def _on_emergency_clicked(self):
        self.fsm.stop()
        self.input_ctrl.release_all_keys()
        self.btn_toggle.setText("AVVIA MACRO (F9)")
        self.lbl_badge.setText("STOP • F12")

    def _update_telemetry_labels(self, state_str: str, detail_str: str, hp: float, boss_area: float):
        self.lbl_state.setText(state_str)
        self.lbl_action.setText(detail_str)
        self.lbl_badge.setText("IN AZIONE" if self.fsm.running else "FERMO")

        # 1. Aggiorna Anello Boss HP
        self.gauge_hp.set_value(hp, f"{hp:.0f}%")

        # 2. Estrae la % di danno dal messaggio di stato per aggiornare l'anello Danno
        dmg_match = re.search(r"Danno:\s*(\d+[.,]\d+|\d+)%", detail_str)
        target_dmg = max(1.0, float(self.spin_dmg_stop.value()))
        self.gauge_dmg.max_val = target_dmg
        if dmg_match:
            cur_dmg = float(dmg_match.group(1).replace(",", "."))
            self.gauge_dmg.set_value(cur_dmg, f"{cur_dmg:.1f}%")

        # 3. Aggiorna Anello Prossimità 3D in base all'area del contorno del Boss
        prox_pct = min(100.0, (boss_area / 18000.0) * 100.0)
        self.gauge_prox.set_value(prox_pct, f"{int(prox_pct)}%")

    def _save_current_json(self):
        self._sync_parameters()
        self.config_mgr.save_config(self.config)
        self.lbl_badge.setText("SALVATO ✓")