#include <SPI.h>
#include <WiFi.h>
#include <WiFiUdp.h>

// --- KONFIGURATION ---
const char* ssid     = "Eureek";
const char* password = "123456789";
const char* hostIP   = "10.176.66.73"; 
const int port       = 5005;

WiFiUDP udp;
#define SAMPLES 4096
#define CHUNK_SIZE 512 
float dataBuffer[SAMPLES];
const int samplingInterval = 125; // 8kHz exakt

// SPI Setup
static const int PIN_SCK  = 18;
static const int PIN_MISO = 16;
static const int PIN_MOSI = 19;
static const int CS_PIN   = 33;
SPISettings adxlSPI(1000000, MSBFIRST, SPI_MODE0);

// --- HILFSFUNKTIONEN ---
void adxl_write8(uint8_t addr, uint8_t data) {
    SPI.beginTransaction(adxlSPI);
    digitalWrite(CS_PIN, LOW);
    SPI.transfer((addr << 1) | 0);
    SPI.transfer(data);
    digitalWrite(CS_PIN, HIGH);
    SPI.endTransaction();
}

// Direkter Read aus den Daten-Registern (Bypass FIFO)
int16_t adxl_read_z_direct() {
    SPI.beginTransaction(adxlSPI);
    digitalWrite(CS_PIN, LOW);
    // Wir starten bei REG_ZDATA_H (0x19)
    SPI.transfer((0x19 << 1) | 1); 
    uint8_t h = SPI.transfer(0x00);
    uint8_t l = SPI.transfer(0x00);
    digitalWrite(CS_PIN, HIGH);
    SPI.endTransaction();
    return (int16_t)((h << 8) | l);
}

void setup() {
    Serial.begin(115200);
    pinMode(CS_PIN, OUTPUT);
    digitalWrite(CS_PIN, HIGH);
    SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, CS_PIN);

    // WiFi
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
    Serial.println("\nWiFi OK!");

    // --- SENSOR SETUP (NORMAL MODE / BYPASS) ---
    adxl_write8(0x26, 0x00); // Standby
    delay(10);
    adxl_write8(0x27, 0x48); // Z-Achse an
    adxl_write8(0x28, 0x00); // Filter auf max (8kHz ODR)
    adxl_write8(0x30, 0x00); // FIFO BYPASS MODE (Deaktiviert den FIFO)
    adxl_write8(0x26, 0x0C); // Messung an (High Power)
    delay(50);
}

void loop() {
    // 1. DATEN ERFASSEN (Präzises 8kHz Timing)
    unsigned long nextSampleTime = micros();
    
    for (int i = 0; i < SAMPLES; i++) {
        while (micros() < nextSampleTime);
        nextSampleTime += samplingInterval;
        
        // Wir lesen direkt den aktuellen Wert
        int16_t raw = adxl_read_z_direct();
        dataBuffer[i] = (float)raw / 7500.0f;
    }

    // 2. WIFI SENDEN (In Chunks)
    uint8_t* bytePtr = (uint8_t*)dataBuffer;
    uint32_t chunkID = 0;
    int chunkBytes = CHUNK_SIZE * sizeof(float);

    for (int offset = 0; offset < (SAMPLES * 4); offset += chunkBytes) {
        udp.beginPacket(hostIP, port);
        udp.write((uint8_t*)&chunkID, sizeof(chunkID)); 
        udp.write(bytePtr + offset, chunkBytes);
        udp.endPacket();
        chunkID++;
        delayMicroseconds(400); 
    }
    Serial.println("Batch gesendet");
}
