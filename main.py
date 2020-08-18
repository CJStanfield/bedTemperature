import json
from enum import Enum

import Adafruit_DHT
import time
import requests


class Device:
    ON = 0
    OFF = 1
    STATUS = OFF
    SERVER_URL = 'http://192.168.86.56:8080/bed-api/'
    PI_URL = 'http://192.168.86.52:5000/'
    HEADERS = {'Accept': 'application/json'}
    RUNTIME_ALLOWED = 0
    REST_TIME_ALLOWED = 0
    DEVICE_TIME = 0
    DEVICE_TYPE = ""
    DID = ""

    def __init__(self, time_allowed, rest_allowed, device_type, did):
        self.RUNTIME_ALLOWED = time_allowed
        self.REST_TIME_ALLOWED = rest_allowed
        self.DEVICE_TYPE = device_type
        self.DID = did
        self.DEVICE_TIME = time.time()

    def get_device_info(self, device_type):
        device = requests.get(self.SERVER_URL + 'device?did=' + self.DID, headers=self.HEADERS)
        json_response = device.json()
        if device_type == 'fan':
            self.STATUS = json_response['fanStatus']
        elif device_type == 'fridge':
            self.STATUS = json_response['fridgeStatus']

    def check_device_time(self, currentTime, bedTime):
        if self.STATUS == self.ON:
            if currentTime - bedTime > self.RUNTIME_ALLOWED:
                return self.OFF
            else:
                return self.ON
        elif self.STATUS == self.OFF:
            if currentTime - bedTime > self.REST_TIME_ALLOWED:
                return self.ON
            else:
                return self.OFF


class Fridge(Device):
    def __init__(self, time_allowed, rest_allowed):
        super().__init__(time_allowed=time_allowed, rest_allowed=rest_allowed, device_type='fridge', did='1')
        self.status = self.OFF
        self.FRIDGE_URL = 'device/fridgePower?did=1&state='

    def set_fridge_status(self, status):
        if status != self.status:
            self.status == status
        # Next line can probably be inside the if statement. This forces the state though
        requests.get(self.SERVER_URL + self.FRIDGE_URL + str(status), headers=self.HEADERS)


class Fan(Device):
    def __init__(self, time_allowed, rest_allowed):
        super().__init__(time_allowed=time_allowed, rest_allowed=rest_allowed, device_type="fan", did='1')
        self.status = self.OFF
        self.FAN_URL = 'device/fanPower?did=1&state='

    def set_fan_status(self, status):
        if status != self.status:
            self.status == status
        # Next line can probably be inside the if statement. This forces the state though
        requests.get(self.SERVER_URL + self.FAN_URL + str(status), headers=self.HEADERS)


def get_temperature_difference(current_temperature, desired_temperature):
    return ((current_temperature - desired_temperature) / desired_temperature) * 100


class Bed:
    DHT_SENSOR = Adafruit_DHT.DHT11
    DHT_PIN = 4
    MINIMUM_CYCLE_TIME = 300
    BED_TIMER = 0
    MANUAL_CONTROL = True

    def __init__(self, uid):
        self.uid = uid
        self.fan = Fan(time_allowed=3600, rest_allowed=600)
        self.fridge = Fridge(time_allowed=3600, rest_allowed=600)
        self.did = "1"
        self.get_user_preferences()
        self.bedTemp = self.get_bed_temperature()
        self.BED_TIMER = time.time()

    # implement error checking
    def get_user_preferences(self):
        user = requests.get(self.fan.SERVER_URL + 'users?uid=' + self.uid, headers=self.fan.HEADERS)
        json_response = user.json()
        user_temp = json_response['temp']
        self.desiredTemp = user_temp
        # print("User Temperature: " + str(self.desiredTemp))
        self.MANUAL_CONTROL = json_response['manualControl']

    def get_bed_temperature(self):
        humidity, temperature = Adafruit_DHT.read(self.DHT_SENSOR, self.DHT_PIN)
        if temperature is not None:
            temp_fahrenheit = (temperature * (9 / 5)) + 32
            # print("Sensor Temperature: " + str(temp_fahrenheit))
            return temp_fahrenheit
        else:
            # print("Sensor Malfunction")
            return None

    def update_current_temperature(self, temperature):
        if temperature is not None:
            tempInt = int(temperature)
            temperatureUrl = "device/temperature?did=" + self.did + "&temperature=" + str(tempInt)
            requests.get(self.fan.SERVER_URL + temperatureUrl, headers=self.fan.HEADERS)

    def update_all_values(self):
        # Get/Update new values
        self.currentTemp = self.get_bed_temperature()
        self.update_current_temperature(self.currentTemp)
        self.get_user_preferences()
        self.fan.get_device_info('fan')
        self.fridge.get_device_info('fridge')

    def run(self):
        # update all values including temperatures and user preferences
        self.update_all_values()
        if self.currentTemp is None:
            return

        if not self.MANUAL_CONTROL:
            current_time = time.time()
            # Method does not change the device status
            allowed_fridge_status = self.fridge.check_device_time(current_time, self.fridge.DEVICE_TIME)
            temperature_difference = get_temperature_difference(current_temperature=self.currentTemp,
                                                                desired_temperature=self.desiredTemp)
            temp = current_time - self.BED_TIMER
            if allowed_fridge_status == Device.ON:

                if temperature_difference > 0:
                    if self.fan.STATUS == Device.OFF:
                        self.BED_TIMER = time.time()
                    if self.fridge.STATUS == Device.OFF:
                        self.BED_TIMER = time.time()
                        self.fridge.DEVICE_TIME = time.time()

                    self.fridge.set_fridge_status(self.fridge.ON)
                    self.fan.set_fan_status(self.fan.ON)


                elif current_time - self.BED_TIMER < self.MINIMUM_CYCLE_TIME:
                    self.fridge.set_fridge_status(self.fridge.ON)
                    self.fan.set_fan_status(self.fan.ON)
                    # self.fridge.DEVICE_TIME = time.time()

                else:
                    self.fridge.set_fridge_status(self.fridge.ON)
                    self.fan.set_fan_status(self.fan.OFF)
                    #self.BED_TIMER = time.time()

            elif allowed_fridge_status == Device.OFF:
                if self.fridge.STATUS == Device.ON:
                    self.fridge.DEVICE_TIME = time.time()
                self.fridge.set_fridge_status(self.fridge.OFF)
                self.fan.set_fan_status(self.fan.OFF)


coolBed = Bed(uid='cjstanfi')
while (True):
    coolBed.run()
    # coolBed.get_bed_temperature()
    time.sleep(5)
