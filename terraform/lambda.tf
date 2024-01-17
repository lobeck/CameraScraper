locals {
  lambda_name_scraper = "camera-scraper"
  lambda_name_edge    = "camera-edge"
}

resource "aws_lambda_function" "scraper" {
  function_name                  = local.lambda_name_scraper
  role                           = aws_iam_role.scraper.arn
  handler                        = "main.lambda_handler"
  runtime                        = "python3.12"
  filename                       = "../lambda.zip"
  source_code_hash               = filebase64sha256("../lambda.zip")
  architectures                  = ["arm64"]
  timeout                        = 120
  reserved_concurrent_executions = 1

  tracing_config {
    mode = "Active"
  }
}

resource "aws_lambda_permission" "scraper" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scraper.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.trigger.arn
}

data "archive_file" "edge" {
  type        = "zip"
  source_file = "../edge.py"
  output_path = "../edge.zip"
}

resource "aws_lambda_function" "edge" {
  function_name    = local.lambda_name_edge
  role             = aws_iam_role.edge.arn
  handler          = "edge.lambda_handler"
  runtime          = "python3.11"
  filename         = data.archive_file.edge.output_path
  source_code_hash = data.archive_file.edge.output_base64sha256

  publish = true
  # :'( still no ARM for lambda@edge
  # architectures                  = ["arm64"]

  provider = aws.us-east-1
}


resource "aws_lambda_permission" "edge" {
  statement_id  = "AllowExecutionFromCloudFront"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.edge.function_name
  principal     = "edgelambda.amazonaws.com"

  provider = aws.us-east-1
}