#!/usr/bin/env python3

import time
import board
import busio
import adafruit_mpr121

# Connect to MPR121 through I2C
i2c = busio.I2C(board.SCL, board.SDA)
mpr121 = adafruit_mpr121.MPR121(i2c)

print("MPR121 ready!")
print("Touch pad 6 to test. Press Ctrl-C to stop.")

while True:
    if mpr121[6].value:
        print("Pad 6 touched!")

        # Wait until the user releases it
        while mpr121[6].value:
            time.sleep(0.05)

        print("Pad 6 released.")

    time.sleep(0.05)