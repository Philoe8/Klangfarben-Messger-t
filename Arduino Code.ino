// ESP32 sketch for single photon counting
// in combination with Hamamatsu H12775 photon counting head
// Ulrich T. Schwarz, 22.7.2022
// based on https://blog.eletrogate.com/esp32-frequencimetro-de-precisao
// by Rui Viana e Gustavo Murta agosto/2020

#include "stdio.h"
#include "driver/pcnt.h"                                                  // PCNT library
#include "soc/pcnt_struct.h"                                              // see https://www.esp32.com/viewtopic.php?t=2890

#define PCNT_COUNT_UNIT       PCNT_UNIT_3                                 // use pcnt unit 0 and channel 0 as pulse counter
#define PCNT_COUNT_CHANNEL    PCNT_CHANNEL_0

#define PCNT_INPUT_SIG_IO     GPIO_NUM_34                                 // pulse counting intput
#define PCNT_INPUT_CTRL_IO    GPIO_NUM_15                                 // pcnt control input - HIGH = count up, LOW = count down
#define OUTPUT_CONTROL_GPIO   GPIO_NUM_32                                 // timer gate, connected to GPIO15
#define PCNT_H_LIM_VAL        cnt_overflow                                // maximum count before counter is resetted

hw_timer_t *Timer0_Cfg = NULL;

volatile bool   flag          = true;                                     // Indicates completion of gate time
uint32_t        cnt_overflow  = 20000;                                    // count maximum, resulting in overflow PCNT
int16_t         pulses        = 0;                                        // number of pulses counted
volatile uint32_t multPulses    = 0;                                      // number of PCNT counter overflows
uint32_t        gate          = 5000;                                  // gate time in microseconds
int             frequence     = 0;                                        // calculated frequency
int valuearray[20000];                                                              //Zaehlt wie viele Werte man bisher hat


esp_timer_create_args_t create_args;                                      // ESP-Timer arguments
esp_timer_handle_t timer_handle;                                          // ESP-Timer instance

portMUX_TYPE timerMux = portMUX_INITIALIZER_UNLOCKED;                     // variabel type portMUX_TYPE for synchronization


//----------------------------------------------------------------------------------------
void setup()
{
  Serial.begin(115200);

  initialize_frequency_counter();
}

//----------------------------------------------------------------------------------
static void IRAM_ATTR pcnt_intr_handler(void *arg)                        // callback on counter overflow
{
  portENTER_CRITICAL_ISR(&timerMux);                                      // block interrupts
  multPulses++;                                                           // increment overflow counter
  PCNT.int_clr.val = BIT(PCNT_COUNT_UNIT);                                // reset interrupt flag
  portEXIT_CRITICAL_ISR(&timerMux);                                       // allow interrups
}

//----------------------------------------------------------------------------------
void initialise_counter(void)                                             // Initialise pulse counter
{
  pcnt_config_t pcnt_config = { };                                        // Instance for PCNT configuration

  pcnt_config.pulse_gpio_num = PCNT_INPUT_SIG_IO;                         // Configure GPIO to count pulses
  pcnt_config.ctrl_gpio_num = PCNT_INPUT_CTRL_IO;                         // Configura GPIO for pcnt control
  pcnt_config.unit = PCNT_COUNT_UNIT;                                     // pcnt counter unit 0
  pcnt_config.channel = PCNT_COUNT_CHANNEL;                               // pcnt canal 0
  pcnt_config.counter_h_lim = PCNT_H_LIM_VAL;                             // set counting limit before reset
  pcnt_config.pos_mode = PCNT_COUNT_INC;                                  // count positive edges
  pcnt_config.neg_mode = PCNT_COUNT_INC;                                  // and also count negative edges
  pcnt_config.lctrl_mode = PCNT_MODE_DISABLE;                             // disable lctrl
  pcnt_config.hctrl_mode = PCNT_MODE_KEEP;                                // enablt hctrl - counting when control port is HIGH
  pcnt_unit_config(&pcnt_config);                                         // send configuration to pcnt counter

  pcnt_counter_pause(PCNT_COUNT_UNIT);                                    // pause counter
  pcnt_counter_clear(PCNT_COUNT_UNIT);                                    // clear counter

  pcnt_event_enable(PCNT_COUNT_UNIT, PCNT_EVT_H_LIM);                     // configure interrupt when limit has been reached
  pcnt_isr_register(pcnt_intr_handler, NULL, 0, NULL);                    // configure interrupt handler
  pcnt_intr_enable(PCNT_COUNT_UNIT);                                      // enable counter

  pcnt_counter_resume(PCNT_COUNT_UNIT);                                   // start counter
}

