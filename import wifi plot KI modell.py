import sys, numpy as np, socket, struct, pyqtgraph as pg, librosa, csv, datetime, os, joblib
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal, Slot, Qt

# --- KONFIGURATION ---
UDP_IP, UDP_PORT = "0.0.0.0", 5005
SAMPLES, FS = 4096, 8000  # 8kHz Abtastrate vom ESP32
EXPECTED_BYTES = SAMPLES * 4
ZOOM_SAMPLES = 800  # Zeigt ca. 100ms im Zeitbereich

class AudioWorker(QtCore.QObject):
    # Signal liefert: Zeitdaten, FFT, MFCCs, Erkannter Name, Konfidenz, Frequenz, Note
    payload_ready = Signal(np.ndarray, np.ndarray, np.ndarray, str, float, float, str)

    def __init__(self):
        super().__init__()
        self.running, self.mode, self.current_label, self.model = True, "Monitor", "none", None
        self.hanning = np.hanning(SAMPLES)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.1)
        self.load_model()

    def load_model(self):
        if os.path.exists('instrument_ai.pkl'):
            try: self.model = joblib.load('instrument_ai.pkl'); return True
            except: return False
        return False

    def run(self):
        try:
            self.sock.bind((UDP_IP, UDP_PORT))
            full_data = bytearray()
            while self.running:
                try:
                    packet, _ = self.sock.recvfrom(4096)
                    if len(packet) > 4: full_data.extend(packet[4:])
                    if len(full_data) >= EXPECTED_BYTES:
                        data = np.frombuffer(full_data[:EXPECTED_BYTES], dtype='<f4').copy()
                        if np.all(np.isfinite(data)): self.process_data(data)
                        full_data = full_data[EXPECTED_BYTES:]
                except socket.timeout: continue
            self.sock.close()
        except Exception as e: print(f"UDP Error: {e}")

    def process_data(self, data):
        # 1. Analyse vorbereiten (DC-Offset/Schwerkraft entfernen für FFT)
        sig = data - np.mean(data)
        fft_raw = np.abs(np.fft.rfft(sig * self.hanning))
        freqs = np.fft.rfftfreq(SAMPLES, 1/FS)
        
        # 2. Musikalische Analyse: Dominante Frequenz & Note (ab 40Hz)
        idx_max = np.argmax(fft_raw[20:]) + 20 
        pitch_hz = freqs[idx_max]
        note_name = librosa.hz_to_note(pitch_hz) if pitch_hz > 40 else "---"

        # 3. KI Features (12 MFCCs für detaillierte Klangfarbe)
        mfccs = np.mean(librosa.feature.mfcc(y=sig, sr=FS, n_mfcc=12), axis=1)
        
        name, conf = "---", 0.0
        if self.mode == "Collect":
            with open('instrument_data.csv', 'a', newline='') as f:
                csv.writer(f).writerow([datetime.datetime.now().isoformat()] + mfccs.tolist() + [self.current_label])
            name = f"REC: {self.current_label}"
        elif self.mode == "Predict" and self.model:
            try:
                probs = self.model.predict_proba(mfccs.reshape(1, -1))
                idx = np.argmax(probs)
                name, conf = self.model.classes_[idx], probs[idx] * 100
            except: pass
        
        self.payload_ready.emit(data, fft_raw, mfccs, name, conf, pitch_hz, note_name)

