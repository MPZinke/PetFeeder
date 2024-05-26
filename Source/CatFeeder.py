#!/opt/homebrew/bin/python3
# -*- coding: utf-8 -*-
__author__ = "MPZinke"

########################################################################################################################
#                                                                                                                      #
#   created by: MPZinke                                                                                                #
#   on 2023.12.21                                                                                                      #
#                                                                                                                      #
#   DESCRIPTION:                                                                                                       #
#   BUGS:                                                                                                              #
#   FUTURE:                                                                                                            #
#   LINKS: - https://randomnerdtutorials.com/raspberry-pi-pico-servo-motor-micropython/                                #
#                                                                                                                      #
########################################################################################################################


from adafruit_minimqtt.adafruit_minimqtt import MQTT
from adafruit_motor import servo
import board
import os
import pwmio
import socketpool
import time
import wifi


# ———————————————————————————————————————————————————— CONSTANTS  ———————————————————————————————————————————————————— #

MQTT_PUBLISH_TOPIC = os.getenv("MQTT_PUBLISH_TOPIC")
MQTT_SUBSCRIBE_TOPIC = os.getenv("MQTT_SUBSCRIBE_TOPIC")

SERVO_ANGLES = {"OPEN": 180, "CLOSE": 0}
SERVO_LABELS = {angle: label for label, angle in SERVO_ANGLES.items()}


# ————————————————————————————————————————————————————— GLOBALS  ————————————————————————————————————————————————————— #

BUTTON_PRESSED: bool = False
LAST_UPDATE = time.time() - 5  # `- 5` so when the first loop hits, the status will be updated
SERVO = None


# —————————————————————————————————————————————————————— SETUP  —————————————————————————————————————————————————————— #

def connect_to_wifi() -> SocketPool:
	wifi_ssid = os.getenv("WIFI_SSID")
	wifi_password = os.getenv("WIFI_PASSWORD")
	wifi.radio.connect(wifi_ssid, wifi_password)
	return socketpool.SocketPool(wifi.radio)


def connect_to_mqtt(socket_pool: socketpool.SocketPool) -> MQTT:
	mqtt_broker = os.getenv("MQTT_BROKER")
	mqtt_user = os.getenv("MQTT_USER")
	mqtt_password = os.getenv("MQTT_PASSWORD")

	mqtt_client = MQTT(broker=mqtt_broker, username=mqtt_user, password=mqtt_password, socket_pool=socket_pool)
	mqtt_client.on_connect = on_connect
	mqtt_client.on_disconnect = on_disconnect
	mqtt_client.on_message = on_message
	mqtt_client.on_publish = on_publish
	mqtt_client.connect()

	return mqtt_client


def create_servo() -> servo.Servo:
	global SERVO

	pwm = pwmio.PWMOut(board.GP0, duty_cycle=2 ** 15, frequency=50)
	SERVO = servo.Servo(pwm)
	SERVO.angle = 0


# ——————————————————————————————————————————————————————— MQTT ——————————————————————————————————————————————————————— #

def on_connect(client: MQTT, userdata, flags, rc) -> None:
	client.subscribe(MQTT_SUBSCRIBE_TOPIC)


def on_disconnect(client: MQTT, userdata, rc) -> None:
	raise Exception("Disconnected")


def on_message(client: MQTT, topic: str, message: str) -> None:
	global BUTTON_PRESSED, SERVO

	if(BUTTON_PRESSED):
		return

	if(message not in SERVO_ANGLES):
		return

	SERVO.angle = SERVO_ANGLES[message]

	client.publish(MQTT_PUBLISH_TOPIC, message)


def on_publish(client: MQTT, _0: None, topic: str, _1: int):
	global LAST_UPDATE

	LAST_UPDATE = time.time()


# ——————————————————————————————————————————————————————— HARDWARE ——————————————————————————————————————————————————————— #

def button_pressed() -> bool:
	return False


def toggle_angle() -> None:
	global SERVO

	SERVO.angle = {"OPEN": SERVO_ANGLES["CLOSE"], "CLOSE": SERVO_ANGLES["OPEN"]}[SERVO.angle]
	client.publish(MQTT_PUBLISH_TOPIC, SERVO_LABELS[SERVO.angle])


def main():
	global BUTTON_PRESSED, LAST_UPDATE, SERVO

	while(True):
		try:
			socket_pool: socketpool.SocketPool = connect_to_wifi()
			mqtt_client: MQTT = connect_to_mqtt(socket_pool)
			create_servo()

			last_poll = time.time() - 2
			while(True):
				current_time = time.time()

				## Button
				# User intervening, so ignore MQTT.
				if(button_pressed()):
					BUTTON_PRESSED = True
				elif(not button_pressed() and BUTTON_PRESSED):
					BUTTON_PRESSED = False
					toggle_angle()

				# Poll ever 2 seconds to maintain connection.
				if(current_time - last_poll >= 2):
					mqtt_client.loop()
					last_poll = current_time

				# Publish state every 5 seconds as to not span the topic.
				if(current_time - LAST_UPDATE >= 5):
					mqtt_client.publish(MQTT_PUBLISH_TOPIC, SERVO_LABELS[SERVO.angle])

		except Exception as error:
			print(error)
			time.sleep(30)

main()