//----------------------------------------------------------------------------------
void time_control(void *p)                                                // callback at end of gate time
{
  gpio_set_level(OUTPUT_CONTROL_GPIO, 0);                                 // control gate: stop counting
  pcnt_get_counter_value(PCNT_COUNT_UNIT, &pulses);                       // get pcnt counter value
  flag = true;                                                            // inform main loop that counting cycle is completed
}

//---------------------------------------------------------------------------------
void initialize_frequency_counter()
{
  // inicializa_oscilador ();                                             // initializes oscillator
  initialise_counter();                                                   // initializes PCNT counter

  gpio_pad_select_gpio(OUTPUT_CONTROL_GPIO);                              // Define control port
  gpio_set_direction(OUTPUT_CONTROL_GPIO, GPIO_MODE_OUTPUT);              // ... as output

  create_args.callback = time_control;                                    // Instance for gate control time callback
  esp_timer_create(&create_args, &timer_handle);                          // set timer parameters

  gpio_matrix_in(PCNT_INPUT_SIG_IO, SIG_IN_FUNC226_IDX, false);           // Directiona of input pulses
}


//---------------------------------------------------------------------------------


void  loop() 
{ 
  while (!Serial.available()); //Solange nichts im Buffer ist wartet der Arudino
  {
    
  }
  int rounds; //Anzahl er Durchgänge. Wird beim readen eingelesen
  //int iterations;
  

  rounds = Serial.readString().toInt(); // Konvertierung der Zahl in int und rounds wird eingelesen vom python
  //iterations = Serial.readString().toInt();
  int startzeit = micros();  

  pcnt_counter_clear(PCNT_COUNT_UNIT);                                // clear pcnt counter
  esp_timer_start_once(timer_handle, 5000);                           // initialize counter for gate time
  gpio_set_level(OUTPUT_CONTROL_GPIO, 1);                             // set control port to enable counting

    

  for(int i = 0; i < rounds;i++) //Anzahl er Durchläufe. Angegeben durch die eingelesene rounds variable
  {
    while(flag == false)
    {

    }
    if (flag == true)                                                       // if cycle terminated (gate time passed)
  {
    flag = false;                                                         // enable new cycle
    frequence = (pulses + (multPulses * cnt_overflow));                   // calculate number of pulses (not deviding by 2, i.e. counting rising and falling edges
    multPulses = 0;                                                       // clear overflow counter

    pcnt_counter_clear(PCNT_COUNT_UNIT);                                // clear pcnt counter
    esp_timer_start_once(timer_handle, 5000);                           // initialize counter for gate time
    gpio_set_level(OUTPUT_CONTROL_GPIO, 1);                             // set control port to enable counting
      
    Serial.write((byte*)&frequence,4);
    //valuearray[i] = frequence;  
    //Serial.println(frequence);
  }
  }
  //int messzeit = micros() - startzeit;

  //for(int j = 0;j<rounds;j++)
    //{
      
      
      //Serial.write((byte*)&valuearray[j],4);    
    //}
//}
  int messzeit = micros() - startzeit;

  Serial.write((byte*)&messzeit,4);  
}
  