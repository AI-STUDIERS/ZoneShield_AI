# ZoneShield AI — Design System & Mission-Critical Console Specification

> **Tactical Glass Cockpit Specification for Industrial HMI / Digital Twin Operations**  
> *OpenCV AI Competition 2026 | Cloud-Optimized OpenCV Library (COOL) & AWS Graviton Target*

---

## 1. Design Direction & Aesthetic

The ZoneShield AI operations dashboard is engineered as a **tactical glass cockpit** for industrial high-speed conveyor anomaly interception. It merges the information density and responsiveness of an air-traffic / defense radar console with the ergonomic polish of modern mission-critical operator software.

- **Calm, High-Contrast Dark Canvas**: Deep `#05070d` background eliminates ocular fatigue during long observation cycles.
- **Glassmorphism with Discipline**: Panels employ `backdrop-filter: blur(12px)`, hairline borders (`1px solid rgba(255, 255, 255, 0.08)`), subtle top inner highlights (`inset 0 1px 0 0 rgba(255, 255, 255, 0.08)`), and soft layered shadows. Depth is strictly constrained to 3 elevation tiers.
- **Semantic Color Integrity**: Color is strictly functional and communicative, never purely decorative.
- **Micro-Label Hierarchy**: 10–11px uppercase tracking labels (`0.08em` letter-spacing) provide unambiguous context above high-visibility monospace readouts.
- **Zero-Jitter Tabular Numerals**: All timings, frame counters, coordinates, and percentages use **JetBrains Mono** with `font-variant-numeric: tabular-nums` to eliminate numeric displacement jitters at 60 FPS.

---

## 2. Design Tokens

### 2.1 Surfaces & Panels
| Token | CSS Variable | Hex / RGBA Value | Purpose |
|---|---|---|---|
| **Base Canvas** | `--bg-0` | `#05070d` | Deepest background layer |
| **Workspace Fill** | `--bg-1` | `#0a0f1c` | Sub-surface for toolbars and footers |
| **Glass Panel** | `--panel` | `rgba(15, 23, 42, 0.55)` | Elevation Level 1 (Card containers, HUDs) |
| **Elevated Panel** | `--panel-elevated`| `rgba(30, 41, 59, 0.65)` | Elevation Level 2 (Modals, popovers) |
| **Hairline Border**| `--panel-border` | `rgba(255, 255, 255, 0.08)` | 1px clean geometric panel boundaries |
| **Active Glow Border**| `--panel-border-glow`| `rgba(0, 242, 255, 0.25)` | Focused card and active state highlight |

### 2.2 Structural Accent
| Token | CSS Variable | Hex / RGBA Value | Purpose |
|---|---|---|---|
| **Primary Cyan** | `--accent-cyan` | `#00f2ff` | Viewport reticles, active indicators, grid crosshairs |
| **Dim Cyan** | `--accent-cyan-dim`| `rgba(0, 242, 255, 0.15)` | Inactive lines, subtle bounding box fills |
| **Grid Lines** | `--accent-cyan-line`| `rgba(0, 242, 255, 0.05)` | Metric conveyor millimeter grid lines |

### 2.3 Semantic Colors (Strict Operational Meaning)
| Semantic Role | Token | Hex | Meaning & Application |
|---|---|---|---|
| **Healthy / Active** | `--sem-green` | `#22c55e` | OpenCV 5 verification, armed guardrails, legitimate production item |
| **Infrastructure / Steady** | `--sem-blue` | `#3b82f6` | AWS COOL Arm64 Graviton status, normal tracking, nominal conveyor speeds |
| **Simulated / Caution / HITL** | `--sem-amber` | `#f59e0b` | **Simulated Actuator badge (C1)**, mock telemetry banner, human review pending, TTI warning |
| **Threat / Veto / E-Stop** | `--sem-red` | `#ef4444` | Foreign object threat, G1-G5 guardrail veto, emergency kill switch active, shield zone |
| **Operator Manual Intervention** | `--sem-magenta`| `#ff2e97` | Manual operator fire override, human inspection ring, highlighted track selection |

