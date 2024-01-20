import re

import boto3
import requests
from bs4 import BeautifulSoup

dynamo_resource = boto3.resource('dynamodb')

table = dynamo_resource.Table('CameraScraper-SunTimes')

r = requests.get("https://www.dwd.de/DE/fachnutzer/luftfahrt/teaser/luftsportberichte/edma/node.html")

r.raise_for_status()

soup = BeautifulSoup(r.text, "html.parser")
data = soup.find("pre").text

station = data[0:4]
print(station)

REGEX = r"^[a-zA-Z]{2} (?P<Date>[0-9-]{10})  (?P<BCMT>[0-9\:]{5}) (?P<SR>[0-9\:]{5}) (?P<SS>[0-9\:]{5}) (?P<ECET>[0-9\:]{5}) (?P<MR>[0-9\:\- ]{5}) (?P<MS>[0-9\:\- ]{5}) ?((?P<FM>VM)|(?P<NM>NM))?$"

for line in data.splitlines():
    m = re.match(REGEX, line)
    if m is not None:
        d = m.groupdict()
        d["Station"] = station
        table.put_item(Item=d)

