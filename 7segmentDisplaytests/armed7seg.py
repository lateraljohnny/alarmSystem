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
# 4 Digit Display Mapping
#
# Q0 = DP
# Q1 = G
# Q2 = F
# Q3 = E
# Q4 = D
# Q5 = C
# Q6 = B
# Q7 = A
#
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
# Custom ARMED Characters
# =========================

# Digit 1: A
# Segments: A B C E F G
A_letter = seg(1,1,1,0,1,1,1)


# Digit 2: only E + G
# Segments: lower-left + middle
r_letter = seg(0,0,0,0,1,0,1)


# Digit 3: only E + G + C
# Segments: lower-left + middle + lower-right
n_letter = seg(0,0,1,0,1,0,1)


# Digit 4: only G + C
# Segments: middle + lower-right
corner_letter = seg(0,0,1,0,0,0,1)



# =========================
# Single Digit Displays
# =========================
#
# Third shift register:
#
# Q0 = A
# Q1 = B
# Q2 = C
# Q3 = D
# Q4 = E
# Q5 = F
# Q6 = G
# Q7 = DP
#
# =========================

def single_seg(A,B,C,D,E,F,G,DP=0):

    value = 0

    if A:  value |= 0b00000001
    if B:  value |= 0b00000010
    if C:  value |= 0b00000100
    if D:  value |= 0b00001000
    if E:  value |= 0b00010000
    if F:  value |= 0b00100000
    if G:  value |= 0b01000000
    if DP: value |= 0b10000000

    return value



# Single display #1 = E
# A F G E D
E_letter = seg(1,0,0,1,1,1,1)


# Single display #2 = d
# B C D E G
d_letter = single_seg(0,1,1,1,1,0,1)



# =========================
# Shift Register Functions
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

    # Middle shift register
    shiftOut(chip2)

    # First shift register
    shiftOut(chip1)

    latchPin.on()



# =========================
# 4 Digit Characters
# =========================

letters = [
    A_letter,
    r_letter,
    n_letter,
    corner_letter
]


currentDigit = 0



# =========================
# Display Refresh
# =========================

def allDigitsOff():

    for digit in digits:
        digit.on()



def refresh_display():

    global currentDigit

    while True:

        allDigitsOff()


        send24(
            letters[currentDigit],
            E_letter,
            d_letter
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


print("Displaying ARMED")


while True:
    sleep(1)
