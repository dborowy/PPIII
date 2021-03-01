#!/usr/bin/env python
import os
import smtplib, ssl
import time
from influxdb import InfluxDBClient
from influxdb.client import InfluxDBClientError
import datetime
import pytz
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont
import logging
import logging.handlers

#Display
serial = i2c(port=1, address=0x3C)
device = ssd1306(serial, height=32)
font = ImageFont.truetype("arial.ttf", size=32)

class TlsSMTPHandler(logging.handlers.SMTPHandler):
    def emit(self, record):
        try:
            import smtplib
            import string # for tls add this line
            try:
                from email.utils import formatdate
            except ImportError:
                formatdate = self.date_time
            port = self.mailport
            if not port:
                port = smtplib.SMTP_PORT
            smtp = smtplib.SMTP(self.mailhost, port)
            msg = self.format(record)
            msg = "From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: %s\r\n\r\n%s" % (
                            self.fromaddr,
                            ",".join(self.toaddrs),
                            self.getSubject(record),
                            formatdate(), msg)
            if self.username:
                smtp.ehlo() # for tls add this line
                smtp.starttls() # for tls add this line
                smtp.ehlo() # for tls add this line
                smtp.login(self.username, self.password)
            smtp.sendmail(self.fromaddr, self.toaddrs, msg)
            smtp.quit()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

#Logging
logger = logging.getLogger() 
gm = TlsSMTPHandler(("smtp.gmail.com", 587), 'mail', ['dominikborowy@gmail.com'], 'Error Termometru', ('PI@gmail.com', 'password'))
gm.setLevel(logging.ERROR) 
logger.addHandler(gm)

def sensor():
    for i in os.listdir('/sys/bus/w1/devices'):
        if i != 'w1_bus_master1':
            ds18b20 = i
    return ds18b20

def read(ds18b20):
    location = '/sys/bus/w1/devices/' + ds18b20 + '/w1_slave'
    tfile = open(location)
    text = tfile.read()
    tfile.close()
    secondline = text.split("\n")[1]
    temperaturedata = secondline.split(" ")[9]
    temperature = float(temperaturedata[2:])
    celsius = temperature / 1000
    farenheit = (celsius * 1.8) + 32
    return celsius, farenheit

def loop(ds18b20):
    #mail
    smtp_server =  "smtp.gmail.com"
    portsmtp = 465
    sender_email = "PI@gmail.com"
    receiver_email = ["dominikborowy@gmail.com"]
    password = "password"  

    #database
    USER = 'root'
    PASSWORD = 'root'
    DBNAME = 'temp'
    host='localhost'
    hostName = 'pi'
    port=8086
    metric = "Server Room Temperatures"
    retention_policy = 'awesome_policy'
    grafana_timezone = pytz.utc

    while True:
        client = InfluxDBClient(host, port, USER, PASSWORD, DBNAME)
        client.create_retention_policy(retention_policy, '30d', 3, default=True)
        json_temp = {
            "tags": {
                "hostName": hostName
            },
            "measurement": metric,
            "fields": {
                "value": read(ds18b20)[0]
            },
            "time": datetime.datetime.now(grafana_timezone).strftime("%m/%d/%Y, %H:%M:%S"),
        }

        #display
        with canvas(device) as draw:
            draw.text((0, 0), str(json_temp['fields']['value']), fill="white",font=font)
        
        with open ('last_breath','w') as file:
            file.write (str(json_temp))

        client.write_points([json_temp], retention_policy=retention_policy)

        if read(ds18b20) != None and read(ds18b20)[0] > 35:
            message = "Temperatura w serwerowni wynosi {}".format(read(ds18b20)[0])

            with smtplib.SMTP_SSL(smtp_server, portsmtp) as server:
                server.login(sender_email, password)
                server.sendmail(sender_email, receiver_email, message)
                server.close()
        time.sleep(180)

def kill():
    quit()

if __name__ == '__main__':
    try:
        serialNum = sensor()
        loop(serialNum)
    except KeyboardInterrupt:
        kill()
    except:
        logger.exception('Error:')
