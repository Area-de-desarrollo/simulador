import sys
import numpy as np
import random
from PyQt5 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
from pyqtgraph import PlotWidget

class VentilatorSimulator(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de Ventilador con Sensores y Alarmas")
        self.setGeometry(100, 100, 1600, 800)
        self.setStyleSheet("""
            background-color: #1e1e1e;
            color: white;
        """)

        # Parámetros ventilatorios iniciales
        self.resp_rate = 15        # respiraciones por minuto
        self.tidal_volume = 500    # mL
        self.peep = 5              # cmH2O
        self.peak_pressure = 20    # cmH2O
        self.ie_ratio = 1.2        # Relación I:E
        self.time_index = 0        # Contador de tiempo para animación
        self.start_time = None     # Tiempo de inicio real
        self.base_speed = 30       # Velocidad base de actualización (ms)
        self.ventilation_mode = "VC-CMV"  # Modo inicial
        self.pressure_support = 15  # cmH2O (para PC-CMV)
        self.plateau_time = 0.3     # segundos (para PC-CMV)
        self.resistance = 10.0      # cmH2O/L/s
        self.compliance = 0.05      # L/cmH2O

        # Parámetros de visualización
        self.max_cycles = 3        # Número máximo de ciclos a mostrar
        self.points_per_cycle = 200 # Puntos por ciclo respiratorio
        self.current_point = 0      # Punto actual en el ciclo
        
        # Buffers para almacenar datos
        self.time_data = np.array([])
        self.pressure_data = np.array([])
        self.flow_data = np.array([])
        self.volume_data = np.array([])

        # Sistema de sensores y alarmas
        self.sensor_data = {
            'flujo_espirado': 0,
            'volumen_espirado': 0,
            'compliance_efectiva': 0.05,
            'resistencia_efectiva': 10,
            'SpO2': 98,
            'frecuencia_cardiaca': 75
        }
        
        self.alarmas_activas = []
        self.eventos = []
        self.ajustes_automaticos = True
        self.ultimo_evento_time = 0

        self.init_ui()
        self.start_simulation()
        self.inicializar_sensores()

    def init_ui(self):
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QHBoxLayout(main_widget)

        # Panel izquierdo (Monitor y Alarmas)
        left_panel = QtWidgets.QVBoxLayout()
        
        # Panel de parámetros ventilatorios
        params_group = QtWidgets.QGroupBox("Parámetros Ventilatorios")
        params_group.setStyleSheet("""
            QGroupBox {
                color: white; 
                border: 1px solid #444; 
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                color: #00aaff;
                font-weight: bold;
            }
        """)
        
        params_layout = QtWidgets.QVBoxLayout()
        
        monitor_params = [
            ("Modo", self.ventilation_mode, "#004040", 18),
            ("PIP", f"{self.peak_pressure} cmH₂O", "#006060", 16),
            ("PEEP", f"{self.peep} cmH₂O", "#006060", 16),
            ("Vt", f"{self.tidal_volume} mL", "#006060", 16),
            ("FR", f"{self.resp_rate} rpm", "#006060", 16),
            ("I:E", f"1:{self.ie_ratio}", "#006060", 16)
        ]
        
        self.labels = {}
        for text, value, color, size in monitor_params:
            label = QtWidgets.QLabel(f"{text}: {value}")
            label.setStyleSheet(f"""
                color: white;
                background-color: {color};
                padding: 6px;
                border-radius: 4px;
                font-weight: bold;
                margin: 2px;
            """)
            label.setFont(QtGui.QFont("Arial", size))
            label.setAlignment(QtCore.Qt.AlignCenter)
            params_layout.addWidget(label)
            self.labels[text] = label
        
        params_group.setLayout(params_layout)
        left_panel.addWidget(params_group)
        
        # Panel de sensores
        sensors_group = QtWidgets.QGroupBox("Datos de Sensores")
        sensors_group.setStyleSheet(params_group.styleSheet())
        
        sensors_layout = QtWidgets.QVBoxLayout()
        
        self.sensor_labels = {
            'flujo_espirado': QtWidgets.QLabel("Flujo Espirado: 0 L/min"),
            'volumen_espirado': QtWidgets.QLabel("Volumen Espirado: 0 mL"),
            'compliance_efectiva': QtWidgets.QLabel("Compliance: 0.05 L/cmH₂O"),
            'resistencia_efectiva': QtWidgets.QLabel("Resistencia: 10 cmH₂O/L/s"),
            'SpO2': QtWidgets.QLabel("SpO₂: 98%"),
            'frecuencia_cardiaca': QtWidgets.QLabel("FC: 75 lpm")
        }
        
        for label in self.sensor_labels.values():
            label.setStyleSheet("""
                color: white;
                background-color: #333333;
                padding: 6px;
                border-radius: 4px;
                margin: 2px;
                font-weight: bold;
            """)
            label.setFont(QtGui.QFont("Arial", 12))
            label.setAlignment(QtCore.Qt.AlignCenter)
            sensors_layout.addWidget(label)
        
        sensors_group.setLayout(sensors_layout)
        left_panel.addWidget(sensors_group)
        
        # Panel de alarmas
        alarms_group = QtWidgets.QGroupBox("Alarmas Activas")
        alarms_group.setStyleSheet("""
            QGroupBox {
                color: #ff5555;
                border: 1px solid #ff5555; 
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                color: #ff5555;
                font-weight: bold;
            }
        """)
        
        self.alarms_layout = QtWidgets.QVBoxLayout()
        self.alarms_layout.addStretch()
        
        self.alarm_label = QtWidgets.QLabel("No hay alarmas activas")
        self.alarm_label.setStyleSheet("""
            color: white;
            font-weight: bold;
            font-size: 14px;
        """)
        self.alarm_label.setAlignment(QtCore.Qt.AlignCenter)
        self.alarms_layout.addWidget(self.alarm_label)
        
        alarms_group.setLayout(self.alarms_layout)
        left_panel.addWidget(alarms_group)
        
        # Panel de eventos
        events_group = QtWidgets.QGroupBox("Registro de Eventos")
        events_group.setStyleSheet("""
            QGroupBox {
                color: #55ff55;
                border: 1px solid #55ff55; 
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                color: #55ff55;
                font-weight: bold;
            }
        """)
        
        self.events_scroll = QtWidgets.QScrollArea()
        self.events_scroll.setWidgetResizable(True)
        self.events_content = QtWidgets.QWidget()
        self.events_layout = QtWidgets.QVBoxLayout(self.events_content)
        self.events_scroll.setWidget(self.events_content)
        
        self.events_scroll.setStyleSheet("""
            background-color: #222222;
            border: none;
        """)
        
        events_group.setLayout(QtWidgets.QVBoxLayout())
        events_group.layout().addWidget(self.events_scroll)
        left_panel.addWidget(events_group)
        
        left_panel.setStretchFactor(params_group, 1)
        left_panel.setStretchFactor(sensors_group, 1)
        left_panel.setStretchFactor(alarms_group, 1)
        left_panel.setStretchFactor(events_group, 2)

        # Panel central (Gráficas)
        graph_panel = QtWidgets.QVBoxLayout()
        
        # Configuración común para gráficos
        graph_style = {
            'background': '#000000',
            'axisColor': '#ffffff',
            'textColor': '#ffffff',
            'tickColor': '#ffffff'
        }
        
        # Gráfico de Presión
        self.pressure_graph = pg.PlotWidget()
        self.setup_graph(self.pressure_graph, "Presión (cmH₂O)", 'y', **graph_style)
        self.pressure_graph.setYRange(0, 40)
        self.pressure_curve = self.pressure_graph.plot(pen=pg.mkPen(color=(255, 255, 0), width=2))
        
        # Gráfico de Flujo
        self.flow_graph = pg.PlotWidget()
        self.setup_graph(self.flow_graph, "Flujo (L/min)", 'm', **graph_style)
        self.flow_graph.setYRange(-60, 60)
        self.flow_curve = self.flow_graph.plot(pen=pg.mkPen(color=(255, 0, 255), width=2))
        
        # Gráfico de Volumen
        self.volume_graph = pg.PlotWidget()
        self.setup_graph(self.volume_graph, "Volumen (mL)", 'g', **graph_style)
        self.volume_graph.setYRange(0, 1000)
        self.volume_curve = self.volume_graph.plot(pen=pg.mkPen(color=(0, 255, 0), width=2))
        
        # Añadir gráficos al panel
        for graph in [self.pressure_graph, self.flow_graph, self.volume_graph]:
            graph_panel.addWidget(graph)
            graph.setMinimumHeight(200)

        # Panel derecho (Controles)
        right_panel = QtWidgets.QVBoxLayout()
        
        # Grupo de selección de modo
        mode_group = QtWidgets.QGroupBox("Modo de Ventilación")
        mode_group.setStyleSheet("""
            QGroupBox {
                color: white; 
                border: 1px solid #444; 
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                color: #00aaff;
                font-weight: bold;
            }
        """)
        
        mode_layout = QtWidgets.QHBoxLayout()
        self.vc_button = QtWidgets.QPushButton("VC-CMV")
        self.pc_button = QtWidgets.QPushButton("PC-CMV")
        
        for button in [self.vc_button, self.pc_button]:
            button.setCheckable(True)
            button.setStyleSheet("""
                QPushButton {
                    background-color: #333;
                    color: white;
                    border: 1px solid #555;
                    padding: 8px;
                    min-width: 100px;
                }
                QPushButton:checked {
                    background-color: #006060;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #444;
                }
            """)
            mode_layout.addWidget(button)
        
        self.vc_button.setChecked(True)
        self.vc_button.clicked.connect(lambda: self.set_ventilation_mode("VC-CMV"))
        self.pc_button.clicked.connect(lambda: self.set_ventilation_mode("PC-CMV"))
        mode_group.setLayout(mode_layout)
        right_panel.addWidget(mode_group)
        
        # Grupo de controles ventilatorios
        control_group = QtWidgets.QGroupBox("Ajustes Ventilatorios")
        control_group.setStyleSheet(mode_group.styleSheet())
        
        control_layout = QtWidgets.QVBoxLayout()
        
        # Controles comunes
        common_controls = [
            ("FR", self.resp_rate, 5, 50, self.set_resp_rate),
            ("PEEP", self.peep, 0, 20, self.set_peep),
            ("I:E", self.ie_ratio, 0.5, 3, self.set_ie_ratio)
        ]
        
        for text, value, min_val, max_val, callback in common_controls:
            layout = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(f"{text}:")
            label.setStyleSheet("color: white;")
            label.setFont(QtGui.QFont("Arial", 10))
            
            if text == "I:E":
                spinbox = QtWidgets.QDoubleSpinBox()
                spinbox.setSingleStep(0.1)
            else:
                spinbox = QtWidgets.QSpinBox()
            
            spinbox.setRange(min_val, max_val)
            spinbox.setValue(value)
            spinbox.setStyleSheet("""
                QSpinBox, QDoubleSpinBox {
                    background-color: #333;
                    color: white;
                    border: 1px solid #555;
                    padding: 5px;
                    min-width: 80px;
                }
            """)
            spinbox.valueChanged.connect(callback)
            
            layout.addWidget(label)
            layout.addWidget(spinbox)
            control_layout.addLayout(layout)
        
        # Controles específicos de VC-CMV
        self.vc_controls = QtWidgets.QWidget()
        vc_layout = QtWidgets.QVBoxLayout()
        
        v_tidal_layout = QtWidgets.QHBoxLayout()
        v_tidal_label = QtWidgets.QLabel("Vt:")
        v_tidal_label.setStyleSheet("color: white;")
        self.v_tidal_spin = QtWidgets.QSpinBox()
        self.v_tidal_spin.setRange(200, 1000)
        self.v_tidal_spin.setValue(self.tidal_volume)
        self.v_tidal_spin.setStyleSheet(spinbox.styleSheet())
        self.v_tidal_spin.valueChanged.connect(self.set_tidal_volume)
        v_tidal_layout.addWidget(v_tidal_label)
        v_tidal_layout.addWidget(self.v_tidal_spin)
        vc_layout.addLayout(v_tidal_layout)
        
        pip_layout = QtWidgets.QHBoxLayout()
        pip_label = QtWidgets.QLabel("PIP:")
        pip_label.setStyleSheet("color: white;")
        self.pip_spin = QtWidgets.QSpinBox()
        self.pip_spin.setRange(10, 40)
        self.pip_spin.setValue(self.peak_pressure)
        self.pip_spin.setStyleSheet(spinbox.styleSheet())
        self.pip_spin.valueChanged.connect(self.set_peak_pressure)
        pip_layout.addWidget(pip_label)
        pip_layout.addWidget(self.pip_spin)
        vc_layout.addLayout(pip_layout)
        
        self.vc_controls.setLayout(vc_layout)
        control_layout.addWidget(self.vc_controls)
        
        # Controles específicos de PC-CMV (inicialmente ocultos)
        self.pc_controls = QtWidgets.QWidget()
        pc_layout = QtWidgets.QVBoxLayout()
        
        p_support_layout = QtWidgets.QHBoxLayout()
        p_support_label = QtWidgets.QLabel("Presión Soporte:")
        p_support_label.setStyleSheet("color: white;")
        self.p_support_spin = QtWidgets.QSpinBox()
        self.p_support_spin.setRange(5, 40)
        self.p_support_spin.setValue(self.pressure_support)
        self.p_support_spin.setStyleSheet(spinbox.styleSheet())
        self.p_support_spin.valueChanged.connect(self.set_pressure_support)
        p_support_layout.addWidget(p_support_label)
        p_support_layout.addWidget(self.p_support_spin)
        pc_layout.addLayout(p_support_layout)
        
        plat_time_layout = QtWidgets.QHBoxLayout()
        plat_time_label = QtWidgets.QLabel("Tiempo Meseta (s):")
        plat_time_label.setStyleSheet("color: white;")
        self.plat_time_spin = QtWidgets.QDoubleSpinBox()
        self.plat_time_spin.setRange(0.1, 1.0)
        self.plat_time_spin.setSingleStep(0.1)
        self.plat_time_spin.setValue(self.plateau_time)
        self.plat_time_spin.setStyleSheet(spinbox.styleSheet())
        self.plat_time_spin.valueChanged.connect(self.set_plateau_time)
        plat_time_layout.addWidget(plat_time_label)
        plat_time_layout.addWidget(self.plat_time_spin)
        pc_layout.addLayout(plat_time_layout)
        
        # Controles de mecánica pulmonar
        mech_layout = QtWidgets.QVBoxLayout()
        
        resist_layout = QtWidgets.QHBoxLayout()
        resist_label = QtWidgets.QLabel("Resistencia (cmH₂O/L/s):")
        resist_label.setStyleSheet("color: white;")
        self.resist_spin = QtWidgets.QDoubleSpinBox()
        self.resist_spin.setRange(5, 50)
        self.resist_spin.setSingleStep(0.5)
        self.resist_spin.setValue(self.resistance)
        self.resist_spin.setStyleSheet(spinbox.styleSheet())
        self.resist_spin.valueChanged.connect(self.set_resistance)
        resist_layout.addWidget(resist_label)
        resist_layout.addWidget(self.resist_spin)
        mech_layout.addLayout(resist_layout)
        
        compl_layout = QtWidgets.QHBoxLayout()
        compl_label = QtWidgets.QLabel("Complianza (L/cmH₂O):")
        compl_label.setStyleSheet("color: white;")
        self.compl_spin = QtWidgets.QDoubleSpinBox()
        self.compl_spin.setRange(0.01, 0.1)
        self.compl_spin.setSingleStep(0.01)
        self.compl_spin.setValue(self.compliance)
        self.compl_spin.setStyleSheet(spinbox.styleSheet())
        self.compl_spin.valueChanged.connect(self.set_compliance)
        compl_layout.addWidget(compl_label)
        compl_layout.addWidget(self.compl_spin)
        mech_layout.addLayout(compl_layout)
        
        pc_layout.addLayout(mech_layout)
        self.pc_controls.setLayout(pc_layout)
        control_layout.addWidget(self.pc_controls)
        self.pc_controls.hide()
        
        control_group.setLayout(control_layout)
        right_panel.addWidget(control_group)
        
        # Grupo de configuración de alarmas
        alarm_config_group = QtWidgets.QGroupBox("Configuración de Alarmas")
        alarm_config_group.setStyleSheet(mode_group.styleSheet())
        
        alarm_config_layout = QtWidgets.QVBoxLayout()
        
        # Configuración de límites de alarmas
        alarm_limits = [
            ("PIP Máx", 40, 10, 60),
            ("PIP Mín", 5, 0, 20),
            ("PEEP Máx", 15, 5, 25),
            ("FR Máx", 35, 10, 60),
            ("Vt Máx", 800, 300, 1200),
            ("SpO₂ Mín", 90, 70, 100)
        ]
        
        self.alarm_limits = {}
        for text, default, min_val, max_val in alarm_limits:
            layout = QtWidgets.QHBoxLayout()
            label = QtWidgets.QLabel(f"{text}:")
            label.setStyleSheet("color: white;")
            
            spinbox = QtWidgets.QSpinBox()
            spinbox.setRange(min_val, max_val)
            spinbox.setValue(default)
            spinbox.setStyleSheet(spinbox.styleSheet())
            
            layout.addWidget(label)
            layout.addWidget(spinbox)
            alarm_config_layout.addLayout(layout)
            self.alarm_limits[text] = spinbox
        
        # Botón para ajustes automáticos
        self.auto_adjust_check = QtWidgets.QCheckBox("Ajustes Automáticos")
        self.auto_adjust_check.setChecked(True)
        self.auto_adjust_check.setStyleSheet("""
            QCheckBox {
                color: white;
                padding: 5px;
            }
        """)
        self.auto_adjust_check.stateChanged.connect(self.toggle_auto_adjust)
        
        alarm_config_layout.addWidget(self.auto_adjust_check)
        alarm_config_group.setLayout(alarm_config_layout)
        right_panel.addWidget(alarm_config_group)
        
        right_panel.addStretch()

        # Ensamblar interfaz
        main_layout.addLayout(left_panel, 1)
        main_layout.addLayout(graph_panel, 2)
        main_layout.addLayout(right_panel, 1)
        self.setCentralWidget(main_widget)

    def setup_graph(self, graph, title, color, **kwargs):
        graph.setBackground(kwargs['background'])
        graph.setTitle(title, color=kwargs['textColor'], size="10pt")
        graph.setLabel('left', text=title, color=kwargs['textColor'])
        graph.setLabel('bottom', text="Tiempo (s)", color=kwargs['textColor'])
        graph.showGrid(x=True, y=True, alpha=0.3)
        graph.setMouseEnabled(x=False, y=False)
        graph.getAxis('left').setPen(kwargs['axisColor'])
        graph.getAxis('bottom').setPen(kwargs['axisColor'])

    def inicializar_sensores(self):
        """Configura los temporizadores para sensores y eventos aleatorios"""
        # Temporizador para actualización continua de sensores
        self.sensor_timer = QtCore.QTimer()
        self.sensor_timer.timeout.connect(self.actualizar_sensores)
        self.sensor_timer.start(1000)  # Actualizar cada segundo
        
        # Temporizador para eventos aleatorios (cada 30 minutos)
        self.event_timer = QtCore.QTimer()
        self.event_timer.timeout.connect(self.generar_evento_aleatorio)
        self.event_timer.start(1800000)  # 30 minutos en ms
        
        # Primer evento al iniciar
        QtCore.QTimer.singleShot(5000, self.generar_evento_aleatorio)

    def actualizar_sensores(self):
        """Actualiza los valores de los sensores con variaciones aleatorias"""
        # Actualizar valores basados en los datos actuales
        if len(self.flow_data) > 0:
            self.sensor_data['flujo_espirado'] = max(0, self.flow_data[-1] * random.uniform(0.9, 1.1))
        
        if len(self.volume_data) > 0:
            self.sensor_data['volumen_espirado'] = max(0, self.volume_data[-1] * random.uniform(0.95, 1.05))
        
        # Variaciones lentas en parámetros fisiológicos
        self.sensor_data['compliance_efectiva'] = max(0.01, min(0.1, 
            self.compliance * random.uniform(0.98, 1.02)))
        
        self.sensor_data['resistencia_efectiva'] = max(5, min(50, 
            self.resistance * random.uniform(0.95, 1.05)))
        
        # Simular variaciones en SpO2 y FC
        self.sensor_data['SpO2'] = max(70, min(100, 
            self.sensor_data['SpO2'] + random.randint(-1, 1)))
        
        self.sensor_data['frecuencia_cardiaca'] = max(40, min(180, 
            self.sensor_data['frecuencia_cardiaca'] + random.randint(-2, 2)))
        
        # Actualizar las etiquetas de los sensores
        self.sensor_labels['flujo_espirado'].setText(f"Flujo Espirado: {self.sensor_data['flujo_espirado']:.1f} L/min")
        self.sensor_labels['volumen_espirado'].setText(f"Volumen Espirado: {self.sensor_data['volumen_espirado']:.0f} mL")
        self.sensor_labels['compliance_efectiva'].setText(f"Compliance: {self.sensor_data['compliance_efectiva']:.3f} L/cmH₂O")
        self.sensor_labels['resistencia_efectiva'].setText(f"Resistencia: {self.sensor_data['resistencia_efectiva']:.1f} cmH₂O/L/s")
        self.sensor_labels['SpO2'].setText(f"SpO₂: {self.sensor_data['SpO2']}%")
        self.sensor_labels['frecuencia_cardiaca'].setText(f"FC: {self.sensor_data['frecuencia_cardiaca']} lpm")
        
        # Verificar alarmas
        self.verificar_alarmas()

    def verificar_alarmas(self):
        """Verifica los valores de los sensores contra los límites de alarma"""
        self.alarmas_activas = []
        
        # Verificar presión máxima
        if len(self.pressure_data) > 0 and max(self.pressure_data[-10:]) > self.alarm_limits["PIP Máx"].value():
            self.alarmas_activas.append(("Presión Alta", f"PIP > {self.alarm_limits['PIP Máx'].value()} cmH₂O", "#ff0000"))
        
        # Verificar presión mínima
        if len(self.pressure_data) > 0 and min(self.pressure_data[-10:]) < self.alarm_limits["PIP Mín"].value():
            self.alarmas_activas.append(("Presión Baja", f"PIP < {self.alarm_limits['PIP Mín'].value()} cmH₂O", "#ff9900"))
        
        # Verificar SpO2
        if self.sensor_data['SpO2'] < self.alarm_limits["SpO₂ Mín"].value():
            self.alarmas_activas.append(("Hipoxemia", f"SpO₂ < {self.alarm_limits['SpO₂ Mín'].value()}%", "#ff0000"))
        
        # Verificar volumen tidal
        if self.sensor_data['volumen_espirado'] > self.alarm_limits["Vt Máx"].value():
            self.alarmas_activas.append(("Volumen Alto", f"Vt > {self.alarm_limits['Vt Máx'].value()} mL", "#ff9900"))
        
        # Verificar frecuencia respiratoria
        if self.resp_rate > self.alarm_limits["FR Máx"].value():
            self.alarmas_activas.append(("Taquipnea", f"FR > {self.alarm_limits['FR Máx'].value()} rpm", "#ff9900"))
        
        # Actualizar visualización de alarmas
        self.actualizar_panel_alarmas()

    def actualizar_panel_alarmas(self):
        """Actualiza el panel de alarmas con las alarmas activas"""
        # Limpiar el layout existente
        for i in reversed(range(self.alarms_layout.count())): 
            widget = self.alarms_layout.itemAt(i).widget()
            if widget is not None and widget != self.alarm_label:
                widget.deleteLater()
        
        if not self.alarmas_activas:
            self.alarm_label.setText("No hay alarmas activas")
            self.alarm_label.setStyleSheet("color: white; font-weight: bold;")
            return
        
        self.alarm_label.setText(f"{len(self.alarmas_activas)} alarmas activas")
        self.alarm_label.setStyleSheet("color: #ff5555; font-weight: bold;")
        
        for alarma in self.alarmas_activas:
            nombre, descripcion, color = alarma
            alarm_widget = QtWidgets.QLabel(f"⚠ {nombre}: {descripcion}")
            alarm_widget.setStyleSheet(f"""
                color: white;
                background-color: {color};
                padding: 6px;
                border-radius: 4px;
                margin: 2px;
                font-weight: bold;
            """)
            self.alarms_layout.addWidget(alarm_widget)

    def generar_evento_aleatorio(self):
        """Genera un evento aleatorio que afecta los parámetros del paciente"""
        eventos_posibles = [
            ('broncoespasmo', "Broncoespasmo detectado", 0.3),
            ('cambio_compliance', "Cambio en compliance pulmonar", 0.3),
            ('desconexion', "Posible desconexión o fuga", 0.2),
            ('aumento_demanda', "Aumento en demanda ventilatoria", 0.2)
        ]
        
        # Seleccionar evento basado en probabilidades
        evento = random.choices(
            [e[0] for e in eventos_posibles],
            weights=[e[2] for e in eventos_posibles]
        )[0]
        
        mensaje = ""
        
        if evento == 'broncoespasmo':
            # Aumento importante de resistencia
            cambio = random.uniform(5, 15)
            self.sensor_data['resistencia_efectiva'] += cambio
            mensaje = f"Evento: Broncoespasmo. Resistencia aumentó {cambio:.1f} cmH₂O/L/s"
            
        elif evento == 'cambio_compliance':
            # Cambio en la distensibilidad pulmonar
            cambio = random.uniform(-0.02, 0.02)
            self.sensor_data['compliance_efectiva'] += cambio
            mensaje = f"Evento: Cambio en compliance. Nuevo valor {self.sensor_data['compliance_efectiva']:.3f} L/cmH₂O"
            
        elif evento == 'desconexion':
            # Simular fuga en el sistema
            self.sensor_data['flujo_espirado'] *= 0.5
            self.sensor_data['volumen_espirado'] *= 0.5
            mensaje = "Alerta: Posible desconexión o fuga en el sistema"
            
        elif evento == 'aumento_demanda':
            # Simular aumento en demanda ventilatoria
            self.sensor_data['flujo_espirado'] *= 1.5
            self.sensor_data['frecuencia_cardiaca'] = min(180, self.sensor_data['frecuencia_cardiaca'] + 10)
            mensaje = "Evento: Aumento en demanda ventilatoria detectado"
        
        # Registrar evento
        self.registrar_evento(mensaje)
        
        # Ajustar parámetros ventilatorios si está en modo automático
        if self.ajustes_automaticos:
            self.ajustar_parametros_automaticos(evento)

    def registrar_evento(self, mensaje):
        """Registra un evento en el panel de eventos"""
        timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
        event_label = QtWidgets.QLabel(f"[{timestamp}] {mensaje}")
        event_label.setStyleSheet("""
            color: #dddddd;
            background-color: #333333;
            padding: 4px;
            border-radius: 3px;
            margin: 2px;
        """)
        
        # Insertar al principio del layout
        self.events_layout.insertWidget(0, event_label)
        
        # Limitar a 50 eventos
        if self.events_layout.count() > 50:
            widget = self.events_layout.itemAt(50).widget()
            if widget is not None:
                widget.deleteLater()

    def ajustar_parametros_automaticos(self, evento):
        """Ajusta los parámetros basado en los datos de sensores"""
        ajustes = []
        
        if evento == 'broncoespasmo':
            # Aumentar PEEP si hay aumento de resistencia
            nuevo_peep = min(15, self.peep + 2)
            if nuevo_peep != self.peep:
                self.set_peep(nuevo_peep)
                ajustes.append(f"PEEP aumentado a {nuevo_peep} cmH₂O")
        
        elif evento == 'cambio_compliance':
            # Ajustar volumen tidal si hay cambio en compliance
            factor_ajuste = self.sensor_data['compliance_efectiva'] / self.compliance
            nuevo_vt = min(800, max(300, self.tidal_volume * factor_ajuste))
            if abs(nuevo_vt - self.tidal_volume) > 20:
                self.set_tidal_volume(int(nuevo_vt))
                ajustes.append(f"Volumen tidal ajustado a {nuevo_vt:.0f} mL")
        
        elif evento == 'aumento_demanda':
            # Aumentar frecuencia respiratoria
            nueva_fr = min(35, self.resp_rate + 5)
            if nueva_fr != self.resp_rate:
                self.set_resp_rate(nueva_fr)
                ajustes.append(f"Frecuencia respiratoria aumentada a {nueva_fr} rpm")
        
        if ajustes:
            mensaje = "Ajustes automáticos: " + ", ".join(ajustes)
            self.registrar_evento(mensaje)

    def toggle_auto_adjust(self, state):
        """Activa/desactiva los ajustes automáticos"""
        self.ajustes_automaticos = (state == QtCore.Qt.Checked)
        mensaje = "Ajustes automáticos ACTIVADOS" if self.ajustes_automaticos else "Ajustes automáticos DESACTIVADOS"
        self.registrar_evento(mensaje)

    # [...] (resto de los métodos existentes como set_resp_rate, set_tidal_volume, etc.)
    def generate_next_point(self):
        """Genera el siguiente punto de datos según el modo actual"""
        total_time = 60 / max(1, self.resp_rate)
        """**************************************"""
        insp_time = total_time * (1/ (1 + (1/self.ie_ratio)))
        exp_time = total_time *(1/(1 + self.ie_ratio))
        esp_time= total_time - insp_time
        cycle_progress = (self.time_index % total_time) / total_time
        current_time_in_cycle = (self.time_index % total_time)
        
        if self.ventilation_mode == "VC-CMV":
            # Modo Controlado por Volumen
            if cycle_progress * total_time < insp_time:
                # Fase inspiratoria
                x = cycle_progress * total_time / insp_time
                
                #hace que la señal salga cuadrada
                #flow = (self.tidal_volume/1000) / insp_time *60
                #ti_trasncurrido = current_time_in_cycle
                #flow = self.calcular_flujo_insp(ti_trasncurrido, insp_time)
                flow = 30 * (self.tidal_volume / 500)
                
                # Volumen durante inspiración (forma sinusoidal)
                #volume = self.tidal_volume * 0.5 * (1 - np.cos(np.pi * x))
                volume=self.tidal_volume*(current_time_in_cycle/insp_time)
                
                # if current_time_in_cycle < insp_time:
                #     x = current_time_in_cycle / insp_time
                #     pressure = self.peep + (self.peak_pressure - self.peep) * (1 - np.exp(-2*x))
                # else:
                #     #caida del PEEP
                #     pressure=self.peep
                #     # if self.peep > 1:
                #     #     pressure=self.peep
                #     # else:
                #     #     if self.peep <= 1:
                #     #         pressure=self.peep + 0.4
                    
                pressure = self.peep + (self.peak_pressure - self.peep) * (1 - np.exp(-4*x))
                
                
            else:
                # Fase espiratoria
                x = (cycle_progress * total_time - insp_time) / exp_time
                flow = -50 * np.exp(-7*x)
                #flow = -60 * (self.tidal_volume/1000) / exp_time * np.exp(-8*x)
                #flow=((-self.peak_pressure - self.peep) / self.resistance)*np.exp((-1*(x-insp_time))*(self.resistance*self.compliance))
               
                if self.peep > 1:
                        pressure=self.peep
                else:
                        if self.peep <= 1:
                            pressure=self.peep + 0.4
                #pressure = self.peep + (self.peak_pressure - self.peep) * np.exp(-4*x)
                
                # Volumen durante espiración (decaimiento exponencial)
                volume = self.tidal_volume * np.exp(-8*x)
        
        else:
            # Modo Controlado por Presión
            ramp_time = insp_time * 0.2
            plateau_time = min(self.plateau_time, insp_time * 0.5)
            release_time = insp_time * 0.1
            current_time_in_cycle = cycle_progress * total_time
            
            # Calcular presión
            if current_time_in_cycle < ramp_time:
                x = current_time_in_cycle / ramp_time
                pressure = self.peep + self.pressure_support * (1 - np.exp(-5*x))
            elif current_time_in_cycle < ramp_time + plateau_time:
                pressure = self.peep + self.pressure_support
            elif current_time_in_cycle < insp_time:
                x = (current_time_in_cycle - ramp_time - plateau_time) / (insp_time - ramp_time - plateau_time)
                pressure = self.peep + self.pressure_support * np.exp(-8*x)
            else:
                x = (current_time_in_cycle - insp_time) / exp_time
                pressure = self.peep + (self.peak_pressure - self.peep) * np.exp(-5*x)
            
            # Calcular flujo
            peak_flow = (self.pressure_support / self.resistance) * 60
            if current_time_in_cycle < ramp_time:
                x = current_time_in_cycle / ramp_time
                flow = peak_flow * (1 - x**2)  # Flujo decelerado
            elif current_time_in_cycle < ramp_time + plateau_time:
                flow = peak_flow * 0.3  # Flujo meseta
            elif current_time_in_cycle < insp_time:
                flow = peak_flow * 0.1  # Flujo residual
            else:
                x = (current_time_in_cycle - insp_time) / exp_time
                flow = -peak_flow * 0.7 * np.exp(-6*x)  # Flujo espiratorio
            
            # Calcular volumen basado en la compliance
            if current_time_in_cycle < insp_time:
                # Durante la inspiración
                if current_time_in_cycle < ramp_time:
                    x = current_time_in_cycle / ramp_time
                    volume = self.tidal_volume * 0.5 * (1 - np.cos(np.pi * x/2))
                elif current_time_in_cycle < ramp_time + plateau_time:
                    x = (current_time_in_cycle - ramp_time) / plateau_time
                    volume = self.tidal_volume * (0.5 + 0.4 * x)
                else:
                    x = (current_time_in_cycle - ramp_time - plateau_time) / (insp_time - ramp_time - plateau_time)
                    volume = self.tidal_volume * (0.9 + 0.1 * (1 - x))
            else:
                # Durante la espiración
                x = (current_time_in_cycle - insp_time) / exp_time
                volume = self.tidal_volume * np.exp(-5*x)
        
        return self.time_index, pressure, flow, volume
    
 
    def update_graphs(self):
        # Sincronizar con el tiempo real
        if self.start_time is None:
            self.start_time = QtCore.QTime.currentTime()
            elapsed = 0.0
        else:
            elapsed = self.start_time.msecsTo(QtCore.QTime.currentTime()) / 1000.0
        self.time_index = elapsed

        # Generar el siguiente punto de datos
        t, pressure, flow, volume = self.generate_next_point()

        # Añadir el nuevo punto a los buffers
        self.time_data = np.append(self.time_data, t)
        self.pressure_data = np.append(self.pressure_data, pressure)
        self.flow_data = np.append(self.flow_data, flow)
        self.volume_data = np.append(self.volume_data, volume)

        # Mantener solo los últimos N puntos (para mostrar varios ciclos)
        total_time = 60 / max(1, self.resp_rate)
        max_points = int(self.points_per_cycle * self.max_cycles)
        if len(self.time_data) > max_points:
            self.time_data = self.time_data[-max_points:]
            self.pressure_data = self.pressure_data[-max_points:]
            self.flow_data = self.flow_data[-max_points:]
            self.volume_data = self.volume_data[-max_points:]
        # Efecto barra deslizante: solo mostrar los datos de los últimos 10 segundos
        window_size = 10
        t_max = self.time_data[-1] if len(self.time_data) > 0 else 0
        t_min = max(0, t_max - window_size)
        mask = (self.time_data >= t_min) & (self.time_data <= t_max)
        self.pressure_curve.setData(self.time_data[mask], self.pressure_data[mask])
        self.flow_curve.setData(self.time_data[mask], self.flow_data[mask])
        self.volume_curve.setData(self.time_data[mask], self.volume_data[mask])
        # Mover la ventana del eje X
        self.pressure_graph.setXRange(t_min, t_max)
        self.flow_graph.setXRange(t_min, t_max)
        self.volume_graph.setXRange(t_min, t_max)
        
    def set_resp_rate(self, value):
        self.resp_rate = value
        self.labels["FR"].setText(f"FR: {value} rpm")
       # self.reset_buffers()
        self.update_animation_speed()

    def set_tidal_volume(self, value):
        self.tidal_volume = value
        self.labels["Vt"].setText(f"Vt: {value} mL")
      #  self.reset_buffers()

    def set_peep(self, value):
        self.peep = value
        self.labels["PEEP"].setText(f"PEEP: {value} cmH₂O")
       # self.reset_buffers()

    def set_peak_pressure(self, value):
        self.peak_pressure = value
        self.labels["PIP"].setText(f"PIP: {value} cmH₂O")
        #self.reset_buffers()

    def set_ie_ratio(self, value):
        self.ie_ratio = round(value, 1)
        self.labels["I:E"].setText(f"I:E: 1:{self.ie_ratio}")
       # self.reset_buffers()

    def set_pressure_support(self, value):
        self.pressure_support = value
        self.peak_pressure = self.peep + value
        self.labels["PIP"].setText(f"PIP: {self.peak_pressure} cmH₂O")
       # self.reset_buffers()

    def set_plateau_time(self, value):
        self.plateau_time = value
       # self.reset_buffers()

    def set_resistance(self, value):
        self.resistance = value
      #  self.reset_buffers()

    def set_compliance(self, value):
        self.compliance = value
      #  self.reset_buffers()

    def start_simulation(self):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_graphs)
        self.update_animation_speed()

    def start_simulation(self):
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_graphs)
        self.update_animation_speed()

    def update_animation_speed(self):
        if hasattr(self, 'timer'):
            self.timer.stop()
        interval = max(10, min(100, int(1000 / self.resp_rate)))
        self.timer.start(interval)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    simulator = VentilatorSimulator()
    simulator.show()
    sys.exit(app.exec_())