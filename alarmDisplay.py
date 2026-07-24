import socket
import math
import time
from collections import deque
from rgbmatrix import RGBMatrix, RGBMatrixOptions

# ==========================================================
# RGB MATRIX CONFIGURATION
# ==========================================================
matrixOptions = RGBMatrixOptions()
matrixOptions.rows = 16
matrixOptions.cols = 32
matrixOptions.chain_length = 1
matrixOptions.parallel = 1
matrixOptions.hardware_mapping = "adafruit-hat"
matrixOptions.gpio_slowdown = 4
matrixOptions.disable_hardware_pulsing = True

matrixDisplay = RGBMatrix(options=matrixOptions)
frameCanvas = matrixDisplay.CreateFrameCanvas()

screenWidth = matrixOptions.cols
screenHeight = matrixOptions.rows

# ==========================================================
# NETWORK SERVER CONFIGURATION (NON-BLOCKING)
# ==========================================================
displayServerPort = 5005
networkServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
networkServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
networkServer.bind(("0.0.0.0", displayServerPort))
networkServer.listen(1)
networkServer.setblocking(False)

print(f"Display server listening on port {displayServerPort}...")

sensorHubConnection = None
networkDataBuffer = ""

# ==========================================================
# GLOBAL STATE VARIABLES
# ==========================================================
lightAdcValue = 512
temperatureFahrenheit = 72.0
potAdcValue = 512
isSystemArmedFlag = 0
thermistorDisabledFlag = 0
photocellDisabledFlag = 0

maxLightSamples = 200
lightSampleHistory = deque(maxlen=maxLightSamples)
previousLightPercentage = 0.5

displayHeight = 8.0
displayColor = (0, 255, 0)

heightAlphaFilter = 0.20
colorAlphaFilter = 0.15
wavePhaseShift = 0.0

# ==========================================================
# UTILITY FUNCTIONS & COLOR ENGINE
# ==========================================================
def clampValue(value, minLimit, maxLimit):
    return max(minLimit, min(value, maxLimit))

def normalizeValue(value, minLimit, maxLimit):
    if maxLimit - minLimit < 20:
        return 0.5
    return clampValue((value - minLimit) / (maxLimit - minLimit), 0.0, 1.0)

def calculateTemperatureColor(tempF, isAlarmTriggered):
    if isAlarmTriggered:
        return (255, 0, 0)

    tempF = clampValue(tempF, 55, 90)
    tempRatio = (tempF - 55) / 35.0

    if tempRatio < 0.33:
        fade = tempRatio / 0.33
        return (0, int(255 * fade), 255)
    elif tempRatio < 0.66:
        fade = (tempRatio - 0.33) / 0.33
        return (0, 255, int(255 * (1 - fade)))
    else:
        fade = (tempRatio - 0.66) / 0.34
        return (255, int(255 * (1 - (fade * 0.53))), 0)

# ==========================================================
# NETWORK PACKET PROCESSING
# ==========================================================
def processNetworkInputs():
    global sensorHubConnection, networkDataBuffer
    global lightAdcValue, temperatureFahrenheit, potAdcValue
    global isSystemArmedFlag, thermistorDisabledFlag, photocellDisabledFlag

    if sensorHubConnection is None:
        try:
            sensorHubConnection, clientAddress = networkServer.accept()
            sensorHubConnection.setblocking(False)
            print(f"Connected to Sensor Hub: {clientAddress}")
        except BlockingIOError:
            return

    try:
        incomingData = sensorHubConnection.recv(1024)
        if not incomingData:
            sensorHubConnection.close()
            sensorHubConnection = None
            return
        networkDataBuffer += incomingData.decode("utf-8", errors="ignore")
    except BlockingIOError:
        return
    except (ConnectionResetError, OSError):
        sensorHubConnection = None
        return

    while "\n" in networkDataBuffer:
        dataLine, networkDataBuffer = networkDataBuffer.split("\n", 1)
        try:
            dataParts = dataLine.strip().split(",")
            # Packet layout updated to match new sensorhub payload size (6 elements)
            if len(dataParts) == 6:
                lightAdcValue = int(dataParts[0])
                temperatureFahrenheit = float(dataParts[1])
                potAdcValue = int(dataParts[2])
                isSystemArmedFlag = int(dataParts[3])
                thermistorDisabledFlag = int(dataParts[4])
                photocellDisabledFlag = int(dataParts[5])
        except ValueError:
            continue

