

import serial
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import librosa
import platform

# --- KONFIGURATION ---
PORT = '/dev/cu.usbserial-016135F7'
BAUD = 921600
SAMPLES = 4096
FS = 8000
HEADER = b'\x02'

def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        if platform.system() == 'Windows':
            ser.set_buffer_size(rx_size=65536)
        ser.reset_input_buffer()
        print(f"Verbunden mit {PORT}")
    except Exception as e:
        print(f"Fehler: {e}")
        return

    plt.ion()
    fig = plt.figure(figsize=(15, 10))
    gs = fig.add_gridspec(2, 2, width_ratios=[2, 1]) # Links breit, rechts schmaler

    # 1. Zeitbereich (Links Oben)
    ax1 = fig.add_subplot(gs[0, 0])
    x_time_ms = np.linspace(0, SAMPLES/FS, SAMPLES) * 1000
    line_signal, = ax1.plot(x_time_ms, np.zeros(SAMPLES), color='#1f77b4', lw=1)
    ax1.set_xlim(0, 25)
    ax1.set_ylim(-1.2, 1.2)
    ax1.set_title("Zeitbereich-Signal (ms)")
    ax1.set_xlabel("Zeit [ms]")
    ax1.set_ylabel("Amplitude")

    # 2. Frequenzbereich (Links Unten)
    ax2 = fig.add_subplot(gs[1, 0])
    xf = np.fft.rfftfreq(SAMPLES, 1/FS)
    line_fft, = ax2.plot(xf, np.zeros(len(xf)), color='#d62728', lw=1.5)
    peak_dots, = ax2.plot([], [], "kx", markersize=7)
    ax2.set_xlim(0, 3000)
    ax2.set_ylim(0, SAMPLES/4)
    ax2.set_title("Frequenzspektrum (FFT)")
    ax2.set_xlabel("Frequenz [Hz]")
    ax2.set_ylabel("Magnitude")

    # 3. MFCCs (Rechts Oben/Mitte)
    ax3 = fig.add_subplot(gs[:, 1]) # Belegt die komplette rechte Spalte
    n_mfcc = 13
    line_mfcc = ax3.barh(range(n_mfcc), np.zeros(n_mfcc), color='#2ca02c')
    ax3.set_yticks(range(n_mfcc))
    ax3.set_yticklabels([f"MFCC {i}" for i in range(n_mfcc)])
    ax3.invert_yaxis() # MFCC 0 oben
    ax3.set_title("Klangfarben-Fingerabdruck (MFCCs)")
    ax3.set_xlabel("Koeffizient-Wert")

    # Info-Text für Merkmale (Rechts im MFCC Plot eingebettet)
    info_text = ax3.text(0.05, 0.02, '', transform=ax3.transAxes, 
                         bbox=dict(boxstyle='round', fc='white', alpha=0.9), verticalalignment='bottom')
    
    annotations = []
    plt.tight_layout()

    try:
        while True:
            if ser.read() == HEADER:
                raw_bytes = ser.read(SAMPLES * 4)
                if len(raw_bytes) == SAMPLES * 4:
                    data = np.frombuffer(raw_bytes, dtype='<f4').copy()
                    
                    # Normalisierung & Features
                    max_abs = np.max(np.abs(data))
                    norm_data = data / max_abs if max_abs > 1e-6 else data
                    fft_values = np.abs(np.fft.rfft(norm_data * np.hanning(SAMPLES)))
                    
                    # Berechnung Spektrale Merkmale
                    sum_fft = np.sum(fft_values)
                    if sum_fft > 1e-6:
                        centroid = np.sum(xf * fft_values) / sum_fft
                        bandwidth = np.sqrt(np.sum(((xf - centroid)**2) * fft_values) / sum_fft)
                        # Roll-off (sicherer Zugriff)
                        cum_energy = np.cumsum(fft_values)
                        rolloff_idx = np.where(cum_energy >= 0.95 * cum_energy[-1])[0]
                        rolloff_freq = xf[rolloff_idx[0]] if len(rolloff_idx) > 0 else 0
                    else:
                        centroid = bandwidth = rolloff_freq = 0

                    # MFCCs
                    mfccs = librosa.feature.mfcc(y=norm_data, sr=FS, n_mfcc=n_mfcc)
                    mfccs_mean = np.mean(mfccs, axis=1)

                    # --- Visualisierung ---
                    line_signal.set_ydata(norm_data)
                    line_fft.set_ydata(fft_values)
                    
                    # MFCC Balken (horizontal)
                    for rect, val in zip(line_mfcc, mfccs_mean):
                        rect.set_width(val)
                    m_min, m_max = np.min(mfccs_mean), np.max(mfccs_mean)
                    ax3.set_xlim(m_min - 20, m_max + 20)

                    # Peaks beschriften
                    peaks, _ = find_peaks(fft_values, height=np.max(fft_values)*0.15)
                    peak_dots.set_data(xf[peaks], fft_values[peaks])
                    for ann in annotations: ann.remove()
                    annotations.clear()
                    for p in peaks:
                        ann = ax2.annotate(f"{xf[p]:.0f}Hz", xy=(xf[p], fft_values[p]), 
                                         xytext=(0,5), textcoords="offset points", ha='center', fontsize=8)
                        annotations.append(ann)

                    # Beschriftung der Audio-Features
                    stats = (f"Audio-Features:\n"
                             f"--------------------\n"
                             f"Helligkeit (Centroid): {centroid:.0f} Hz\n"
                             f"Bandbreite: {bandwidth:.0f} Hz\n"
                             f"Roll-off (95%): {rolloff_freq:.0f} Hz")
                    info_text.set_text(stats)

                    fig.canvas.draw_idle()
                    fig.canvas.flush_events()
                else:
                    ser.reset_input_buffer()
    except KeyboardInterrupt:
        print("\nMessung beendet.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
