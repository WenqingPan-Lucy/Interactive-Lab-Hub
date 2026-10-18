
import time
import board
import pi_servo_hat
from adafruit_apds9960.apds9960 import APDS9960

# Servo settings
SERVO_CHANNEL = 0
CLOSED_ANGLE = 0
OPEN_ANGLE = 110

# Minimum time between actions
COOLDOWN = 1.5

# Initialize gesture sensor
i2c = board.I2C()
apds = APDS9960(i2c)
apds.enable_proximity = True
apds.enable_gesture = True

# Initialize servo motor
servo = pi_servo_hat.PiServoHat()
servo.restart()

# Initially, the candy box is closed
box_open = False
current_angle = CLOSED_ANGLE
last_action = 0

servo.move_servo_position(SERVO_CHANNEL, CLOSED_ANGLE)

print("Candy Box is ready!")
print("Swipe UP to OPEN the box.")
print("Swipe DOWN to CLOSE the box.")

try:
    while True:

        # Detect hand gesture
        gesture = apds.gesture()
        now = time.monotonic()


        # DOWN gesture: OPEN the candy box
        if gesture == 0x02 and not box_open:
            if now - last_action >= COOLDOWN:
                target_angle = OPEN_ANGLE
                print("DOWN detected! Opening candy box...")
            else:
                time.sleep(0.05)
                continue

        # UP gesture: CLOSE the candy box
        elif gesture == 0x01 and box_open:
            if now - last_action >= COOLDOWN:
                target_angle = CLOSED_ANGLE
                print("UP detected! Closing candy box...")
            else:
                time.sleep(0.05)
                continue

        else:
            time.sleep(0.05)
            continue

        # Move servo smoothly
        step = 1 if target_angle > current_angle else -1

        for angle in range(
            current_angle,
            target_angle + step,
            step
        ):
            servo.move_servo_position(SERVO_CHANNEL, angle)
            time.sleep(0.02)

        # Update current position and box state
        current_angle = target_angle
        box_open = (target_angle == OPEN_ANGLE)
        last_action = time.monotonic()

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nCandy Box stopped.")