# ==========================================================
# GRAPHICS DRAWING ROUTINES
# ==========================================================
def drawCenteredWarningSign():
    """Draws a red warning triangle centered horizontally at x=15."""
    trianglePeakX = 15
    triangleStartY = 1
    triangleEndY = 6

    for iteration in range(triangleEndY - triangleStartY + 1):
        currentY = triangleStartY + iteration
        startX = trianglePeakX - iteration
        endX = trianglePeakX + iteration
        for xPos in range(startX, endX + 1):
            frameCanvas.SetPixel(xPos, currentY, 255, 0, 0)

    frameCanvas.SetPixel(trianglePeakX, triangleStartY + 1, 0, 0, 0)
    frameCanvas.SetPixel(trianglePeakX, triangleStartY + 2, 0, 0, 0)
    frameCanvas.SetPixel(trianglePeakX, triangleStartY + 4, 0, 0, 0)

def drawDualThresholdIndicators(thresholdY):
    """Draws 2 purple indicator dots on left and right borders."""
    purpleColor = (180, 0, 255)
    frameCanvas.SetPixel(0, thresholdY, *purpleColor)
    frameCanvas.SetPixel(1, thresholdY, *purpleColor)
    frameCanvas.SetPixel(30, thresholdY, *purpleColor)
    frameCanvas.SetPixel(31, thresholdY, *purpleColor)

# ==========================================================
# RENDERING ENGINE
# ==========================================================
def renderVisualFrame():
    global displayHeight, displayColor, wavePhaseShift, previousLightPercentage

    isLightThresholdTripped = (photocellDisabledFlag == 0) and (lightAdcValue >= potAdcValue)
    isTempThresholdTripped = (thermistorDisabledFlag == 0) and (temperatureFahrenheit > 81)
    isAlarmTriggered = (isSystemArmedFlag == 1) and (isLightThresholdTripped or isTempThresholdTripped)

    lightSampleHistory.append(lightAdcValue)
    lightMinimum = min(lightSampleHistory)
    lightMaximum = max(lightSampleHistory)

    lightPercentage = normalizeValue(lightAdcValue, lightMinimum, lightMaximum)
    lightDelta = abs(lightPercentage - previousLightPercentage)
    previousLightPercentage = lightPercentage

    matrixDisplay.brightness = int(15 + (lightPercentage * 70))

    if lightPercentage <= 0.05:
        waveAmplitude = 3.0
    elif lightPercentage <= 0.25:
        waveAmplitude = 4.0 * (lightDelta * 12) if lightDelta > 0.01 else 0.0
    else:
        waveAmplitude = 5.0 * (lightDelta * 12) if lightDelta > 0.01 else 0.0

    wavePhaseShift += 0.15 + (lightDelta * 2.5)

    targetHeight = 1.0 + (lightPercentage * (screenHeight - 1))
    displayHeight += (targetHeight - displayHeight) * heightAlphaFilter

    targetColor = calculateTemperatureColor(temperatureFahrenheit, isAlarmTriggered)
    displayColor = tuple(
        current + (target - current) * colorAlphaFilter
        for current, target in zip(displayColor, targetColor)
    )

    redVal, greenVal, blueVal = [int(color) for color in displayColor]
    baseHeight = displayHeight

    # 1. Render Ambience Wave
    for xPos in range(screenWidth):
        if waveAmplitude > 0:
            waveOffset = math.sin(xPos * 0.4 + wavePhaseShift) * waveAmplitude
            columnHeight = clampValue(int(baseHeight + waveOffset), 1, screenHeight)
        else:
            columnHeight = clampValue(int(baseHeight), 1, screenHeight)

        for yPos in range(screenHeight - columnHeight, screenHeight):
            colorFade = (yPos - (screenHeight - columnHeight)) / max(columnHeight, 1)
            frameCanvas.SetPixel(xPos, yPos, int(redVal * colorFade), int(greenVal * colorFade), int(blueVal * colorFade))

    # 2. Threshold Level Indicators
    thresholdYPosition = clampValue(int((1.0 - (potAdcValue / 1023.0)) * 15), 0, 15)
    drawDualThresholdIndicators(thresholdYPosition)

    # 3. Flashing Warning Triangle (4 Hz Flash during Alarm)
    if isAlarmTriggered:
        if int(time.time() * 4) % 2 == 0:
            drawCenteredWarningSign()

# ==========================================================
# MAIN EXECUTION LOOP (~30 HZ)
# ==========================================================
targetFrameTime = 1.0 / 30.0

try:
    while True:
        loopStartTime = time.time()

        frameCanvas.Clear()
        processNetworkInputs()
        renderVisualFrame()

        frameCanvas = matrixDisplay.SwapOnVSync(frameCanvas)

        elapsedTime = time.time() - loopStartTime
        if elapsedTime < targetFrameTime:
            time.sleep(targetFrameTime - elapsedTime)

except KeyboardInterrupt:
    print("\nShutting down display server...")

finally:
    frameCanvas.Clear()
    matrixDisplay.SwapOnVSync(frameCanvas)
    networkServer.close()
    print("Clean exit")
