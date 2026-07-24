import os
import time
import threading
from gpiozero import OutputDevice, DigitalInputDevice

DATA_PIN = 23
CLOCK_PIN = 18
LATCH_PIN = 5
dataPin = OutputDevice(DATA_PIN)
clockPin = OutputDevice(CLOCK_PIN)
latchPin = OutputDevice(LATCH_PIN)
D1_PIN = 22
D2_PIN = 21
D3_PIN = 19
D4_PIN = 4

digits = [
    OutputDevice(D1_PIN),
    OutputDevice(D2_PIN),
    OutputDevice(D3_PIN),
    OutputDevice(D4_PIN)
]

# =========================
# Main 4 digit display
# Q0=DP, Q1=G, Q2=F, Q3=E, Q4=D, Q5=C, Q6=B, Q7=A
# =========================
def seg(A, B, C, D, E, F, G, DP=0):
    value = 0
    if DP: value |= 0b00000001
    if G:  value |= 0b00000010
    if F:  value |= 0b00000100
    if E:  value |= 0b00001000
    if D:  value |= 0b00010000
    if C:  value |= 0b00100000
    if B:  value |= 0b01000000
    if A:  value |= 0b10000000
    return value

sLetter = seg(1, 0, 1, 1, 0, 1, 1)
aLetter = seg(1, 1, 1, 0, 1, 1, 1)
fLetter = seg(1, 0, 0, 0, 1, 1, 1)
eLetter = seg(1, 0, 0, 1, 1, 1, 1)
rLetter = seg(0, 0, 0, 0, 1, 0, 1)
bLetter = seg(1, 1, 1, 1, 1, 1, 1)
mHalfLetter = seg(0, 0, 1, 0, 1, 0, 1)

safeMain = [sLetter, aLetter, fLetter, eLetter]
armedMain = [aLetter, rLetter, mHalfLetter, mHalfLetter]
breachMain = [bLetter, rLetter, eLetter, aLetter]

# =========================
# Second shift register
# Q0=DP, Q1=G, Q2=F, Q3=E, Q4=D, Q5=C, Q6=A, Q7=B
# =========================
def secondSeg(A, B, C, D, E, F, G, DP=0):
    value = 0
    if DP: value |= 0b00000001
    if G:  value |= 0b00000010
    if F:  value |= 0b00000100
    if E:  value |= 0b00001000
    if D:  value |= 0b00010000
    if C:  value |= 0b00100000
    if A:  value |= 0b01000000
    if B:  value |= 0b10000000
    return value

eDisplay = secondSeg(1, 0, 0, 1, 1, 1, 1) # E for ARMED
cDisplay = secondSeg(1, 0, 0, 1, 1, 1, 0) # C for BREACH

# =========================
# Third shift register
# Q0=A, Q1=B, Q2=C, Q3=D, Q4=E, Q5=F, Q6=G, Q7=DP
# =========================
def thirdSeg(A, B, C, D, E, F, G, DP=0):
    value = 0
    if A: value |= 0b00000001
    if B: value |= 0b00000010
    if C: value |= 0b00000100
    if D: value |= 0b00001000
    if E: value |= 0b00010000
    if F: value |= 0b00100000
    if G: value |= 0b01000000
    if DP: value |= 0b10000000
    return value

dDisplay = thirdSeg(0, 1, 1, 1, 1, 0, 1) # d for ARMED
hDisplay = thirdSeg(0, 1, 1, 0, 1, 1, 1) # H for BREACH

def shiftOut(value):
    for i in range(8):
        if value & (1 << i):
            dataPin.on()
        else:
            dataPin.off()

        clockPin.on()
        clockPin.off()

def send24(chip1, chip2, chip3):
    latchPin.off()
    shiftOut(chip3) # Last shift register first
    shiftOut(chip2) # Second shift register
    shiftOut(chip1) # First shift register
    latchPin.on()

# =========================
# Display
# =========================
displayState = "SAFE"
currentDigit = 0

def allDigitsOff():
    for digit in digits:
        digit.on()

def refreshDisplay():
    global currentDigit
    while True:
        allDigitsOff()

        if displayState == "SAFE":
            send24(safeMain[currentDigit], 0, 0)
        elif displayState == "ARMED":
            send24(armedMain[currentDigit], eDisplay, dDisplay)
        elif displayState == "BREACH":
            send24(breachMain[currentDigit], cDisplay, hDisplay)
        elif displayState == "OFF":
            send24(0, 0, 0)

        digits[currentDigit].off()

        currentDigit += 1
        if currentDigit >= 4:
            currentDigit = 0

        time.sleep(0.003)


allDigitsOff()
thread = threading.Thread(target=refreshDisplay)
thread.daemon = True
thread.start()

# =========================
# 1-Wire Signal
# =========================
commsPin = DigitalInputDevice(17, pull_up=False)
print("Listening for state changes on GPIO 17...")

stateChanges = 0
lastCheck = time.time()
lastVal = commsPin.value

try:
    while True:
        time.sleep(0.05)
        currentVal = commsPin.value

        if currentVal != lastVal:
            stateChanges += 1
            lastVal = currentVal

        if time.time() - lastCheck >= 0.6:
            if stateChanges > 1:
                if displayState != "BREACH":
                    displayState = "BREACH"
                    print("State updated: BREACH")
            elif currentVal == 1:
                if displayState != "ARMED":
                    displayState = "ARMED"
                    print("State updated: ARMED")
            else:
                if displayState != "SAFE":
                    displayState = "SAFE"
                    print("State updated: SAFE")

            stateChanges = 0
            lastCheck = time.time()

except KeyboardInterrupt:
    print("\nShutting down cleanly...")
    allDigitsOff()
    os._exit(0)
