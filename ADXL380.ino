#include <SPI.h>

static const int PIN_SCK  = 5;  // SCK
static const int PIN_MISO = 19;  // MI
static const int PIN_MOSI = 18;  // MO
static const int CS_PIN   = 12;   // choose any free GPIO

SPISettings adxlSPI(200000, MSBFIRST, SPI_MODE0);

// Registers
static const uint8_t REG_DEVID   = 0x00;
static const uint8_t REG_STATUS3 = 0x14;

static const uint8_t REG_XDATA_H = 0x15;
static const uint8_t REG_XDATA_L = 0x16;
static const uint8_t REG_YDATA_H = 0x17;
static const uint8_t REG_YDATA_L = 0x18;
static const uint8_t REG_ZDATA_H = 0x19;
static const uint8_t REG_ZDATA_L = 0x1A;

static const uint8_t REG_OP_MODE = 0x26;
static const uint8_t REG_DIG_EN  = 0x27;
static const uint8_t FIFO_CFG0  = 0x30;
static const uint8_t REG_FIFO_DATA  = 0x1D;
int Status0 = 0b00000010;
int counter = 0;
uint16_t zvalue[6400];

static inline uint8_t CMD(uint8_t addr, bool read) {
  return (uint8_t)((addr << 1) | (read ? 1 : 0));
}

uint8_t adxl_read8(uint8_t addr) {
  uint8_t v;
  SPI.beginTransaction(adxlSPI);
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(CMD(addr, true));
  v = SPI.transfer(0x00);
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();
  return v;
}

void adxl_write8(uint8_t addr, uint8_t data) {
  SPI.beginTransaction(adxlSPI);
  digitalWrite(CS_PIN, LOW);
  SPI.transfer(CMD(addr, false));
  SPI.transfer(data);
  digitalWrite(CS_PIN, HIGH);
  SPI.endTransaction();
}

int16_t adxl_read16(uint8_t addrH, uint8_t addrL) {
  uint8_t h = adxl_read8(addrH);
  uint8_t l = adxl_read8(addrL);
  return (int16_t)((h << 8) | l);
}

// Convert counts to g using selected range bits from OP_MODE[7:6]
float counts_to_g(int16_t counts, uint8_t range_bits) {
  float lsb_per_g = 7500.0f;          // ±4g
  if (range_bits == 0x01) lsb_per_g = 3750.0f; // ±8g
  if (range_bits == 0x02) lsb_per_g = 1875.0f; // ±16g
  return (float)counts / lsb_per_g;
}


void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("Chekcpoint");
  pinMode(CS_PIN, OUTPUT);
  digitalWrite(CS_PIN, HIGH);

  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, CS_PIN);

  // 1) Verify comms
  uint8_t devid = adxl_read8(REG_DEVID);
  Serial.print("DEVID = 0x"); Serial.println(devid, HEX);

  // 2) Put in standby before config (datasheet requirement) :contentReference[oaicite:4]{index=4}
  adxl_write8(REG_OP_MODE, 0x00);
  delay(2);

  // 3) Enable Z and FIFO
  adxl_write8(REG_DIG_EN, 0x48); // Z only
  delay(2);

  // 4) Configurate FIFO
  adxl_write8(FIFO_CFG0, 0b00010000);
  delay(2);


  // 4) Enter HP mode, ±4g (RANGE bits [7:6]=00, OP_MODE[3:0]=1100) :contentReference[oaicite:6]{index=6}
  adxl_write8(REG_OP_MODE, 0x0C);
  delay(2);

  // 5) Read back what we wrote (this is the key!)
  uint8_t dig_en = adxl_read8(REG_DIG_EN);
  uint8_t op_mode = adxl_read8(REG_OP_MODE);
  //Serial.print("DIG_EN readback = 0x"); Serial.println(dig_en, HEX);
  //Serial.print("OP_MODE readback = 0x"); Serial.println(op_mode, HEX);

}

void loop() 
{
  //int Status = adxl_read8(REG_DIG_EN);
  //Serial.println(Status, BIN);
  //delay(100); //Status Abfrage Register welche Werte sind enabled
  if(counter == 6400)
  {
    counter = 0;
  }  
  if(counter < 6400)
  {
  if (adxl_read8(0x11) & (1 << 1))
    {
    
    SPI.beginTransaction(adxlSPI);
    digitalWrite(CS_PIN, LOW);
    SPI.transfer(REG_FIFO_DATA << 1|0x01);
    for (int i = 0; i<320;i++)
    {  
    uint8_t hi = SPI.transfer(0x00);
    uint8_t lo = SPI.transfer(0x00);
    digitalWrite(CS_PIN, HIGH);
    zvalue[counter] = (SPI.transfer(0x00) <<8)| SPI.transfer(0x00);
    //Serial.println(zvalue[counter]);
    Serial.println(counter);
    counter++;
    }
    digitalWrite(CS_PIN, HIGH);
    SPI.endTransaction();
    }
  }
  
} 

/*  int16_t z = adxl_read16(REG_ZDATA_H, REG_ZDATA_L);

  // Get range bits from OP_MODE[7:6]
  uint8_t op_mode = adxl_read8(REG_OP_MODE);
  uint8_t range_bits = (op_mode >> 6) & 0x03;

  // Convert to g

  float zg = counts_to_g(z, range_bits);

  // ---- Serial Plotter output (numbers only!) ----
  // Format: X  Y  Z
  Serial.print(xg, 5);
  Serial.print('\t');
  Serial.print(yg, 5);
  Serial.print('\t');
  Serial.println(zg, 5);

  delay(20);   // ~50 Hz update (adjust as you like)
  
}*/