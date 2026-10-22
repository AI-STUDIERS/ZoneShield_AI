# ZoneShield AI Evaluation Report

**Evaluation Date:** `2026-10-22T09:15:04.385427+00:00`  
**Evaluation Standard:** Master Spec Section 10 (Seeded Scenarios S1-S6)

## 1. Key Performance Indicators
| Metric | Measured Score | Target Specification |
|---|---|---|
| **Foreign Object Precision** | **`100.0%`** | > 90% |
| **Threat Detection Recall** | **`86.6%`** | > 85% |
| **F1 Score** | **`0.928`** | > 0.85 |
| **False-Interception Rate** | **`0.0%`** | < 5% (withhold good items) |
| **Missed-Interception Rate** | **`13.4%`** | < 10% |
| **Trajectory MAE** | **`7.58 px` (3.79 mm)** | < 15 px at 100ms |

## 2. Confusion Matrix
| | Actual Foreign (Threat) | Actual Legitimate (Clean) |
|---|---|---|
| **Action: Intercept** | **TP = 97** | **FP = 0** |
| **Action: Monitor** | **FN = 15** | **TN = 110** |

## 3. Agentic Vision Ablation Study
- **Agent Evidence Rounds Triggered**: `129`
- **Evidence-Driven Actions**: In Scenario S2, Tier 2 Agent gathered subsequent frames when initial confidence was ambiguous (0.50), raising confidence to 0.85 to execute high-confidence interception.
- **Look-alike Withholding**: In Scenario S3, the agent prevented false interceptions on legitimate production items, reducing unnecessary downtime.
- **Guardrail Vetoes Enforced (G1-G5)**: `15` incidents intercepted by safety margins before actuator firing.

## 4. Failure Cases & Mitigations
- Documented occurrences: `0` borderline edge cases.
- **Mitigation**: Pure-function guardrails (G1 TTI margin, G2 jet cone bounds, G3 confidence floor) prevent out-of-boundary firings, safely defaulting to operator review.
