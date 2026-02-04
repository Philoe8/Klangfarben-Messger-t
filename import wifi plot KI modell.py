import sys, numpy as np, socket, struct, pyqtgraph as pg, librosa, csv, datetime, os, joblib
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Signal, Slot, Qt
from scipy import signal, stats

# --- KONFIGURATION ---
UDP_IP, UDP_PORT = "0.0.0.0", 5005
SAMPLES, FS = 4096, 8000 
EXPECTED_BYTES = SAMPLES * 4
ZOOM_SAMPLES = 800 

class AudioWorker(QtCore.QObject):
    payload_ready = Signal(np.ndarray, np.ndarray, np.ndarray, str, float, list, list, float)

    def __init__(self):
        super().__init__()
        self.running, self.mode, self.current_label, self.model = True, "Monitor", "none", None
        self.noise_threshold = 0.02 
        self.hanning = np.hanning(SAMPLES)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.2)
        nyquist = FS / 2
        self.b, self.a = signal.butter(4, 55 / nyquist, btype='high')
        self.load_model()

    def load_model(self):
        if os.path.exists('vibr_ai_model.pkl'):
            try: 
                self.model = joblib.load('vibr_ai_model.pkl')
                return True
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
                        raw = np.frombuffer(full_data[:EXPECTED_BYTES], dtype='<f4').copy()
                        self.process_data(raw)
                        full_data = full_data[EXPECTED_BYTES:]
                except socket.timeout: continue
            self.sock.close()
        except Exception as e: print(f"UDP Error: {e}")

    def process_data(self, data):
        sig = signal.detrend(data - np.mean(data))
        rms = float(np.sqrt(np.mean(sig**2)))
        sig_f = signal.lfilter(self.b, self.a, sig)
        
        # FFT für Resonanzen
        sig_h = librosa.effects.harmonic(sig_f, margin=3.0)
        fft_raw = np.abs(np.fft.rfft(sig_h * self.hanning))
        fft_db = 20 * np.log10(fft_raw + 1e-5)
        freqs = np.fft.rfftfreq(SAMPLES, 1/FS)
        
        name, conf, peaks = "KEIN SIGNAL", 0.0, []
        mfccs = np.zeros(12); dash_feats = [0.0] * 5 

        if rms > self.noise_threshold:
            # Feature Extraktion
            centroid = np.mean(librosa.feature.spectral_centroid(y=sig_f, sr=FS))
            flatness = np.mean(librosa.feature.spectral_flatness(y=sig_f))
            rolloff = np.mean(librosa.feature.spectral_rolloff(y=sig_f, sr=FS))
            kurt = float(stats.kurtosis(sig_f))
            crest = np.max(fft_raw) / (np.mean(fft_raw) + 1e-6)
            
            dash_feats = [centroid/4000, flatness*20, rolloff/4000, min(1, crest/50), min(1, abs(kurt)/10)]
            mfccs = np.mean(librosa.feature.mfcc(y=sig_f, sr=FS, n_mfcc=12), axis=1)
            
            # Der Feature-Vektor (muss beim Training und Predict identisch sein!)
            all_feats = np.append(mfccs, [centroid, flatness, rolloff, crest, kurt])
            
            # Peaks
            idx = librosa.util.peak_pick(fft_raw, pre_max=30, post_max=30, pre_avg=30, post_avg=30, delta=0.5, wait=15)
            idx = sorted([i for i in idx if 55 < freqs[i] < 3800], key=lambda x: fft_raw[x], reverse=True)[:5]
            peaks = [{'hz': freqs[i], 'val': fft_db[i], 'note': librosa.hz_to_note(freqs[i])} for i in idx]

            if self.mode == "Collect":
                with open('vibr_data.csv', 'a', newline='') as f:
                    csv.writer(f).writerow([datetime.datetime.now().isoformat()] + all_feats.tolist() + [self.current_label])
                name = f"REC: {self.current_label}"
            elif self.mode == "Predict":
                if self.model:
                    try:
                        probs = self.model.predict_proba(all_feats.reshape(1, -1))[0]
                        best = np.argmax(probs)
                        conf = float(probs[best] * 100)
                        name = str(self.model.classes_[best])
                        if conf < 45.0: name = "UNSICHER"
                    except: 
                        name = "STRUKTUR-FEHLER"
                        conf = 0.0
                else: name = "KEIN MODELL"
        else:
            if self.mode == "Collect": name = "PAUSE (Leise)"

        self.payload_ready.emit(sig, fft_db, mfccs, name, conf, peaks, dash_feats, rms)

