# ZoneShield AI — Security Policy

## Supported Versions

Security patches are provided for the latest release branch only.

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly by
contacting the maintainers at **zoneshield@example.org**. Do not open a public
GitHub issue for security vulnerabilities.

Include as much of the following as possible:

* Type of issue (e.g., data exposure, credential leak, injection)
* Steps to reproduce
* Impact assessment
* Suggested fix or mitigation
* Your contact information

## Security Considerations for ZoneShield AI

* **No physical hardware control**: The actuator is strictly simulated (`SimulatedActuator` per constraint C1).
* **No facial recognition**: Video processing operates on conveyor surfaces only; no human tracking or biometrics.
* **Credential management**: Never commit `.env` files or AWS credentials. Use `.env.example` as a template.
* **Least-privilege IAM**: Terraform IAM policies are intentionally scoped to S3, CloudWatch, and Bedrock only.
* **Cost guard**: A CloudWatch idle-stop alarm automatically stops EC2 instances when CPU < 5% for 30 minutes.

## Disclosure

Security reports will be acknowledged within 7 business days. We will work
with you to understand and resolve the issue before any public disclosure.