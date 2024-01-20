resource "aws_route53_zone" "main" {
  name = var.domain_name
}

resource "aws_route53_record" "main" {
  name = ""
  type = "A"
  alias {
    evaluate_target_health = false
    name                   = aws_cloudfront_distribution.images.domain_name
    zone_id                = aws_cloudfront_distribution.images.hosted_zone_id
  }
  zone_id = aws_route53_zone.main.id
}

resource "aws_route53_record" "main-v6" {
  name = ""
  type = "AAAA"
  alias {
    evaluate_target_health = false
    name                   = aws_cloudfront_distribution.images.domain_name
    zone_id                = aws_cloudfront_distribution.images.hosted_zone_id
  }
  zone_id = aws_route53_zone.main.id
}