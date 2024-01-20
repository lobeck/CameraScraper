resource "aws_dynamodb_table" "KeyValue" {
  name         = "CameraScraper-KeyValue"
  hash_key     = "Key"
  billing_mode = "PAY_PER_REQUEST"


  attribute {
    name = "Key"
    type = "S"
  }
}

resource "aws_dynamodb_table" "SunTimes" {
  name         = "CameraScraper-SunTimes"
  hash_key     = "Station"
  range_key    = "Date"
  billing_mode = "PAY_PER_REQUEST"


  attribute {
    name = "Station"
    type = "S"
  }

  attribute {
    name = "Date"
    type = "S"
  }
}