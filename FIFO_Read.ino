#include <SPI.h>

// ADXL380 Register
#define REG_FIFO_DATA       0x11
#define REG_DIG_EN          0x27 
#define REG_POWER_CTL       0x2D
#define REG_INT_MAP         0x2E
#define REG_FIFO_CFG0       0x30 
#define REG_FIFO_CFG1       0x31 
#define REG_FIFO_ENTRIES    0x1E

const int CS_PIN = 5;
const int INT_PIN = 4;
const int MAX_SAMPLES = 6400;

// Globales Array zur Vermeidung von Stack-Problemen
int16_t zSamples[MAX_SAMPLES]; 
volatile int currentSampleCount = 0;
volatile bool fifoFullFlag = false;

void IRAM_ATTR isr() {
  fifoFullFlag = true;
}

void setup() {
  Serial.begin(115200); // Hohe Baudrate für schnellen Plot
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);
  pinMode(INT_PIN, INPUT);
  
  SPI.begin();
  attachInterrupt(digitalPinToInterrupt(INT_PIN), isr, RISING);

  initADXL380();
}

void loop() {
  // 1. Daten sammeln bis 6400 erreicht sind
  if (fifoFullFlag && currentSampleCount < MAX_SAMPLES) {
    fifoFullFlag = false;
    readZAxisFIFO();
  }

  // 2. Wenn voll: Visualisieren und Reset
  if (currentSampleCount >= MAX_SAMPLES) {
    visualizeData();
    
    // Reset für den nächsten Durchlauf
    currentSampleCount = 0;
    Serial.println("--- Neustart der Messung ---");
    
    // Optional: FIFO leeren, um Altlasten zu vermeiden
    writeReg(REG_FIFO_CFG0, 0x00); // FIFO Reset
    writeReg(REG_FIFO_CFG0, 0x02); // FIFO wieder an
  }
}

void readZAxisFIFO() {
  int entries = readReg(REG_FIFO_ENTRIES);
  
  digitalWrite(CS_PIN, LOW);
  SPI.transfer((REG_FIFO_DATA << 1) | 0x01); 

  for (int i = 0; i < entries; i++) {
    int16_t raw = (SPI.transfer(0x00) << 8) | SPI.transfer(0x00);
    if (currentSampleCount < MAX_SAMPLES) {
      zSamples[currentSampleCount++] = raw;
    }
  }
  digitalWrite(CS_PIN, HIGH);
}

void visualizeData() {
  // Format für den Arduino Seriellen Plotter: Ein Wert pro Zeile
  for (int i = 0; i < MAX_SAMPLES; i++) {
    // Umrechnung in g (Beispiel für ±4g Bereich)
    float gValue = zSamples[i] * 0.00075; 
    Serial.println(gValue); 
    
    // Kleiner Delay, damit der Serial-Buffer nicht überläuft
    if (i % 100 == 0) delay(1); 
  }
}

void initADXL380() {
  writeReg(REG_DIG_EN, 0x48);    // Nur Z-Achse + FIFO EN
  writeReg(REG_FIFO_CFG0, 0x02); // Stream Mode
  writeReg(REG_FIFO_CFG1, 300);  // Watermark fast voll (300/320)
  writeReg(REG_INT_MAP, 0x01);   // Watermark auf INT1
  writeReg(REG_POWER_CTL, 0x02); // Start
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
