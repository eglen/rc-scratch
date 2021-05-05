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
HORIZ_SERVO_PORT = 13
VERT_SERVO_PORT= 12

#LED GPIO
LIVENESS_PORT = 4
ACTIVITY_PORT = 18

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

    #Data LED ON
    gpio.write(ACTIVITY_PORT,1)

    # Move the Servos
    setServoDuty(HORIZ_SERVO_PORT, clamp(HORIZ_SERVO_CENTER - horizontal, 500, 2500))
    setServoDuty(VERT_SERVO_PORT, clamp(VERT_SERVO_CENTER - vertical, 600, 2500))

    # Wait for 0.2s so that the servos have time to move
    sleep(0.1)

    # Stop the servo motors to save energy and reduce noise
    gpio.set_servo_pulsewidth(HORIZ_SERVO_PORT, 0)
    gpio.set_servo_pulsewidth(VERT_SERVO_PORT, 0)

    #Data LED OFF
    gpio.write(ACTIVITY_PORT,0)

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
        gpio.write(LIVENESS_PORT,1)
        sleep(0.1)
        gpio.write(LIVENESS_PORT,0)
        sleep(0.1)
        gpio.write(LIVENESS_PORT,1)
        sleep(0.1)
        gpio.write(LIVENESS_PORT,0)
        sleep(2)


# Run the app on the local development server
# Accept any IP address
# Create ad-hoc SSL encryption (needed for iOS 13 support)
if __name__ == "__main__":
    #app.run(host="0.0.0.0", ssl_context='adhoc')
    liveness = threading.Thread(target=app_liveness_led, args=())
    liveness.daemon = True
    liveness.start()
    app.run(host="0.0.0.0")
    app.logger.removeHandler(default_handler)

