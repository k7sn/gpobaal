# ==============================================================================
# FILE: gpo_macro/gui_dashboard.py
# ==============================================================================

"""
================================================================================
MODULO 5: INTERFACCIA GRAFICA DESKTOP PYQT5 (gui_dashboard.py)
================================================================================
Dashboard con controlli slider/spinbox per regolare in tempo reale il raggio di
combattimento, l'offset di mira, la lettura visiva della Skill Bar e i profili JSON.
"""

from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSpinBox, QDoubleSpinBox, QGroupBox,
    QFileDialog, QCheckBox, QFormLayout
)
from typing import Dict, Any

from config_manager import ConfigManager
from state_machine import BossFarmStateMachine
from vision_core import VisionEngine
from input_controller import CombatInputController


class StatusBridge(QObject):
    status_changed = pyqtSignal(str, str, float, float)


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
        self.setWindowTitle("GPO External Vision Macro - True Demon Baal")
        self.setMinimumSize(700, 580)
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', sans-serif; }
            QGroupBox { border: 1px solid #1e293b; border-radius: 6px; margin-top: 12px; padding-top: 14px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #94a3b8; }
            QPushButton { background-color: #2563eb; color: white; border-radius: 5px; padding: 8px 14px; font-weight: bold; }
            QPushButton:hover { background-color: #1d4ed8; }
            QSpinBox, QDoubleSpinBox { background-color: #1e293b; border: 1px solid #334155; padding: 4px; border-radius: 4px; color: #f8fafc; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        status_group = QGroupBox("Stato Macchina a Stati & Controllo Rapido")
        status_layout = QVBoxLayout(status_group)

        self.lbl_state = QLabel("STATO: INATTIVO (Premi F9 per avviare)")
        self.lbl_state.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_action = QLabel("Dettaglio: Riconoscimento HSV + Lettura HUD Skill Bar attivi")
        self.lbl_metrics = QLabel("Boss HP: 0.0%  |  Distanza: -- px  |  Emergenza: F12")

        btn_row = QHBoxLayout()
        self.btn_toggle = QPushButton("Avvia Macro (F9)")
        self.btn_toggle.clicked.connect(self._on_toggle_clicked)

        self.btn_kill = QPushButton("Arresto Emergenza (F12)")
        self.btn_kill.setStyleSheet("background-color: #dc2626;")
        self.btn_kill.clicked.connect(self._on_emergency_clicked)

        btn_row.addWidget(self.btn_toggle)
        btn_row.addWidget(self.btn_kill)

        status_layout.addWidget(self.lbl_state)
        status_layout.addWidget(self.lbl_action)
        status_layout.addWidget(self.lbl_metrics)
        status_layout.addLayout(btn_row)
        main_layout.addWidget(status_group)

        combat_group = QGroupBox("Parametri di Combattimento, Mira e Lettura HUD")
        form = QFormLayout(combat_group)

        self.spin_radius = QSpinBox()
        self.spin_radius.setRange(50, 1200)
        self.spin_radius.setSuffix(" px")
        self.spin_radius.setValue(int(self.config["combat"]["combat_radius_px"]))
        self.spin_radius.valueChanged.connect(self._sync_parameters)

        self.spin_safe_dist = QSpinBox()
        self.spin_safe_dist.setRange(20, 800)
        self.spin_safe_dist.setSuffix(" px")
        self.spin_safe_dist.setValue(int(self.config["combat"]["safe_distance_px"]))
        self.spin_safe_dist.valueChanged.connect(self._sync_parameters)

        self.spin_aim_offset = QSpinBox()
        self.spin_aim_offset.setRange(-250, 250)
        self.spin_aim_offset.setSuffix(" px")
        self.spin_aim_offset.setValue(int(self.config["combat"]["aim_offset_y"]))
        self.spin_aim_offset.valueChanged.connect(self._sync_parameters)

        self.spin_skill_delay = QSpinBox()
        self.spin_skill_delay.setRange(50, 3000)
        self.spin_skill_delay.setSuffix(" ms")
        self.spin_skill_delay.setValue(int(self.config["combat"]["skill_global_delay_ms"]))
        self.spin_skill_delay.valueChanged.connect(self._sync_parameters)

        self.chk_visual_hud = QCheckBox("Leggi visivamente dallo schermo le mosse pronte (Skill Bar HUD)")
        self.chk_visual_hud.setChecked(bool(self.config["vision"].get("enable_visual_skillbar_read", True)))
        self.chk_visual_hud.stateChanged.connect(self._sync_parameters)

        self.chk_server_hop = QCheckBox("Abilita Server Hop automatico su timeout spawn")
        self.chk_server_hop.setChecked(bool(self.config["server_hop"]["enabled"]))
        self.chk_server_hop.stateChanged.connect(self._sync_parameters)

        form.addRow("Raggio d'Azione Ingaggio:", self.spin_radius)
        form.addRow("Distanza Minima Sicurezza:", self.spin_safe_dist)
        form.addRow("Altezza di Mira (Offset Y):", self.spin_aim_offset)
        form.addRow("Ritardo Globale tra Abilità:", self.spin_skill_delay)
        form.addRow("", self.chk_visual_hud)
        form.addRow("", self.chk_server_hop)
        main_layout.addWidget(combat_group)

        profile_group = QGroupBox("Gestione Profili di Configurazione (JSON)")
        profile_layout = QHBoxLayout(profile_group)

        btn_save = QPushButton("Salva config.json")
        btn_save.clicked.connect(self._save_current_json)

        btn_load = QPushButton("Carica Profilo JSON...")
        btn_load.setStyleSheet("background-color: #334155;")
        btn_load.clicked.connect(self._load_external_json)

        profile_layout.addWidget(btn_save)
        profile_layout.addWidget(btn_load)
        main_layout.addWidget(profile_group)

    def _sync_parameters(self):
        self.config["combat"]["combat_radius_px"] = self.spin_radius.value()
        self.config["combat"]["safe_distance_px"] = self.spin_safe_dist.value()
        self.config["combat"]["aim_offset_y"] = self.spin_aim_offset.value()
        self.config["combat"]["skill_global_delay_ms"] = self.spin_skill_delay.value()
        self.config["vision"]["enable_visual_skillbar_read"] = self.chk_visual_hud.isChecked()
        self.config["server_hop"]["enabled"] = self.chk_server_hop.isChecked()

    def _on_toggle_clicked(self):
        if self.fsm.running:
            self.fsm.stop()
            self.btn_toggle.setText("Avvia Macro (F9)")
        else:
            self.fsm.start()
            self.btn_toggle.setText("Ferma Macro (F9)")

    def _on_emergency_clicked(self):
        self.fsm.stop()
        self.input_ctrl.release_all_keys()
        self.btn_toggle.setText("Avvia Macro (F9)")

    def _update_telemetry_labels(self, state_str: str, detail_str: str, hp: float, dist: float):
        self.lbl_state.setText(f"STATO: {state_str}")
        self.lbl_action.setText(f"Dettaglio: {detail_str}")
        self.lbl_metrics.setText(f"Boss HP: {hp:.1f}%  |  Distanza: {int(dist)} px  |  Kill Sessione: {self.fsm.boss_kills_count}")

    def _save_current_json(self):
        self._sync_parameters()
        self.config_mgr.save_config(self.config)

    def _load_external_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona Configurazione JSON", "", "JSON Files (*.json)")
        if path:
            self.config_mgr.filepath = path
            loaded = self.config_mgr.load_config()
            self.config.update(loaded)
            self.spin_radius.setValue(int(self.config["combat"]["combat_radius_px"]))
            self.spin_safe_dist.setValue(int(self.config["combat"]["safe_distance_px"]))
            self.spin_aim_offset.setValue(int(self.config["combat"]["aim_offset_y"]))
            self.spin_skill_delay.setValue(int(self.config["combat"]["skill_global_delay_ms"]))

