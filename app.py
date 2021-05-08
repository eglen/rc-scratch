from flask import Flask, render_template, request, Response
from flask.logging import default_handler
from flask_socketio import SocketIO, emit
import threading
from time import sleep
from logging.config import dictConfig
import pigpio

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

# The servos are connected on these GPIO pins (BCM numbering)
HORIZ_SERVO_PORT = 27
VERT_SERVO_PORT= 24

#LED GPIO
LIVENESS_PORT = 17
ACTIVITY_PORT = 22

# Servo Info

HORIZ_SERVO_MIN = 1250 #Actual servo min 600
HORIZ_SERVO_MAX = 2040 #Actual servo max 2500
HORIZ_SERVO_CENTER = HORIZ_SERVO_MIN + (HORIZ_SERVO_MAX - HORIZ_SERVO_MIN)/2

VERT_SERVO_MIN = 800
VERT_SERVO_MAX = 1700
VERT_SERVO_CENTER = VERT_SERVO_MIN + (VERT_SERVO_MAX - VERT_SERVO_MIN)/2

#Command range
MIN_COMMAND = -50
MAX_COMMAND = 50

HORIZ_CONVERSION = (HORIZ_SERVO_MAX - HORIZ_SERVO_CENTER)/MAX_COMMAND
VERT_CONVERSION = (VERT_SERVO_MAX - VERT_SERVO_CENTER)/MAX_COMMAND

blink_pattern = ((1, 0.1), (0, 0.1), (1,0.1), (0, 2))

# Create Flask App
app = Flask(__name__, static_url_path='', static_folder='lib')
app.config['SECRET_KEY'] = 'prasutagus!'
socketio = SocketIO(app)

# GPIO Info
gpio = pigpio.pi()

def setupGPIO():
    gpio.set_servo_pulsewidth(HORIZ_SERVO_PORT, 0)
    gpio.set_servo_pulsewidth(VERT_SERVO_PORT, 0)

def setServoDuty(servo, duty):
    gpio.set_servo_pulsewidth(servo, duty)

def clamp(num, minimum, maximum):
    return max(min(num, maximum), minimum)

# Serve the HTML file when the root path is requested
@app.route("/")
def serveRoot():
    return render_template('main.html')

@socketio.on('rudder')
def handle_rudder(rudderPos):
    gpio.write(ACTIVITY_PORT, 1)
    print('rudder' + str(rudderPos))
    horizontal = HORIZ_CONVERSION * int(rudderPos)
    setServoDuty(HORIZ_SERVO_PORT, clamp(HORIZ_SERVO_CENTER - horizontal, HORIZ_SERVO_MIN, HORIZ_SERVO_MAX))
    gpio.write(ACTIVITY_PORT, 0)

@socketio.on('throttle')
def test_message(throttlePos):
    gpio.write(ACTIVITY_PORT, 1)
    print('throttle' + str(throttlePos))
    vertical = VERT_CONVERSION * int(throttlePos)
    setServoDuty(VERT_SERVO_PORT, clamp(VERT_SERVO_CENTER - vertical, VERT_SERVO_MIN, VERT_SERVO_MAX))
    gpio.write(ACTIVITY_PORT, 0)

@socketio.on('connect')
def connect():
    print('Client connected')
    global blink_pattern
    blink_pattern=((1, 0.1), (0, 0.1))

@socketio.on('disconnect')
def disconnect():
    print('Client disconnected')
    global blink_pattern
    blink_pattern=((1, 0.5), (0, 0.5))

def app_liveness_led():
    #App LED blink pattern
    while True:
        for pattern in blink_pattern:
            gpio.write(LIVENESS_PORT, pattern[0])
            sleep(pattern[1])

# Run the app on the local development server
# Accept any IP address
if __name__ == "__main__":
    print("Starting")
    liveness = threading.Thread(target=app_liveness_led, args=())
    liveness.daemon = True
    liveness.start()
    print("Starting2")
    app.logger.removeHandler(default_handler)
    socketio.run(app, host="0.0.0.0")

