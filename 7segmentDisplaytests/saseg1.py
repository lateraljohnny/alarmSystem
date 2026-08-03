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
# Main 4 digit display
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
# ARMED
# =========================

A_letter = seg(1,1,1,0,1,1,1)

second_letter = seg(
    0,0,0,0,1,0,1
)

third_letter = seg(
    0,0,1,0,1,0,1
)

fourth_letter = seg(
    0,0,1,0,1,0,1
)


armed_main = [
    A_letter,
    second_letter,
    third_letter,
    fourth_letter
]



# =========================
# BREACH
# =========================

# Capital B

B_letter = seg(
    1,1,1,1,1,1,1
)


# lowercase r

r_letter = seg(
    0,0,0,0,1,0,1
)


# E

E_breach = seg(
    1,0,0,1,1,1,1
)


# A

A_breach = seg(
    1,1,1,0,1,1,1
)


breach_main = [
    B_letter,
    r_letter,
    E_breach,
    A_breach
]

# =========================
# Second shift register
#
# Q0 = DP
# Q1 = G
# Q2 = F
# Q3 = E
# Q4 = D
# Q5 = C
# Q6 = A
# Q7 = B
# =========================

def second_seg(A,B,C,D,E,F,G,DP=0):

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



# E for ARMED

E_display = second_seg(
    1,0,0,1,1,1,1
)


# C for BREACH

C_display = second_seg(
    1,0,0,1,1,1,0
)



# =========================
# Third shift register
#
# Q0 = A
# Q1 = B
# Q2 = C
# Q3 = D
# Q4 = E
# Q5 = F
# Q6 = G
# Q7 = DP
# =========================

def third_seg(A,B,C,D,E,F,G,DP=0):

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



# d for ARMED

d_display = third_seg(
    0,1,1,1,1,0,1
)


# H for BREACH

H_display = third_seg(
    0,1,1,0,1,1,1
)



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

    # Second shift register
    shiftOut(chip2)

    # First shift register
    shiftOut(chip1)

    latchPin.on()



# =========================
# Display State
# =========================

display_state = "SAFE"



# =========================
# Multiplexing
# =========================

currentDigit = 0



def allDigitsOff():

    for digit in digits:
        digit.on()



def refresh_display():

    global currentDigit

    while True:

        allDigitsOff()


        if display_state == "SAFE":

            send24(
                safe[currentDigit],
                0,
                0
            )


        elif display_state == "ARMED":

            send24(
                armed_main[currentDigit],
                E_display,
                d_display
            )


        elif display_state == "BREACH":

            send24(
                breach_main[currentDigit],
                C_display,
                H_display
            )


        elif display_state == "OFF":

            send24(
                0,
                0,
                0
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



print("Current state: SAFE")
print("")
print("Commands:")
print("safe")
print("armed")
print("breach")
print("off")



while True:

    command = input()


    if command == "safe":

        display_state = "SAFE"
        print("Displaying SAFE")


    elif command == "armed":

        display_state = "ARMED"
        print("Displaying ARMED")


    elif command == "breach":

        display_state = "BREACH"
        print("Displaying BREACH")


    elif command == "off":

        display_state = "OFF"
        print("Display OFF")
