import socket
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# --- KONFIGURATION ---
UDP_IP = "0.0.0.0" # Auf allen Schnittstellen lauschen
UDP_PORT = 5005
SAMPLES = 4096
FS = 8000
TOTAL_BYTES = SAMPLES * 4

def main():
    # 1. UDP Socket Setup
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
    print(f"Lausche auf UDP Port {UDP_PORT}...")

    # 2. Plot Setup
    plt.ion()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    
    x_time_ms = np.linspace(0, SAMPLES/FS, SAMPLES) * 1000
    line_signal, = ax1.plot(x_time_ms, np.zeros(SAMPLES), color='#1f77b4')
    ax1.set_xlim(0, 20)
    ax1.set_ylim(-1.5, 1.5)
    ax1.set_xlabel("Zeit (ms)")
    ax1.set_title("Kabelloses Oszilloskop (UDP)")

    xf = np.fft.rfftfreq(SAMPLES, 1/FS)
    line_fft, = ax2.plot(xf, np.zeros(len(xf)), color='#d62728')
    peak_dots, = ax2.plot([], [], "kx")
    ax2.set_xlim(0, 2000)
    ax2.set_ylim(0, SAMPLES/4)
    ax2.set_xlabel("Frequenz (Hz)")
    
    annotations = []

    try:
        while True:
            full_frame = b""
            # Sammle Chunks bis Frame voll ist
            while len(full_frame) < TOTAL_BYTES:
                packet, _ = sock.recvfrom(4096)
                full_frame += packet
            
            # Daten verarbeiten
            data = np.frombuffer(full_frame[:TOTAL_BYTES], dtype='<f4').copy()
            
            # Plots aktualisieren
            line_signal.set_ydata(data)
            
            fft_values = np.abs(np.fft.rfft(data * np.hanning(SAMPLES)))
            line_fft.set_ydata(fft_values)
            
            # Peak Detection & Beschriftung
            peaks, _ = find_peaks(fft_values, height=np.max(fft_values)*0.15)
            peak_dots.set_data(xf[peaks], fft_values[peaks])
            
            for ann in annotations: ann.remove()
            annotations.clear()
            
            for p in peaks:
                ann = ax2.annotate(f"{xf[p]:.0f}Hz", xy=(xf[p], fft_values[p]), 
                                 xytext=(0,10), textcoords="offset points", ha='center',
                                 bbox=dict(boxstyle='round', fc='yellow', alpha=0.5))
                annotations.append(ann)

            fig.canvas.draw_idle()
            fig.canvas.flush_events()

    except KeyboardInterrupt:
        print("\nBeendet.")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