### 2.4 Typography & Motion
- **UI Body & Headings**: Inter (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto`)
- **Telemetry, IDs, Timings**: JetBrains Mono with `tabular-nums`
- **Radii**: `12px` on glass panels, `8px` on tactical control buttons, `6px` on micro-badges
- **Transitions**: `120–200ms ease-out` for UI buttons; spring only for emergency modals; all animations honor `prefers-reduced-motion`

---

## 3. Component Hierarchy

```
App.tsx (Root Container)
├── TopBar
│   ├── Logo & Brand (ZoneShield AI v0.1)
│   ├── Pulsing Compliance Dots (OpenCV 5.0 green, AWS COOL blue, SIMULATED ACTUATOR amber)
│   ├── Connection State Chip (LIVE / RECONNECTING / OFFLINE)
│   ├── Uptime Clock (hh:mm:ss tabular-nums)
│   └── Sound FX & Fullscreen Toggles
├── ConnectionBanner
│   ├── Emergency Kill Switch Active Banner (Red alert strip)
│   ├── Connection Lost Strip (Exponential backoff countdown + "Retry now")
│   └── Mock Telemetry Strip (Displayed when ?mock=1 is active)
├── Main Workspace (1fr / 420px Grid)
│   ├── ViewportWorkspace
│   │   ├── ViewportToolbar (2D RADAR / 3D ISOMETRIC / MOG2 MASK toggles, Target Counter, G1-G5 Chips, Layer Toggles)
│   │   ├── CanvasViewport (Dual stacked canvas: DPR-aware Static Grid + 60 FPS Dynamic Track Render)
│   │   ├── IsometricViewport (3D Canvas isometric projection, orbit camera, extruded track stalks, jet volume)
│   │   └── Mog2MaskViewport (Binary segmented foreground mask from OpenCV BackgroundSubtract)
│   └── SidePanelTabs
│       ├── Tab Header (TELEMETRY | TRACE | REVIEW(n) | SELF-CHECK)
│       ├── TelemetryTab (4 KPI Cards with deltas, 120-sample Sparkline, Real Keys Waterfall, 60s Actuator Strip)
│       ├── DecisionTraceTab (Chronological feed, T1/T2 badges, agent tool-call expansion, filters, click-to-highlight)
│       ├── ReviewQueueTab (Evidence crop cards, deadline countdown ring, APPROVE confirm modal, EXPIRED->MONITOR)
│       └── SystemSelfCheckTab (GET /system/info proof, OpenCV 5, COOL NEON, G1-G5 thresholds)
├── ControlFooter
│   ├── START BELT / PAUSE (Space)
│   ├── MANUAL FIRE (M) (Popover confirm, G4 cooldown 400ms lock, result toast)
│   └── EMERGENCY KILL SWITCH (K) (Instant engagement, 1.5s radial hold reset + clearance checkbox)
├── FooterBar
│   ├── C1 Constraint Line: "Digital twin only. Zero physical GPIO/solenoids fired."
│   ├── WebSocket State & Sequence Number
│   ├── Last-Frame Age (ms)
│   └── Hidden Dev FPS Meter (?debug=1)
└── ShortcutsModal (Keyboard shortcut reference overlay - ?)
```

---

## 4. State Machine & Guardrail Architecture

### 4.1 Track 7-State Lifecycle
```
   ┌───────────────┐
   │  MONITORING   │ ◄────────────────────────┐
   └───────┬───────┘                          │
           │ target acquired                  │
           ▼                                  │
   ┌───────────────┐                          │
   │   TRACKING    │                          │
   └───────┬───────┘                          │
           │ Kalman converged                 │
           ▼                                  │
   ┌───────────────┐                          │
   │   ASSESSING   │                          │
   └───┬───────┬───┘                          │
       │       │ ambiguous                    │
       │       ▼                              │
       │   ┌─────────────────────┐            │
       │   │ GATHERING_EVIDENCE  │ (Tier 2)   │
       │   └──────────┬──────────┘            │
       │              │ Bedrock escalate      │
       │              ▼                       │
       │   ┌─────────────────────┐            │
       │   │   AWAITING_HUMAN    │ (HITL)     │
       │   └──────────┬──────────┘            │
       │              │ operator approved     │
       ▼              ▼                       │
   ┌─────────────────────┐                    │
   │    INTERCEPTING     │                    │
   └──────────┬──────────┘                    │
              │ simulated pulse               │
              ▼                               │
   ┌─────────────────────┐                    │
   │     VERIFYING       │ ───────────────────┘
   └─────────────────────┘ (deflection confirmed)
```

### 4.2 Guardrails (Veto Layer G1–G5)
1. **G1 (TTI Margin)**: $TTI \ge 230\text{ ms}$ ($\text{actuation\_delay } 80\text{ms} + \text{min\_margin } 150\text{ms}$).
2. **G2 (Jet Cone Alignment)**: Predicted $x$ coordinate at jet line within $260\text{ mm} - 340\text{ mm}$.
3. **G3 (Ambiguity Floor)**: Confidence $\ge 0.40$ for deterministic action.
4. **G4 (Cooldown Protection)**: Minimum $400\text{ ms}$ interval between firings.
5. **G5 (Emergency Kill Switch)**: Instant software interlock.
