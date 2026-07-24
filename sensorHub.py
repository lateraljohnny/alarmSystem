import math
import socket
import statistics
import time
import board
import busio
import digitalio
import RPi.GPIO as GPIO
import adafruit_mcp3xxx.mcp3008 as MCP
from gpiozero import OutputDevice, DigitalInputDevice
from adafruit_mcp3xxx.analog_in import AnalogIn

# ==========================================================
# HARDWARE SETUP
# ==========================================================
spiBus = busio.SPI(clock=board.SCK, MOSI=board.MOSI, MISO=board.MISO)
chipSelectPin = digitalio.DigitalInOut(board.D8)
mcpAdc = MCP.MCP3008(spiBus, chipSelectPin)

disarmSignal = OutputDevice(16)
breachSignal = OutputDevice(21)
localBuzzer = OutputDevice(18)

lockoutSwitchPin = DigitalInputDevice(13, pull_up=True)           # Lockout Switch (dpin1)
thermistorDisableSwitchPin = DigitalInputDevice(19, pull_up=True) # Thermistor Disable (dpin2)
photocellDisableSwitchPin = DigitalInputDevice(26, pull_up=True)  # Photocell Disable (dpin3)
# Note: Physical Arm Button (Pin 12) is omitted from software setup since it drives the hardware SR Latch directly.

potentiometerChannel = AnalogIn(mcpAdc, MCP.P0)
thermistorChannel = AnalogIn(mcpAdc, MCP.P1)
photocellChannel = AnalogIn(mcpAdc, MCP.P2)

latchArmedPin = digitalio.DigitalInOut(board.D25)
latchArmedPin.direction = digitalio.Direction.INPUT

# ==========================================================
# CALIBRATION CONSTANTS
# ==========================================================
circuitVcc = 3.3
seriesResistance = 10000.0
thermistorNominal = 10000.0
temperatureNominal = 25.0
betaValue = 3950.0
temperatureOffsetF = 0.0

# ==========================================================
# NETWORK CONFIGURATION
# ==========================================================
displayServerIp = "172.20.1.72"
displayServerPort = 5005

updateRate = 30
frameTime = 1.0 / updateRate

# ==========================================================
# FILTERING VARIABLES
# ==========================================================
lightAlphaFilter = 0.25
tempAlphaFilter = 0.25
potAlphaFilter = 0.25

lightFiltered = None
tempFiltered = None
potFiltered = None

