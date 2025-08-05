import sys
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg

class VentilatorSimulator(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador de Ventilador - Versión Mejorada")
        self.setGeometry(100, 100, 1400, 700)
        self.setStyleSheet("background-color: #1e1e1e;")

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

        self.init_ui()
        self.start_simulation()

    def init_ui(self):
        main_widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QHBoxLayout(main_widget)

        # Panel izquierdo (Monitor)
        left_panel = QtWidgets.QVBoxLayout()
        
        # Etiquetas de monitoreo
        monitor_params = [
            ("Modo", self.ventilation_mode, "#004040", 18),
            ("PIP", f"{self.peak_pressure} cmH₂O", "#006060", 16),
            ("Pplat", "18 cmH₂O", "#006060", 16),
            ("PEEP", f"{self.peep} cmH₂O", "#006060", 16),
            ("Vt", f"{self.tidal_volume} mL", "#006060", 16),
            ("FR", f"{self.resp_rate} rpm", "#006060", 16),
            ("I:E", f"1:{self.ie_ratio}", "#006060", 16),
            ("SpO₂", "98%", "#008080", 16)
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
            """)
            label.setFont(QtGui.QFont("Arial", size))
            label.setAlignment(QtCore.Qt.AlignCenter)
            left_panel.addWidget(label)
            left_panel.addSpacing(8)
            self.labels[text] = label

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
        self.pressure_graph.setYRange(-5,30)
        self.pressure_graph.setXRange(0, 10)
        self.pressure_curve = self.pressure_graph.plot(
            pen=pg.mkPen(color=(255, 255, 0), width=2),
            fillLevel=0,
            brush=pg.mkBrush(255, 255, 0, 80)  # Amarillo translúcido
        )
        
        # Gráfico de Flujo
        self.flow_graph = pg.PlotWidget()
        self.setup_graph(self.flow_graph, "Flujo (L/min)", 'm', **graph_style)
        self.flow_graph.setYRange(-50,30)
        self.flow_graph.setXRange(0, 5)
        self.flow_curve = self.flow_graph.plot(
            pen=pg.mkPen(color=(255, 0, 255), width=2),
            fillLevel=0,
            brush=pg.mkBrush(255, 0, 255, 80)  # Magenta translúcido
        )
        
        # Gráfico de Volumen
        self.volume_graph = pg.PlotWidget()
        self.setup_graph(self.volume_graph, "Volumen (mL)", 'g', **graph_style)
        self.volume_graph.setYRange(2,1100)
        self.volume_graph.setXRange(0, 10)
        self.volume_curve = self.volume_graph.plot(
            pen=pg.mkPen(color=(0, 255, 0), width=2),
            fillLevel=0,
            brush=pg.mkBrush(0, 255, 0, 80)  # Verde translúcido
        )
        
        # Añadir gráficos al panel
        for graph in [self.pressure_graph, self.flow_graph, self.volume_graph]:
            graph_panel.addWidget(graph)
            graph.setMinimumHeight(180)
            graph.setMaximumHeight(200)

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
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
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
        v_tidal_label.setFont(QtGui.QFont("Arial", 10))
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
        pip_label.setFont(QtGui.QFont("Arial", 10))
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
        p_support_label.setFont(QtGui.QFont("Arial", 10))
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
        plat_time_label.setFont(QtGui.QFont("Arial", 10))
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
        resist_label.setFont(QtGui.QFont("Arial", 10))
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
        compl_label.setFont(QtGui.QFont("Arial", 10))
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

    def reset_buffers(self):
        """Reinicia todos los buffers de datos"""
        self.time_data = np.array([])
        self.pressure_data = np.array([])
        self.flow_data = np.array([])
        self.volume_data = np.array([])
        self.current_point = 0
        self.time_index = 0
        self.start_time = None
    
        """**************************************************************************************************""" 
    def calcular_flujo_insp(self, ti, ti_total):
        flujo_inicial=38.0
        flujo_final=9.0
        k=-np.log(flujo_final/flujo_inicial)/ti_total
        return flujo_inicial * np.exp(-k * ti)
    
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
                # flow = (self.tidal_volume/1000) / insp_time *60
                ti_trasncurrido = current_time_in_cycle
                flow = self.calcular_flujo_insp(ti_trasncurrido, insp_time)
                
                # Volumen durante inspiración (forma sinusoidal)
                volume = self.tidal_volume * 0.5 * (1 - np.cos(np.pi * x))
                if current_time_in_cycle < insp_time:
                    x = current_time_in_cycle / insp_time
                    pressure = self.peep + (self.peak_pressure - self.peep) * (1 - np.exp(-2*x))
                else:
                    #caida del PEEP
                    pressure=self.peep
                    # if self.peep > 1:
                    #     pressure=self.peep
                    # else:
                    #     if self.peep <= 1:
                    #         pressure=self.peep + 0.4
                    
                #pressure = self.peep + (self.peak_pressure - self.peep) * (1 - np.exp(-4*x))
                
                
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

    def set_ventilation_mode(self, mode):
        self.ventilation_mode = mode
        self.labels["Modo"].setText(f"Modo: {mode}")
        self.reset_buffers()
        
        if mode == "VC-CMV":
            self.vc_button.setChecked(True)
            self.pc_button.setChecked(False)
            self.vc_controls.show()
            self.pc_controls.hide()
        else:
            self.vc_button.setChecked(False)
            self.pc_button.setChecked(True)
            self.vc_controls.hide()
            self.pc_controls.show()

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

    def update_animation_speed(self):
        """Ajusta dinámicamente la velocidad según la frecuencia respiratoria"""
        if hasattr(self, 'timer'):
            self.timer.stop()
            
        # Calculamos el intervalo en ms inversamente proporcional a la FR
        min_interval = 10  # Mínimo 10ms para no sobrecargar el sistema
        max_interval = 100 # Máximo 100ms para frecuencias muy bajas
        
        # Intervalo ajustado (a mayor FR, menor intervalo = más rápido)
        interval = max(min_interval, min(max_interval, int(1000 / self.resp_rate)))
        
        self.timer.start(interval)


# Bloque principal fuera de la clase
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    simulator = VentilatorSimulator()
    simulator.show()
    sys.exit(app.exec_())
