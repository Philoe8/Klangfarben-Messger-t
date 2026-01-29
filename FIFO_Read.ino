#include <SPI.h>

// ADXL380 Register (Auszug)
#define REG_FIFO_DATA       0x11
#define REG_DIG_EN          0x27  // Steuerung Achsen & FIFO
#define REG_POWER_CTL       0x2D
#define REG_INT_MAP         0x2E
#define REG_FIFO_CFG0       0x30  // FIFO Modus
#define REG_FIFO_CFG1       0x31  // FIFO Watermark
#define REG_FIFO_ENTRIES    0x1E

const int CS_PIN = 5;
const int INT_PIN = 4;
const int MAX_SAMPLES = 6400;

int16_t zSamples[MAX_SAMPLES]; // Array für 6400 Rohdaten-Punkte
volatile int currentSampleCount = 0;
volatile bool fifoThresholdReached = false;

void IRAM_ATTR isr() {
  fifoThresholdReached = true;
}

void setup() {
  Serial.begin(115200);
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);
  pinMode(INT_PIN, INPUT);
  
  SPI.begin();
  attachInterrupt(digitalPinToInterrupt(INT_PIN), isr, RISING);

  // 1. Nur Z-Achse und FIFO aktivieren (Z_EN = 0x40, FIFO_EN = 0x08 -> 0x48)
  writeReg(REG_DIG_EN, 0x48);

  // 2. FIFO Stream-Modus
  writeReg(REG_FIFO_CFG0, 0x02); 

  // 3. Watermark auf 310 setzen (FIFO fast voll)
  writeReg(REG_FIFO_CFG1, 0x36); // Beispielwert für hohe Füllrate

  // 4. Watermark-Interrupt auf INT1 mappen
  writeReg(REG_INT_MAP, 0x01); 

  // 5. Start (Measurement Mode)
  writeReg(REG_POWER_CTL, 0x02); 
  
  Serial.println("Messung gestartet...");
}

void loop() {
  if (fifoThresholdReached && currentSampleCount < MAX_SAMPLES) {
    fifoThresholdReached = false;
    readZAxisFIFO();
  }

  if (currentSampleCount >= MAX_SAMPLES) {
    Serial.println("Array voll! 6400 Samples gesammelt.");
    // Hier folgt die weitere Verarbeitung (z.B. FFT oder Senden)
    while(1); // Stoppt die Demo
  }
}

void readZAxisFIFO() {
  int entries = readReg(REG_FIFO_ENTRIES);
  
  digitalWrite(CS_PIN, LOW);
  SPI.transfer((REG_FIFO_DATA << 1) | 0x01); // Read-Bit

  for (int i = 0; i < entries; i++) {
    // Da nur Z-Achse aktiv, ist jeder Wert im FIFO ein Z-Sample
    int16_t raw = (SPI.transfer(0x00) << 8) | SPI.transfer(0x00);
    
    if (currentSampleCount < MAX_SAMPLES) {
      zSamples[currentSampleCount++] = raw;
    }
  }
  digitalWrite(CS_PIN, HIGH);
}

void writeReg(byte reg, byte val) {
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(reg << 1); 
  SPI.transfer(val);
  digitalWrite(CS_PIN, HIGH);
}

byte readReg(byte reg) {
  digitalWrite(CS_PIN, LOW);
  SPI.transfer((reg << 1) | 0x01);
  byte val = SPI.transfer(0x00);
  digitalWrite(CS_PIN, HIGH);
  return val;
}