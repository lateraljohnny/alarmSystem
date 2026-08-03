from gpiozero import OutputDevice
from time import sleep
import threading


# =========================
# Raspberry Pi Pins
# =========================

DATA_PIN = 23
CLOCK_PIN = 18
LATCH_PIN = 5

dataPin = OutputDevice(DATA_PIN)
clockPin = OutputDevice(CLOCK_PIN)
latchPin = OutputDevice(LATCH_PIN)


# =========================
# 4 Digit Display Pins
# =========================

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
# Segment Mapping
#
# Q0 = DP
# Q1 = G
# Q2 = F
# Q3 = E
# Q4 = D
# Q5 = C
# Q6 = B
# Q7 = A
# =========================

def seg(A,B,C,D,E,F,G,DP=0):

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



# =========================
# SAFE
# =========================

S_letter = seg(1,0,1,1,0,1,1)

A_letter = seg(1,1,1,0,1,1,1)

F_letter = seg(1,0,0,0,1,1,1)

E_letter = seg(1,0,0,1,1,1,1)


safe = [
    S_letter,
    A_letter,
    F_letter,
    E_letter
]


# =========================
# Shift Register
# =========================

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

    # Last shift register first
    shiftOut(chip3)

    # Second shift register
    shiftOut(chip2)

    # First shift register
    shiftOut(chip1)

    latchPin.on()



# =========================
# Display Refresh
# =========================

currentDigit = 0


def allDigitsOff():

    for digit in digits:
        digit.on()



def refresh_display():

    global currentDigit

    while True:

        allDigitsOff()

        send24(
            safe[currentDigit],  # SAFE
            0,                   # single digit OFF
            0                    # single digit OFF
        )

        digits[currentDigit].off()

        currentDigit += 1

        if currentDigit >= 4:
            currentDigit = 0

        sleep(0.003)



# =========================
# Start
# =========================

allDigitsOff()

thread = threading.Thread(target=refresh_display)
thread.daemon = True
thread.start()


print("Displaying SAFE")


while True:
    sleep(1)
