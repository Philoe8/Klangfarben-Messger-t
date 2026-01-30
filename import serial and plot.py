import serial
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks


# --- KONFIGURATION ---
PORT = '/dev/cu.usbserial-01D18279' # Prüfe 'ls /dev/cu.*' im Terminal
BAUD = 921600
SAMPLES = 4096
FS = 8000
HEADER = b'\x02'

def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    
        print(f"Streaming gestartet auf {PORT}...")
    except Exception as e:
        print(f"Fehler: {e}")
        return

    # Plot Setup
    plt.ion()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    # 1. Zeitbereich-Plot (Beschriftung in Millisekunden)
    # x_time in Sekunden * 1000 = Millisekunden
    x_time_ms = np.linspace(0, SAMPLES/FS, SAMPLES) * 1000 
    line_signal, = ax1.plot(x_time_ms, np.zeros(SAMPLES), color='#1f77b4')
    ax1.set_xlim(0, 20) # Zeige die ersten 20 ms
    ax1.set_ylim(-1.5, 1.5)
    ax1.set_title("Zeitbereich (Oszilloskop)")
    ax1.set_xlabel("Zeit (ms)")
    ax1.set_ylabel("Amplitude")
    ax1.grid(True, alpha=0.3)

    # 2. Frequenzbereich-Plot
    xf = np.fft.rfftfreq(SAMPLES, 1/FS)
    line_fft, = ax2.plot(xf, np.zeros(len(xf)), color='#d62728')
    peak_dots, = ax2.plot([], [], "kx", markersize=8) 
    
    ax2.set_xlim(0, 2000) 
    ax2.set_ylim(0, SAMPLES/4)
    ax2.set_title("Frequenzbereich (FFT)")
    ax2.set_xlabel("Frequenz (Hz)")
    ax2.set_ylabel("Stärke")
    ax2.grid(True, alpha=0.3)

    # Liste für die Text-Labels der Peaks
    annotations = []

    plt.tight_layout()

    try:
        while True:
            if ser.read() == HEADER:
                raw_data = ser.read(SAMPLES * 4)
                if len(raw_data) == SAMPLES * 4:
                    data = np.frombuffer(raw_data, dtype='<f4').copy()
                    # ... nach dem Empfang der Daten ...

                    # --- NORMALISIERUNG ---
                    # max_val = np.max(np.abs(data))
                    # if max_val > 0:
                    #    data = data / max_val  # Jetzt liegt das Signal exakt zwischen -1.0 und 1.0
                    
                    # Update Signal
                    line_signal.set_ydata(data)
                    
                    # FFT & Peak Detection
                    fft_values = np.abs(np.fft.rfft(data * np.hanning(SAMPLES)))
                    line_fft.set_ydata(fft_values)
                    
                    peaks, _ = find_peaks(fft_values, height=np.max(fft_values)*0.15, distance=20)
                    peak_dots.set_data(xf[peaks], fft_values[peaks])
                    
                    # Alte Peak-Beschriftungen entfernen
                    for ann in annotations:
                        ann.remove()
                    annotations.clear()
                    
                    # Neue Peak-Beschriftungen hinzufügen
                    for p in peaks:
                        freq = xf[p]
                        val = fft_values[p]
                        # Annotate direkt über dem Peak platzieren
                        ann = ax2.annotate(f"{freq:.0f}Hz", 
                                         xy=(freq, val), 
                                         xytext=(0, 10), 
                                         textcoords="offset points",
                                         ha='center', va='bottom',
                                         fontsize=9, fontweight='bold',
                                         bbox=dict(boxstyle='round,pad=0.2', fc='yellow', alpha=0.5))
                        annotations.append(ann)
                    
                    fig.canvas.draw_idle()
                    fig.canvas.flush_events()
    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        ser.close()

if __name__ == "__main__":
    main()
