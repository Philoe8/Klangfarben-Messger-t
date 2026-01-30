#include <WiFi.h>
#include <WiFiUdp.h>

// --- KONFIGURATION ---
const char* ssid     = "FRITZ!Box 6660 Cable UP";
const char* password = "49581136885637492341";
const char* hostIP   = "192.168.178.42"; // IP deines Macs
const int port       = 5005;

WiFiUDP udp;
#define SAMPLES 4096
#define CHUNK_SIZE 512 // Floats pro Paket (2048 Bytes)
float dataBuffer[SAMPLES];
const int samplingInterval = 125; // 8kHz

void setup() {
    Serial.begin(115200);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi verbunden!");
    Serial.print("ESP32 IP: "); Serial.println(WiFi.localIP());
}

void loop() {
    // 1. Daten erfassen (Mix aus 3 Frequenzen)
    unsigned long nextSampleTime = micros();
    for (int i = 0; i < SAMPLES; i++) {
        while (micros() < nextSampleTime);
        nextSampleTime += samplingInterval;
        float t = (float)micros() / 1000000.0;
        dataBuffer[i] = 0.5 * sin(2 * PI * 440.0 * t) + 0.3 * sin(2 * PI * 880.0 * t);
    }

    // 2. In Chunks senden (passend für MTU)
    uint8_t* bytePtr = (uint8_t*)dataBuffer;
    int bytesToSend = SAMPLES * sizeof(float);
    int chunkBytes = CHUNK_SIZE * sizeof(float);

    for (int offset = 0; offset < bytesToSend; offset += chunkBytes) {
        udp.beginPacket(hostIP, port);
        udp.write(bytePtr + offset, chunkBytes);
        udp.endPacket();
        delayMicroseconds(200); // Entlastung für Wi-Fi Stack
    }
    
    delay(50); // Frame-Pause
}
