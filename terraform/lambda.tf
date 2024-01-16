locals {
  lambda_name = "camera-scraper"
}

resource "aws_lambda_function" "scraper" {
  function_name                  = local.lambda_name
  role                           = aws_iam_role.scraper.arn
  handler                        = "main.lambda_handler"
  runtime                        = "python3.12"
  filename                       = "../lambda.zip"
  source_code_hash               = filebase64sha256("../lambda.zip")
  architectures                  = ["arm64"]
  timeout                        = 120
  reserved_concurrent_executions = 1
}

resource "aws_lambda_permission" "scraper" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scraper.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.trigger.arn
}