resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.lambda_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_event_rule" "trigger" {
  name                = "${local.lambda_name}-trigger"
  schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "trigger_lambda" {
  target_id = "scraper_lambda"
  rule      = aws_cloudwatch_event_rule.trigger.name
  arn       = aws_lambda_function.scraper.arn
}
