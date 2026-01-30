import matplotlib.pyplot as plt
import serial
import time
import numpy as np
import matplotlib.mlab as mlab
import matplotlib.gridspec as gridspec
import struct # Struct erlaubt den Datastream einzuteilen in 2er paare. Kann damit die bytes einlsen

gelesenes = np.zeros(4)
values = []
x = 0
zeit = 0
arduino = serial.Serial(port='COM8', baudrate=115200)

while(arduino.in_waiting): #Clearen des Ports
    arduino.flushInput()



num = input("Enter a number: ")
arduino.write(bytes(num,  'utf-8'))
num = int(num)

#iterations = input("Enter iteratons: ")
#arduino.write(bytes(iterations,  'utf-8'))
#iterations = int(iterations)  

for x in range(num):
    

        gelesenes =struct.unpack('i', arduino.read(4))[0]#Einlesen des Wertes am seriellen Port
        values.append(gelesenes)   #Weitergeben an Liste
        

zeit = struct.unpack('i', arduino.read(4))[0] 
print(len(values))
print(zeit)
 

#np.savetxt('9mA_360K_2.txt', values) 
arduino.close()

values.pop(0)
timeaxis = [(x * 5) for x in range(len(values))]

plt.plot(timeaxis , values)

plt.show()
plt.close()

#i_values = [sum(values[i:i+100])/100 for i in range(0, len(values), 100)]
#i_timeaxis = [(x * 50) for x in range(len(i_values))]
#plt.plot(i_timeaxis,i_values)

#plt.show()
#plt.close()
arduino.close()