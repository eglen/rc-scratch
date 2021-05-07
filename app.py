from flask import Flask, render_template, request, Response
from flask.logging import default_handler
from camera_pi import Camera
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

# Create Flask App
app = Flask(__name__)


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

# Expose an endpoint for sending the servo coordinates
# from the JS to the Flask Backend
@app.route("/moveservos", methods=["POST"])
def moveServos():
    #Data LED ON
    gpio.write(ACTIVITY_PORT, 1)

    # Get the values from the request
    horizontal = HORIZ_CONVERSION * int(request.form["horizontal"])
    vertical = VERT_CONVERSION * int(request.form["vertical"])

    print("H: " + str(horizontal) + "\t" + str(HORIZ_SERVO_CENTER - horizontal) + "\t" + str(clamp(HORIZ_SERVO_CENTER - horizontal, HORIZ_SERVO_MIN, HORIZ_SERVO_MAX)) +
          "\t V: " + str(vertical) + "\t" + str(VERT_SERVO_CENTER - vertical) + "\t" + str(clamp(VERT_SERVO_CENTER - vertical, VERT_SERVO_MIN, VERT_SERVO_MAX)))

    # Move the Servos
    setServoDuty(HORIZ_SERVO_PORT, clamp(HORIZ_SERVO_CENTER - horizontal, HORIZ_SERVO_MIN, HORIZ_SERVO_MAX))
    setServoDuty(VERT_SERVO_PORT, clamp(VERT_SERVO_CENTER - vertical, VERT_SERVO_MIN, VERT_SERVO_MAX))

    # Don't sleep in the handling thread, leave that to the client
    #sleep(0.05)

    # We've got enough power and high enough quality servos to prioritize responsiveness
    #gpio.set_servo_pulsewidth(HORIZ_SERVO_PORT, 0)
    #gpio.set_servo_pulsewidth(VERT_SERVO_PORT, 0)

    #Data LED OFF
    gpio.write(ACTIVITY_PORT, 0)

    # Return empty request (Should return a 200 OK with an empty body)
    return ""

#https://blog.miguelgrinberg.com/post/video-streaming-with-flask
def gen(camera):
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(Camera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def app_liveness_led():
    #App LED blink pattern
    while True:
        gpio.write(LIVENESS_PORT, 1)
        sleep(0.1)
        gpio.write(LIVENESS_PORT, 0)
        sleep(0.1)
        gpio.write(LIVENESS_PORT, 1)
        sleep(0.1)
        gpio.write(LIVENESS_PORT, 0)
        sleep(2)


# Run the app on the local development server
# Accept any IP address
if __name__ == "__main__":
    #app.run(host="0.0.0.0", ssl_context='adhoc')
    liveness = threading.Thread(target=app_liveness_led, args=())
    liveness.daemon = True
    liveness.start()
    app.run(host="0.0.0.0")
    app.logger.removeHandler(default_handler)

