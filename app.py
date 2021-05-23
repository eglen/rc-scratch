import io
import os
from flask import Flask, render_template, request, Response
from flask_socketio import SocketIO, emit
from subprocess import Popen, PIPE
from struct import Struct
from threading import Thread
from time import sleep
import picamera
import pigpio

from wsgiref.simple_server import make_server
from ws4py.websocket import WebSocket
from ws4py.server.wsgirefserver import (
    WSGIServer,
    WebSocketWSGIHandler,
    WebSocketWSGIRequestHandler,
)
from ws4py.server.wsgiutils import WebSocketWSGIApplication

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

#Video config
WIDTH = 544
HEIGHT = 368
FRAMERATE = 24
WS_PORT = 5002
JSMPEG_MAGIC = b'jsmp'
JSMPEG_HEADER = Struct('>4sHH')
VFLIP = False
HFLIP = False

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
    return render_template('main.html', width=WIDTH, height=HEIGHT, ws_port=WS_PORT)

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


class StreamingWebSocket(WebSocket):
    def opened(self):
        self.send(JSMPEG_HEADER.pack(JSMPEG_MAGIC, WIDTH, HEIGHT), binary=True)

class BroadcastOutput(object):
    def __init__(self, camera):
        print('Spawning background conversion process')
        self.converter = Popen([
            'ffmpeg',
            '-f', 'rawvideo',
            '-pix_fmt', 'yuv420p',
            '-s', '%dx%d' % camera.resolution,
            '-r', str(float(camera.framerate)),
            '-i', '-',
            '-f', 'mpeg1video',
            '-b', '400k',
            '-r', str(float(camera.framerate)),
            '-'],
            stdin=PIPE, stdout=PIPE, stderr=io.open(os.devnull, 'wb'),
            shell=False, close_fds=True)

    def write(self, b):
        self.converter.stdin.write(b)

    def flush(self):
        print('Waiting for background conversion process to exit')
        self.converter.stdin.close()
        self.converter.wait()


class BroadcastThread(Thread):
    def __init__(self, converter, websocket_server):
        super(BroadcastThread, self).__init__()
        self.converter = converter
        self.websocket_server = websocket_server

    def run(self):
        try:
            while True:
                buf = self.converter.stdout.read1(32768)
                if buf:
                    self.websocket_server.manager.broadcast(buf, binary=True)
                elif self.converter.poll() is not None:
                    break
        finally:
            self.converter.stdout.close()

# Run the app on the local development server
# Accept any IP address
if __name__ == "__main__":
    print("Starting")
    print('Initializing camera')
    with picamera.PiCamera() as camera:
        camera.resolution = (WIDTH, HEIGHT)
        camera.framerate = FRAMERATE
        camera.vflip = VFLIP # flips image rightside up, as needed
        camera.hflip = HFLIP # flips image left-right, as needed
        sleep(1) # camera warm-up time
        print('Initializing websockets server for video stream on port %d' % WS_PORT)
        WebSocketWSGIHandler.http_version = '1.1'
        websocket_server = make_server(
            '', WS_PORT,
            server_class=WSGIServer,
            handler_class=WebSocketWSGIRequestHandler,
            app=WebSocketWSGIApplication(handler_cls=StreamingWebSocket))
        websocket_server.initialize_websockets_manager()
        websocket_thread = Thread(target=websocket_server.serve_forever)
        print('Initializing broadcast thread')
        output = BroadcastOutput(camera)
        broadcast_thread = BroadcastThread(output.converter, websocket_server)
        print('Starting recording')
        camera.start_recording(output, 'yuv')

        print('Starting websockets thread')
        websocket_thread.start()
        print('Starting broadcast thread')
        broadcast_thread.start()
        print('Starting liveness LED')
        liveness = Thread(target=app_liveness_led, args=())
        liveness.daemon = True
        liveness.start()
        socketio.run(app, host="0.0.0.0")
        while True:
            camera.wait_recording(1)
