resource "aws_dynamodb_table" "KeyValue" {
  name         = "CameraScraper-KeyValue"
  hash_key     = "Key"
  billing_mode = "PAY_PER_REQUEST"


  attribute {
    name = "Key"
    type = "S"
  }
}