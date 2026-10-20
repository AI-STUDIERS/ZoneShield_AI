output "evidence_bucket_name" {
  value       = aws_s3_bucket.evidence_store.bucket
  description = "S3 bucket for storing evidence and benchmark artifacts"
}

output "graviton_instance_ip" {
  value       = length(aws_instance.graviton_cool) > 0 ? aws_instance.graviton_cool[0].public_ip : null
  description = "Public IP of AWS Graviton COOL production worker"
}

output "x86_instance_ip" {
  value       = length(aws_instance.x86_baseline) > 0 ? aws_instance.x86_baseline[0].public_ip : null
  description = "Public IP of x86 baseline instance"
}
