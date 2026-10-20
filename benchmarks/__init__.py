"""ZoneShield AI Benchmarking Suite.

Implements the Master Spec 3-way evaluation:
- B1: Stock OpenCV 5 on x86 (c7i baseline)
- B2: Stock OpenCV 5 on Graviton (c7g baseline)
- B3: COOL on Graviton (c7g with Arm NEON & KleidiCV/COOL acceleration)
"""
