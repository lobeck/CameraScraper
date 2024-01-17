import io
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import boto3
import requests
from bs4 import BeautifulSoup

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

s3_client = boto3.client("s3")
ssm_client = boto3.client("ssm")
dynamo_resource = boto3.resource('dynamodb')

table = dynamo_resource.Table('CameraScraper-KeyValue')

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

patch_all()

# config handling
paginator = ssm_client.get_paginator("get_parameters_by_path")

@dataclass
class Config:
    url: str
    bucketName: str
    interval: timedelta = None


def fetch_config() -> Config:
    config = Config(url="", bucketName="")
    for page in paginator.paginate(Path="/cameraScraper", WithDecryption=True):
        for param in page["Parameters"]:
            if param["Name"].endswith("/interval"):
                config.interval = timedelta(minutes=float(param["Value"]))
            if param["Name"].endswith("/url"):
                config.url = param["Value"]
            if param["Name"].endswith("/bucket"):
                config.bucketName = param["Value"]
    return config


# initialize basics on cold start
config = fetch_config()


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
        picture_time = datetime.strptime(match.group(0), "%Y%m%d-%H%M%S")
        if picture_time > latest_picture:
            latest_picture = picture_time
        logger.debug(picture_time)

        prefix = "east"
        if "west" in img:
            prefix = "west"

        object_name = f"{prefix}/{picture_time.strftime('%Y/%m/%d')}/{picture_time.strftime('%H%M%S')}.jpg"
        logger.debug(object_name)

        try:
            logger.debug(s3_client.head_object(Bucket=config.bucketName, Key=object_name))
        except s3_client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                logger.debug(f"Object {object_name} does not exist")
                image = requests.get(img)
                if image.status_code == 200:
                    s3_client.upload_fileobj(io.BytesIO(image.content), config.bucketName, object_name,
                                             ExtraArgs={"ContentType": "image/jpeg",
                                                        "StorageClass": "INTELLIGENT_TIERING"}
                                             )
            else:
                raise e

    print(f"latest_picture: {latest_picture}")
    return latest_picture


if __name__ == "__main__":
    lambda_handler(None, None)
