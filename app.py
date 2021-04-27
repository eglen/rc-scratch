from flask import Flask, render_template, request
from flask.logging import default_handler
from time import sleep
import pigpio
from logging.config import dictConfig

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
HORIZ_SERVO_PORT = 13
VERT_SERVO_PORT= 12

# Servo Info
HORIZ_SERVO_CENTER = 1750
VERT_SERVO_CENTER = 1500

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
    # Get the values from the request
    horizontal = 25 * int(request.form["rudder"])
    vertical = 25 * int(request.form["throttle"])
    print("13: " + str(horizontal) + "\t" + str(HORIZ_SERVO_CENTER - horizontal) + "\t 12: " + str(vertical) + "\t" + str(VERT_SERVO_CENTER-vertical))

    # Move the Servos
    setServoDuty(HORIZ_SERVO_PORT, clamp(HORIZ_SERVO_CENTER - horizontal, 500, 2500))
    setServoDuty(VERT_SERVO_PORT, clamp(VERT_SERVO_CENTER - vertical, 600, 2500))

    # Wait for 0.2s so that the servos have time to move
    sleep(0.2)

    # Stop the servo motors to save energy and reduce noise
    gpio.set_servo_pulsewidth(HORIZ_SERVO_PORT, 0)
    gpio.set_servo_pulsewidth(VERT_SERVO_PORT, 0)

    # Return empty request (Should return a 200 OK with an empty body)
    return ""

# Run the app on the local development server
# Accept any IP address
# Create ad-hoc SSL encryption (needed for iOS 13 support)
if __name__ == "__main__":
    #app.run(host="0.0.0.0", ssl_context='adhoc')
    app.run(host="0.0.0.0")
    app.logger.removeHandler(default_handler)