# ==========================================================
# KEYPAD CLASS
# ==========================================================
class KeypadReader:
        def __init__(self, rowPinsList, colPinsList):
                self.rowPinsList = rowPinsList
                self.colPinsList = colPinsList
                self.keyMap = [
                        ['1', '2', '3', 'A'],
                        ['4', '5', '6', 'B'],
                        ['7', '8', '9', 'C'],
                        ['*', '0', '#', 'D']
                ]
                self.lastKeyPressed = None
                GPIO.setmode(GPIO.BCM)

                for col in self.colPinsList:
                        GPIO.setup(col, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                for row in self.rowPinsList:
                        GPIO.setup(row, GPIO.OUT)
                        GPIO.output(row, GPIO.LOW)

        def scanKeypad(self):
                """Scans keypad non-blockingly."""
                pressedKey = None
                for rIdx, row in enumerate(self.rowPinsList):
                        GPIO.output(row, GPIO.HIGH)
                        for cIdx, col in enumerate(self.colPinsList):
                                if GPIO.input(col) == GPIO.HIGH:
                                        pressedKey = self.keyMap[rIdx][cIdx]
                        GPIO.output(row, GPIO.LOW)

                if pressedKey != self.lastKeyPressed:
                        self.lastKeyPressed = pressedKey
                        if pressedKey is not None:
                                return pressedKey
                return None

# ==========================================================
# UTILITY FUNCTIONS
# ==========================================================
def convertAdcToFahrenheit(adcValue):
        adcValue = max(1, min(1022, adcValue))
        voltage = (adcValue * circuitVcc / 1023.0)
        resistance = seriesResistance * voltage / (circuitVcc - voltage)

        steinhart = (resistance / thermistorNominal)
        steinhart = math.log(steinhart)
        steinhart /= betaValue
        steinhart += (1.0 / (temperatureNominal + 273.15))
        steinhart = 1.0 / steinhart

        tempC = steinhart - 273.15
        rawTempF = tempC * 9.0 / 5.0 + 32.0
        calibratedTempF = rawTempF - temperatureOffsetF

        return calibratedTempF, voltage, resistance

def calculateMedianAdc(channel, sampleCount=9):
        adcValues = []
        for _ in range(sampleCount):
                adcValues.append(channel.value >> 6)
                time.sleep(0.002)
        return int(statistics.median(adcValues))

def connectToDisplayServer():
        while True:
                try:
                        displaySocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        displaySocket.connect((displayServerIp, displayServerPort))
                        print(f"\n[NETWORK] Connected to display server {displayServerIp}:{displayServerPort}")
                        return displaySocket
                except OSError:
                        print("[NETWORK] Display unavailable... retrying in 2 seconds.")
                        time.sleep(2)

def pulseDisarmSignal():
        """Forces the hardware SR Latch back to DISARMED state."""
        disarmSignal.on()
        time.sleep(0.2)
        disarmSignal.off()

# ==========================================================
# STARTUP & INITIALIZATION
# ==========================================================
time.sleep(0.5)

# Ensure hardware starts completely disarmed
if latchArmedPin.value:
        print("[SYSTEM] System initially ARMED on startup. Forcing initial DISARM...")
        pulseDisarmSignal()

displayClientSocket = connectToDisplayServer()

keypadRowPins = [20, 24, 23, 22]
keypadColPins = [27, 17, 6, 5]
keypad = KeypadReader(keypadRowPins, keypadColPins)

pinDataBuffer = ""
correctSecurityPin = "1357"

# --- State Control Flags ---
pendingArmAuthorization = False
pendingDipSwitchChange = False
lastHardwareArmedState = False

# Active sensors match physical DIP positions on boot
activeThermistorDisabled = 1 if thermistorDisableSwitchPin.is_active else 0
activePhotocellDisabled = 1 if photocellDisableSwitchPin.is_active else 0

# ==========================================================
# MAIN EXECUTION LOOP
# ==========================================================
try:
        while True:
                frameStartTime = time.time()

                # 1. --- Lockout Switch (dpin1) Check ---
                if lockoutSwitchPin.is_active:
                        if latchArmedPin.value:
                                pulseDisarmSignal()
                                pendingArmAuthorization = False
                                print("\n[STATE CHANGE DENIED] Arming attempt blocked! Lockout switch (dpin1) is ACTIVE.")
                else:
                # 2. --- Detect Hardware Arming Request ---
                        currentHardwareArmed = latchArmedPin.value
                        if currentHardwareArmed and not lastHardwareArmedState:
                                pendingArmAuthorization = True
                                print("\n[STATE CHANGE REQUESTED] System arming requested via hardware button.")
                                print("[SYSTEM] PIN verification required! Enter PIN and press '#' to authorize arming.")
                lastHardwareArmedState = currentHardwareArmed

                # 3. --- Detect Sensor Config (DIP Switch) Requests ---
                physThermSwitch = 1 if thermistorDisableSwitchPin.is_active else 0
                physPhotoSwitch = 1 if photocellDisableSwitchPin.is_active else 0

                if (physThermSwitch != activeThermistorDisabled) or (physPhotoSwitch != activePhotocellDisabled):
                        if not pendingDipSwitchChange:
                                pendingDipSwitchChange = True
                                print("\n[STATE CHANGE REQUESTED] Sensor configuration change detected on DIP switches.")
                                print("[SYSTEM] PIN verification required! Enter PIN and press '#' to authorize sensor change.")

                # 4. --- Keypad Processing & PIN Verification ---
                keyPressed = keypad.scanKeypad()
                if keyPressed:
                        print(f"\n[KEYPAD] Pressed: {keyPressed}")
                        if keyPressed == '#':
                                print("[SYSTEM] Verifying PIN...")

                                # --- STEP 1: VERIFY PIN FIRST ---
                                if pinDataBuffer == correctSecurityPin:
                                        print("[PIN VERIFIED] Access Granted!")
                                        pinActionTaken = False

                                        # Action A: Authorize pending arm request
                                        if pendingArmAuthorization:
                                                print("[STATE CHANGE AUTHORIZED] Arming state verified by owner.")
                                                print("[STATE CHANGE EXECUTED] System is officially ARMED.")
                                                pendingArmAuthorization = False
                                                pinActionTaken = True

                                        # Action B: Authorize pending DIP switch sensor changes
                                        if pendingDipSwitchChange:
                                                activeThermistorDisabled = physThermSwitch
                                                activePhotocellDisabled = physPhotoSwitch
                                                pendingDipSwitchChange = False
                                                print("[STATE CHANGE AUTHORIZED] DIP switch sensor change approved.")
                                                print(f"[STATE CHANGE EXECUTED] Active sensor config updated (Thermistor Disabled: {activeThermistorDisabled}, Photocell Disabled: {activePhotocellDisabled}).")
                                                pinActionTaken = True

                                        # Action C: If system is armed AND no other auths were pending -> Execute Disarm
                                        if not pinActionTaken and latchArmedPin.value:
                                                print("[STATE CHANGE REQUESTED] Disarm requested via keypad.")
                                                print("[STATE CHANGE AUTHORIZED] Disarm command approved.")
                                                pulseDisarmSignal()
                                                print("[STATE CHANGE EXECUTED] System successfully DISARMED.")

                                else:
                                        # --- STEP 2: REJECT ALL PENDING CHANGES IF PIN INVALID ---
                                        print("[PIN VERIFICATION FAILED] Access Denied: Invalid PIN!")

                                        if pendingArmAuthorization:
                                                print("[STATE CHANGE DENIED] Unauthorized arm attempt! Forcing disarm...")
                                                pulseDisarmSignal()
                                                pendingArmAuthorization = False
                                                print("[STATE CHANGE EXECUTED] System forced back to DISARMED.")

                                        if pendingDipSwitchChange:
                                                print("[STATE CHANGE DENIED] DIP switch change rejected! Active sensor configuration remains unchanged.")
                                                pendingDipSwitchChange = False

                                        if not pendingArmAuthorization and not pendingDipSwitchChange and latchArmedPin.value:
                                                print("[STATE CHANGE DENIED] Disarm attempt failed due to invalid PIN! System remains ARMED.")

                                pinDataBuffer = ""

                        elif keyPressed == '*':
                                pinDataBuffer = ""
                                print("[KEYPAD] PIN Buffer Cleared.")
                        else:
                                if len(pinDataBuffer) < 8:
                                        pinDataBuffer += keyPressed
                                print(f"[KEYPAD] Buffer: {'*' * len(pinDataBuffer)}")

                # 5. --- Sensor Sampling ---
                lightRawAdc = calculateMedianAdc(photocellChannel)
                tempRawAdc = calculateMedianAdc(thermistorChannel)
                potRawAdc = calculateMedianAdc(potentiometerChannel)

                # Exponential Smoothing
                if lightFiltered is None: lightFiltered = lightRawAdc
                else: lightFiltered = ((1.0 - lightAlphaFilter) * lightFiltered) + (lightAlphaFilter * lightRawAdc)

                if tempFiltered is None: tempFiltered = tempRawAdc
                else: tempFiltered = ((1.0 - tempAlphaFilter) * tempFiltered) + (tempAlphaFilter * tempRawAdc)

                if potFiltered is None: potFiltered = potRawAdc
                else: potFiltered = ((1.0 - potAlphaFilter) * potFiltered) + (potAlphaFilter * potRawAdc)

                lightAdcValue = int(lightFiltered)
                tempAdcValue = int(tempFiltered)
                potAdcValue = int(potFiltered)

                temperatureF, voltageCalc, resistanceCalc = convertAdcToFahrenheit(tempAdcValue)
                isSystemArmedFlag = 1 if latchArmedPin.value else 0

                # --- Local Alarm Logic ---
                isLightThresholdTripped = (activePhotocellDisabled == 0) and (lightAdcValue >= potAdcValue)
                isTempThresholdTripped = (activeThermistorDisabled == 0) and (temperatureF > 81.0)
                isAlarmTriggered = (isSystemArmedFlag == 1) and (isLightThresholdTripped or isTempThresholdTripped)

                if isAlarmTriggered:
                        if int(time.time() * 4) % 2 == 0:
                                localBuzzer.on()
                                breachSignal.on()
                        else:
                                localBuzzer.off()
                                breachSignal.off()
                else:
                        localBuzzer.off()
                        if isSystemArmedFlag == 1:
                                breachSignal.on()
                        else:
                                breachSignal.off()

                # --- Networking ---
                packetData = f"{lightAdcValue},{temperatureF:.1f},{potAdcValue},{isSystemArmedFlag},{activeThermistorDisabled},{activePhotocellDisabled}\n"

                print(
                        f"Light:{lightAdcValue:4d}  "
                        f"Temp:{temperatureF:5.1f}F  "
                        f"POT:{potAdcValue:4d}  "
                        f"ARMED:{isSystemArmedFlag}  "
                        f"T_DIS:{activeThermistorDisabled}  "
                        f"P_DIS:{activePhotocellDisabled}  "
                        f"{voltageCalc:0.2f}V  "
                        f"{resistanceCalc:7.0f}Ω",
                        end="\r",
                        flush=True,
                )

                try:
                        displayClientSocket.sendall(packetData.encode("utf-8"))
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                        print("\n[NETWORK] Connection lost. Reconnecting...")
                        try:
                                displayClientSocket.close()
                        except Exception:
                                pass
                        displayClientSocket = connectToDisplayServer()

                # --- Frame Sync ---
                elapsedTime = time.time() - frameStartTime
                if elapsedTime < frameTime:
                        time.sleep(frameTime - elapsedTime)

except KeyboardInterrupt:
        print("\n[SYSTEM] Stopping Sensor Hub...")
finally:
        localBuzzer.off()
        disarmSignal.off()