class InstrumentStudio(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Musical Instrument Studio v12.0")
        self.resize(1200, 950)
        self.last_accuracy = None
        
        central = QtWidgets.QWidget(); self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        
        # --- TOOLBAR ---
        ctrl = QtWidgets.QHBoxLayout()
        self.label_in = QtWidgets.QLineEdit(); self.label_in.setPlaceholderText("Note/Akkord...")
        self.label_in.setFixedWidth(200)
        self.btn_collect = QtWidgets.QPushButton("● RECORD"); self.btn_collect.setCheckable(True)
        self.btn_collect.setStyleSheet("QPushButton:checked { background-color: #c0392b; color: white; }")
        self.btn_predict = QtWidgets.QPushButton("▶ PREDICT"); self.btn_predict.setCheckable(True)
        self.btn_predict.setStyleSheet("QPushButton:checked { background-color: #27ae60; color: white; }")
        self.btn_train = QtWidgets.QPushButton("🚀 Train AI")
        self.btn_clear = QtWidgets.QPushButton("🗑 Clear")
        self.led = QtWidgets.QLabel(); self.led.setFixedSize(16,16); self.update_led("red")
        
        for w in [self.label_in, self.btn_collect, self.btn_predict, self.btn_train, self.btn_clear, self.led]:
            ctrl.addWidget(w)
        layout.addLayout(ctrl)

        # --- STATUS PANEL ---
        self.status = QtWidgets.QLabel("Status: MONITOR MODE")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("font-size: 22px; font-weight: bold; background: #1a1a1a; color: #00ff00; padding: 12px; border-radius: 5px;")
        layout.addWidget(self.status)

        # --- PLOTS ---
        self.win = pg.GraphicsLayoutWidget(); layout.addWidget(self.win)
        
        # Plot 1: Oszilloskop (Zeitbereich inkl. Lage)
        self.p1 = self.win.addPlot(title="Instrument Schwingung (Z-Achse Rohdaten)")
        self.p1.setYRange(-2.5, 2.5); self.p1.setMouseEnabled(y=False)
        self.curve1 = self.p1.plot(pen='c')
        self.win.nextRow()
        
        # Plot 2: Spektrum (Frequenzbereich fixiert)
        self.p2 = self.win.addPlot(title="Klang-Spektrum (Obertöne)")
        self.p2.setLabel('bottom', "Frequenz", units='Hz')
        self.p2.setXRange(0, 2500) # Musikalisch wichtigster Bereich
        self.p2.setYRange(0, 20)   # Fixierte Amplitude für Vergleichbarkeit
        self.p2.setMouseEnabled(y=False)
        self.curve2 = self.p2.plot(pen='m')
        self.win.nextRow()
        
        # Plot 3: MFCC Fingerabdruck
        self.p3 = self.win.addPlot(title="Klangfarben-Fingerabdruck (MFCC)")
        self.p3.setYRange(-25, 160); self.p3.setMouseEnabled(y=False)
        x_ax = self.p3.getAxis('bottom')
        names = ["Energy", "Bass", "L-Mid", "Mid", "H-Mid", "Pres.", "Brill.", "Treb.", "M9", "M10", "M11", "M12"]
        x_ax.setTicks([[(i, names[i]) for i in range(len(names))]])
        self.mfcc_bar = pg.BarGraphItem(x=np.arange(12), height=np.zeros(12), width=0.5, brush='#3498db')
        self.p3.addItem(self.mfcc_bar)

        # Worker & Thread
        self.worker = AudioWorker(); self.thread = QtCore.QThread()
        self.worker.moveToThread(self.thread)
        self.worker.payload_ready.connect(self.update_ui)
        self.thread.started.connect(self.worker.run); self.thread.start()
        
        self.btn_collect.clicked.connect(self.toggle_collect)
        self.btn_predict.clicked.connect(self.toggle_predict)
        self.btn_train.clicked.connect(self.train)
        self.btn_clear.clicked.connect(self.clear_data)

    def update_led(self, color):
        self.led.setStyleSheet(f"background-color: {color}; border-radius: 8px; border: 1px solid #555;")

    def toggle_collect(self, checked):
        if checked: self.btn_predict.setChecked(False); self.worker.mode = "Collect"
        else: self.worker.mode = "Monitor"
        self.worker.current_label = self.label_in.text()

    def toggle_predict(self, checked):
        if checked:
            if not self.worker.model: 
                QtWidgets.QMessageBox.warning(self, "Fehler", "Kein Modell vorhanden!")
                self.btn_predict.setChecked(False); return
            self.btn_collect.setChecked(False); self.worker.mode = "Predict"
        else: self.worker.mode = "Monitor"

    def clear_data(self):
        if QtWidgets.QMessageBox.question(self, "Löschen", "Alle Daten & Modell löschen?") == QtWidgets.QMessageBox.Yes:
            if os.path.exists('instrument_data.csv'): os.remove('instrument_data.csv')
            if os.path.exists('instrument_ai.pkl'): os.remove('instrument_ai.pkl')
            self.worker.model = None; self.status.setText("Daten gelöscht.")

    def train(self):
        try:
            import pandas as pd
            from sklearn.ensemble import RandomForestClassifier
            df = pd.read_csv('instrument_data.csv', header=None)
            X = df.iloc[:, 1:-1].apply(pd.to_numeric, errors='coerce')
            y = df.iloc[:, -1]
            clf = RandomForestClassifier(n_estimators=100, random_state=42).fit(X.dropna(), y.loc[X.dropna().index])
            joblib.dump(clf, 'instrument_ai.pkl'); self.worker.load_model()
            QtWidgets.QMessageBox.information(self, "Erfolg", f"KI trainiert mit {len(X)} Proben!")
        except Exception as e: QtWidgets.QMessageBox.warning(self, "Fehler", f"Training: {e}")

    @Slot(np.ndarray, np.ndarray, np.ndarray, str, float, float, str)
    def update_ui(self, t, f, m, name, conf, hz, note):
        self.curve1.setData(t[:ZOOM_SAMPLES])
        self.curve2.setData(np.fft.rfftfreq(SAMPLES, 1/FS), f)
        self.mfcc_bar.setOpts(height=m)
        self.update_led("#0f0")
        if hasattr(self, 'lt'): self.lt.stop()
        self.lt = QtCore.QTimer.singleShot(800, lambda: self.update_led("red"))

        # Pegel-Check gegen Rauschen
        is_active = m[0] > 15 # Energie-Check
        
        if self.worker.mode == "Predict":
            note_info = f" | 🎵 {note} ({hz:.1f} Hz)" if is_active else ""
            self.status.setText(f"ERKANNT: {name.upper()} ({conf:.1f}%){note_info}")
            self.status.setStyleSheet("font-size: 22px; font-weight: bold; background: #1b5e20; color: white; padding: 12px;")
        elif self.worker.mode == "Collect":
            self.status.setText(f"LERNEN FÜR: {name.upper()}")
            self.status.setStyleSheet("font-size: 22px; font-weight: bold; background: #b71c1c; color: white; padding: 12px;")
        else:
            note_info = f"🎵 {note} ({hz:.1f} Hz)" if is_active else "---"
            self.status.setText(f"MONITOR: {note_info}")
            self.status.setStyleSheet("font-size: 22px; font-weight: bold; background: #1a1a1a; color: #00ff00; padding: 12px;")

    def closeEvent(self, e):
        self.worker.running = False; self.thread.quit(); self.thread.wait(2000); e.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv); app.setStyle('Fusion')
    s = InstrumentStudio(); s.show(); sys.exit(app.exec())
