terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# S3 Bucket for datasets, evidence, and benchmark artifacts
resource "aws_s3_bucket" "evidence_store" {
  bucket_prefix = "zoneshield-evidence-"
  force_destroy = true

  tags = {
    Project     = "ZoneShield-AI"
    Environment = var.environment
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "evidence_lifecycle" {
  bucket = aws_s3_bucket.evidence_store.id

  rule {
    id     = "expire-stale-evidence"
    status = "Enabled"

    expiration {
      days = 14
    }
  }
}

# IAM Role for Graviton Vision Worker with least-privilege permissions
resource "aws_iam_role" "vision_worker_role" {
  name_prefix = "zoneshield-worker-role-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_policy" "worker_policy" {
  name_prefix = "zoneshield-worker-policy-"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.evidence_store.arn,
          "${aws_s3_bucket.evidence_store.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_worker_policy" {
  role       = aws_iam_role.vision_worker_role.name
  policy_arn = aws_iam_policy.worker_policy.arn
}

resource "aws_iam_instance_profile" "worker_profile" {
  name_prefix = "zoneshield-instance-profile-"
  role        = aws_iam_role.vision_worker_role.name
}

# Security group for vision API & WebSocket
resource "aws_security_group" "worker_sg" {
  name_prefix = "zoneshield-sg-"
  description = "ZoneShield AI vision worker security group"

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "FastAPI REST and WebSocket"
  }

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "SSH administration"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# AWS Graviton Instance with COOL (Cloud-Optimized OpenCV Library)
resource "aws_instance" "graviton_cool" {
  count                = var.deploy_ec2 ? 1 : 0
  ami                  = var.graviton_cool_ami
  instance_type        = "c7g.xlarge" # 4 vCPUs, Arm Neoverse-V1 / NEON / KleidiCV
  iam_instance_profile = aws_iam_instance_profile.worker_profile.name
  security_groups      = [aws_security_group.worker_sg.name]

  user_data = <<-EOF
              #!/bin/bash
              echo "Starting ZoneShield AI on AWS Graviton with COOL..."
              git clone https://github.com/example/zoneshield-ai.git /app
              cd /app
              python3 -m pip install -r requirements.txt
              python3 -m zoneshield.selfcheck
              python3 -m backend.main
              EOF

  tags = {
    Name        = "ZoneShield-Graviton-COOL"
    Architecture = "arm64"
    Workload    = "Production-Vision"
  }
}

# x86 Baseline Instance for 3-Way Benchmark Comparison
resource "aws_instance" "x86_baseline" {
  count                = (var.deploy_ec2 && var.deploy_baseline_x86) ? 1 : 0
  ami                  = var.x86_ami
  instance_type        = "c7i.xlarge" # 4 vCPUs, Intel Xeon
  iam_instance_profile = aws_iam_instance_profile.worker_profile.name
  security_groups      = [aws_security_group.worker_sg.name]

  tags = {
    Name         = "ZoneShield-x86-Baseline"
    Architecture = "x86_64"
    Workload     = "Benchmark-Baseline"
  }
}

# Cost Guard: CloudWatch Alarm to Stop Instance if Idle > 30 minutes
resource "aws_cloudwatch_metric_alarm" "idle_stop_alarm" {
  count               = var.deploy_ec2 ? 1 : 0
  alarm_name          = "zoneshield-graviton-idle-stop"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = "3"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "600" # 10 minutes * 3 = 30 minutes
  statistic           = "Average"
  threshold           = "5.0"
  alarm_description   = "Auto-stop Graviton instance when idle to safeguard AWS credits (C5 Budget Rule)"
  alarm_actions       = ["arn:aws:automate:${var.aws_region}:ec2:stop"]

  dimensions = {
    InstanceId = aws_instance.graviton_cool[0].id
  }
}
