from datetime import datetime, timedelta

import boto3

dynamo_resource = boto3.resource("dynamodb")

table = dynamo_resource.Table("CameraScraper-KeyValue")

HEADER_DATE_FORMAT = "%a, %d %b %Y %H:%M:%S %Z"


def handle_origin_request(request):
    # build override path
    prefix = request["uri"].replace("/", "").split(".")[0]
    response = table.get_item(Key={"Key": f"{prefix}-latestPicture"})
    picture_time = datetime.strptime(response["Item"]["Value"], "%Y-%m-%d %H:%M:%S")

    request["uri"] = f"/{prefix}/{picture_time.strftime('%Y/%m/%d')}/{picture_time.strftime('%H%M%S')}.jpg"
    # mark requests so the origin-response handler can identify them
    request["headers"]["edgelambda-marker"] = [{"key": "edgelambda-marker", "value": "rerouted"}]
    return request


def lambda_handler(event, context):
    try:
        event_type = event["Records"][0]["cf"]["config"]["eventType"]
        if event_type == "origin-request":
            request = event["Records"][0]["cf"]["request"]
            if request["uri"] not in ["/east.jpg", "/west.jpg"]:
                # skip requests we don't care about
                return request

            # override origin path on requests to the generic images
            return handle_origin_request(request)
        elif event_type == "origin-response":
            response = event["Records"][0]["cf"]["response"]
            # search for marked requests - ignore non-marked
            if "edgelambda-marker" not in event["Records"][0]["cf"]["request"]["headers"]:
                return response
            # override cache timing to prevent the default 3600
            try:
                last_modified = datetime.strptime(response["headers"]["last-modified"][0]["value"], HEADER_DATE_FORMAT)
                expires = last_modified + timedelta(minutes=10)
                if expires < datetime.now():
                    # dummy to jump into except block
                    raise ValueError("Expired")
                response["headers"]["expires"] = [{"key": "Expires", "value": expires.strftime(HEADER_DATE_FORMAT.replace(" %Z", " GMT"))}]
            except Exception as e:
                print(e)
                response["headers"]["cache-control"] = [{"key": "Cache-Control", "value": "max-age=60"}]
            return response
        else:
            raise ValueError(event_type)
    except Exception as e:
        print(e)
        return {
            "status": "404",
            "statusDescription": "Not Found",
            "headers": {
                "cache-control": [
                    {
                        "key": "Cache-Control",
                        "value": "max-age=60"
                    }
                ],
                "content-type": [
                    {
                        "key": "Content-Type",
                        "value": "text/html"
                    }
                ]
            },
            "body": "Better luck next time"
        }


if __name__ == "__main__":
    import json

    with open("request.json", "r") as f:
        from pprint import pprint
        pprint(lambda_handler(json.load(f), {}))
