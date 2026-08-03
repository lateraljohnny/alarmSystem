from gpiozero import OutputDevice
from time import sleep


# =========================
# Raspberry Pi pins
# =========================

DATA_PIN = 23
CLOCK_PIN = 18
LATCH_PIN = 5


dataPin = OutputDevice(DATA_PIN)
clockPin = OutputDevice(CLOCK_PIN)
latchPin = OutputDevice(LATCH_PIN)


# =========================
# Shift register output
# =========================

def shiftOut(value):

    # Send 8 bits, LSB first
    for i in range(8):

        if value & (1 << i):
            dataPin.on()
        else:
            dataPin.off()

        clockPin.on()
        clockPin.off()



def send24(chip1, chip2, chip3):

    latchPin.off()

    # IMPORTANT:
    # Last chip in chain receives data first
    shiftOut(chip3)
    shiftOut(chip2)
    shiftOut(chip1)

    latchPin.on()



# =========================
# Segment mappings
# =========================

# First two displays:
# Q0=DP
# Q1=G
# Q2=F
# Q3=E
# Q4=D
# Q5=C
# Q6=B
# Q7=A

A_FIRST_STYLE = 0b10000000


# Third display:
# Q0=A
# Q1=B
# Q2=C
# Q3=D
# Q4=E
# Q5=F
# Q6=G
# Q7=DP

A_THIRD_STYLE = 0b00000001



while True:

    print("All three displays showing A")

    # Chip 1 → 4 digit display
    # Chip 2 → first single digit
    # Chip 3 → second single digit

    send24(
        A_FIRST_STYLE,
        A_FIRST_STYLE,
        A_THIRD_STYLE
    )

    sleep(3)


    print("Turning everything off")

    send24(
        0,
        0,
        0
    )

    sleep(3)
