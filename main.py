import io
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import boto3
import requests
from bs4 import BeautifulSoup

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

s3_client = boto3.client("s3")
ssm_client = boto3.client("ssm")
dynamo_resource = boto3.resource('dynamodb')

table = dynamo_resource.Table('CameraScraper-KeyValue')
sunset_table = dynamo_resource.Table('CameraScraper-SunTimes')

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

patch_all()

# config handling
paginator = ssm_client.get_paginator("get_parameters_by_path")

@dataclass
class Config:
    url: str
    bucketName: str
    knownPrefixes: list[str]
    interval: timedelta = None


@dataclass
class METAR:
    def __init__(self, station='EDMA'):
        r = requests.get(f"https://aviationweather.gov/api/data/metar?ids={station}", timeout=(1, 1))
        r.raise_for_status()
        text = r.text
        if text.startswith(station):
            self.text = text[:-1]  # cut trailing newline

        now = datetime.now()
        metar_time = datetime.strptime(self.text[5:11], "%d%H%M")
        self.valid_from = metar_time.replace(year=now.year, month=now.month)

    text: str
    valid_from: datetime


class SunsetCache:
    def __init__(self):
        self.cache = {}

    def get(self, station: str, date: datetime) -> Optional[dict]:
        if station not in self.cache:
            self.cache[station] = {}
        d = date.strftime("%Y-%m-%d")
        if d not in self.cache[station]:
            entry = sunset_table.get_item(Key={"Station": station, "Date": d})
            if "Item" in entry:
                self.cache[station][d] = entry["Item"]
                return entry["Item"]
        else:
            return self.cache[station][d]
        return None


def fetch_config() -> Config:
    config = Config(url="", bucketName="", knownPrefixes=["east", "west"])
    for page in paginator.paginate(Path="/cameraScraper", WithDecryption=True):
        for param in page["Parameters"]:
            if param["Name"].endswith("/interval"):
                config.interval = timedelta(minutes=float(param["Value"]))
            if param["Name"].endswith("/url"):
                config.url = param["Value"]
            if param["Name"].endswith("/bucket"):
                config.bucketName = param["Value"]
            if param["Name"].endswith("/knownPrefixes"):
                config.bucketName = param["Value"].split(",")
    return config


# initialize basics on cold start
config = fetch_config()
sunset_cache = SunsetCache()


def lambda_handler(event, context):
    global config
    logger.debug(event)
    logger.debug(context)

    last_run_item = table.get_item(Key={"Key": "LastRun"})
    if "Item" in last_run_item:
        last_run = datetime.strptime(last_run_item["Item"]["Value"], "%Y-%m-%d %H:%M:%S")
    else:
        last_run = datetime(1970, 1, 1)

    logger.debug(config)
    if last_run + config.interval > datetime.now():
        logger.info(f"Last run is too recent - check back {last_run + config.interval}")
        return

    # refresh config before scrape
    config = fetch_config()

    try:
        xray_recorder.begin_subsegment('scrape')
        last_run = scrape(config)
        xray_recorder.end_subsegment()
        if last_run.year == 1970:
            # if no pictures are found, back off anyway to prevent hammering
            last_run = datetime.now()
    except Exception as e:
        logger.error(e)
    finally:
        table.put_item(Item={"Key": "LastRun", "Value": last_run.strftime("%Y-%m-%d %H:%M:%S")})


def scrape(config: Config):
    latest_picture = datetime(1970, 1, 1)
    latest_pictures = {}
    for prefix in config.knownPrefixes:
        prefix_latest_picture = table.get_item(Key={"Key": f"{prefix}-latestPicture"})
        if "Item" in prefix_latest_picture:
            latest_pictures[prefix] = datetime.strptime(prefix_latest_picture["Item"]["Value"], "%Y-%m-%d %H:%M:%S")
        else:
            latest_pictures[prefix] = datetime(1970, 1, 1)

    metar = None
    try:
        metar = METAR()
    except Exception as e:
        print(e)

    # start scraping
    page = requests.get(config.url)

    soup = BeautifulSoup(page.text, 'html.parser')

    for img in soup.find_all(id="wimg1"):
        img = img.get("src")
        filename = img.split("/")[-1]
        logger.debug(filename)

        regex = r"(20[0-9]{6}-[0-9]{6})"
        match = re.search(regex, filename)
        logger.debug(match.group(0))

        prefix = "east"
        if "west" in img:
            prefix = "west"

        picture_time = datetime.strptime(match.group(0), "%Y%m%d-%H%M%S")
        if picture_time > latest_picture:
            latest_picture = picture_time
        logger.debug(picture_time)

        if picture_time > latest_pictures[prefix]:
            latest_pictures[prefix] = picture_time

        object_name = f"{prefix}/{picture_time.strftime('%Y/%m/%d')}/{picture_time.strftime('%H%M%S')}.jpg"
        logger.debug(object_name)

        try:
            logger.debug(s3_client.head_object(Bucket=config.bucketName, Key=object_name))
        except s3_client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.debug(f"Object {object_name} does not exist")
                image = requests.get(img)
                if image.status_code == 200:
                    metadata = {}
                    if metar is not None and metar.valid_from < picture_time < metar.valid_from + timedelta(hours=1):
                        metadata["metar"] = metar.text
                    try:
                        sunset = sunset_cache.get("EDMA", picture_time)
                        if sunset is not None:
                            metadata["BCMT"] = sunset["BCMT"]
                            metadata["SR"] = sunset["SR"]
                            metadata["SS"] = sunset["SS"]
                            metadata["ECET"] = sunset["ECET"]
                    except Exception as e:
                        print(e)
                    s3_client.put_object(Body=io.BytesIO(image.content), Bucket=config.bucketName, Key=object_name,
                                         ContentType="image/jpeg", StorageClass="INTELLIGENT_TIERING", Metadata=metadata
                                         )
            else:
                raise e

    for prefix in config.knownPrefixes:
        table.put_item(Item={"Key": f"{prefix}-latestPicture", "Value": latest_pictures[prefix].strftime("%Y-%m-%d %H:%M:%S")})
    print(f"latest_pictures: {latest_pictures}")
    print(f"latest_picture: {latest_picture}")
    return latest_picture


if __name__ == "__main__":
    lambda_handler(None, None)
