resource "aws_ssm_parameter" "interval" {
  name  = "/cameraScraper/interval"
  type  = "String"
  value = "10.25" # minutes
}

resource "aws_ssm_parameter" "url" {
  name  = "/cameraScraper/url"
  type  = "String"
  value = "https://pl-jesenwang.de/?page_id=104"
}

resource "aws_ssm_parameter" "bucket" {
  name  = "/cameraScraper/bucket"
  type  = "String"
  value = var.bucket
}