class InstrumentStudio(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Vibration Studio v27.0")
        self.resize(1200, 900)
        central = QtWidgets.QWidget(); self.setCentralWidget(central); layout = QtWidgets.QVBoxLayout(central)
        
        ctrl = QtWidgets.QHBoxLayout()
        self.label_in = QtWidgets.QLineEdit(); self.label_in.setPlaceholderText("Name...")
        self.btn_collect = QtWidgets.QPushButton("● RECORD"); self.btn_collect.setCheckable(True)
        self.btn_predict = QtWidgets.QPushButton("▶ PREDICT"); self.btn_predict.setCheckable(True)
        self.btn_train = QtWidgets.QPushButton("🚀 Train AI"); self.btn_clear = QtWidgets.QPushButton("🗑 Clear")
        self.lbl_count = QtWidgets.QLabel("Samples: 0")
        self.vu = QtWidgets.QProgressBar(); self.vu.setOrientation(Qt.Vertical); self.vu.setFixedWidth(12); self.vu.setTextVisible(False)
        self.sl_gate = QtWidgets.QSlider(Qt.Vertical); self.sl_gate.setRange(0, 100); self.sl_gate.setValue(20); self.sl_gate.setFixedHeight(60)
        
        for w in [self.label_in, self.btn_collect, self.btn_predict, self.btn_train, self.btn_clear, self.lbl_count, self.vu, self.sl_gate]: ctrl.addWidget(w)
        layout.addLayout(ctrl)
        
        self.status = QtWidgets.QLabel("Status: MONITOR"); self.status.setStyleSheet("font-size: 20px; font-weight: bold; background: #111; color: #555; padding: 10px;")
        layout.addWidget(self.status)
        
        self.win = pg.GraphicsLayoutWidget(); layout.addWidget(self.win)
        self.p1 = self.win.addPlot(title="Vibration Zeitbereich"); self.curve1 = self.p1.plot(pen='c')
        self.win.nextRow()
        self.p2 = self.win.addPlot(title="Frequenz-Spektrum"); self.p2.setXRange(0, 4000); self.curve2 = self.p2.plot(pen='m')
        self.peak_labels = [pg.TextItem(color='w', anchor=(0.5, 1)) for _ in range(5)]
        for lbl in self.peak_labels: lbl.hide(); self.p2.addItem(lbl)
        self.win.nextRow()
        self.p3 = self.win.addPlot(title="Timbre Dashboard"); self.p3.setYRange(0, 1.2)
        self.timbre_bar = pg.BarGraphItem(x=[1,2,3,4,5], height=[0,0,0,0,0], width=0.6, brushes=['#f1c40f','#e74c3c','#3498db','#9b59b6','#2ecc71'])
        self.p3.addItem(self.timbre_bar)
        self.p3.getAxis('bottom').setTicks([[(1,'Bright'), (2,'Noisy'), (3,'Roll'), (4,'Sharp'), (5,'Attack')]])

        self.worker = AudioWorker(); self.thread = QtCore.QThread()
        self.worker.moveToThread(self.thread); self.worker.payload_ready.connect(self.update_ui); self.thread.started.connect(self.worker.run); self.thread.start()
        self.sl_gate.valueChanged.connect(self.update_gate); self.btn_collect.clicked.connect(self.toggle_mode); self.btn_predict.clicked.connect(self.toggle_mode); self.btn_train.clicked.connect(self.train); self.btn_clear.clicked.connect(self.clear_data)
        self.refresh_counter()

    def update_gate(self, val): self.worker.noise_threshold = val / 500.0
    
    def refresh_counter(self):
        if os.path.exists('vibr_data.csv'):
            with open('vibr_data.csv', 'r') as f: self.lbl_count.setText(f"Samples: {sum(1 for _ in f)}")
        else: self.lbl_count.setText("Samples: 0")

    def toggle_mode(self):
        self.worker.mode = "Collect" if self.btn_collect.isChecked() else "Predict" if self.btn_predict.isChecked() else "Monitor"
        self.worker.current_label = self.label_in.text()

    def clear_data(self):
        if os.path.exists('vibr_data.csv'): os.remove('vibr_data.csv'); self.refresh_counter(); self.status.setText("DATEN GELÖSCHT")

    def train(self):
        try:
            import pandas as pd
            from sklearn.ensemble import RandomForestClassifier
            if not os.path.exists('vibr_data.csv'): return
            df = pd.read_csv('vibr_data.csv', header=None)
            
            # DIAGNOSE AUSGABE IM TERMINAL
            print(f"--- TRAINING DIAGNOSE ---")
            print(f"Anzahl Proben: {len(df)}")
            print(f"Anzahl Features (Spalten): {df.shape[1] - 2}") # Abzug Zeitstempel und Label
            
            X, y = df.iloc[:, 1:-1], df.iloc[:, -1]
            clf = RandomForestClassifier(n_estimators=100).fit(X, y)
            joblib.dump(clf, 'vibr_ai_model.pkl'); self.worker.load_model()
            QtWidgets.QMessageBox.information(self, "Erfolg", "KI trainiert & Prozent-Fix aktiv!")
        except Exception as e: QtWidgets.QMessageBox.warning(self, "Fehler", f"Fehler: {e}")

    @Slot(np.ndarray, np.ndarray, np.ndarray, str, float, list, list, float)
    def update_ui(self, t, f_db, m, name, conf, peaks, d_feats, rms):
        self.curve1.setData(t[:ZOOM_SAMPLES]); self.curve2.setData(np.fft.rfftfreq(SAMPLES, 1/FS), f_db); self.timbre_bar.setOpts(height=d_feats)
        vu_val = min(100, int(rms * 400)); self.vu.setValue(vu_val)
        self.vu.setStyleSheet(f"QProgressBar::chunk {{ background-color: {'#2ecc71' if vu_val > self.sl_gate.value() else '#e67e22'}; }}")
        for i, lbl in enumerate(self.peak_labels):
            if i < len(peaks): lbl.setText(f"{peaks[i]['hz']:.0f}Hz"); lbl.setPos(peaks[i]['hz'], peaks[i]['val']); lbl.show()
            else: lbl.hide()
        
        active = name not in ["KEIN SIGNAL", "UNSICHER", "PAUSE (Leise)", "STRUKTUR-FEHLER"]
        self.status.setStyleSheet(f"font-size: 20px; font-weight: bold; background: #111; color: {'#0f0' if active else '#ff9900' if 'FEHLER' in name else '#555'}; padding: 10px;")
        self.status.setText(f"{name} ({conf:.1f}%)")
        if self.worker.mode == "Collect": self.refresh_counter()

    def closeEvent(self, event): self.worker.running = False; self.thread.quit(); self.thread.wait(1000); event.accept()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv); app.setStyle("Fusion"); s = InstrumentStudio(); s.show(); sys.exit(app.exec())
