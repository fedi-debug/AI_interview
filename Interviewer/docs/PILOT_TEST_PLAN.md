# HireNest Pilot Test Plan

## Objectives

1. Validate MCQ generation quality for 3 job profiles.
2. Measure automated interview score vs human rater agreement.
3. Tune fusion weights and gaze/VAD thresholds on GTX 1650 hardware.
4. Document bias/fairness findings.

## Participants

- **N = 10** internal volunteers (not final hiring candidates).
- Mix of gender, accent, and skin tone for fairness sampling.
- Signed consent form mirroring in-app consent screen.

## Protocol (per participant, ~45 min)

| Phase | Duration | Steps |
|-------|----------|-------|
| Setup | 5 min | Run `setup_windows.ps1`, confirm mock/real ASR |
| MCQ | 15 min | `POST /mcq/generate`, complete 20 Q, submit |
| Interview | 20 min | React UI, 5 scripted answers + free response |
| Debrief | 5 min | Human rater scores 1–100 independently |

## Human rater rubric

| Dimension | Weight | Criteria |
|-----------|--------|----------|
| Content | 50% | Technical accuracy, completeness |
| Fluency | 20% | Pace, fillers, clarity |
| Prosody | 15% | Engagement, stress patterns |
| Nonverbal | 15% | Eye contact, posture |

## Metrics

- **Pearson r** between `final_score` and human overall.
- **MAE** per dimension (target MAE < 12 after tuning).
- **Latency**: ASR segment < 3s, frame processing < 200ms.
- **GPU VRAM peak** (Task Manager / `nvidia-smi`).

## Tuning checklist

- [ ] Adjust `SCORE_WEIGHTS_*` in `.env`
- [ ] Gaze away threshold (default 0.5s)
- [ ] VAD aggressiveness (0–3)
- [ ] Whisper model: base vs small
- [ ] Video FPS: 5 vs 8

## Acceptance criteria

- MCQ JSON valid ≥ 95% of generations (manual review).
- WebSocket session completes without crash for 10/10 users.
- r ≥ 0.65 overall after weight tuning (pilot target).
- No participant PII leaves local machine.

## Reporting template

```
Participant ID: P##
Job profile: 
MCQ score: 
Automated final: 
Human final: 
Delta: 
Notes (accent/lighting): 
Appeal/human review flag: Y/N
```

## Post-pilot

1. Update weights in `config.py` defaults from median-best run.
2. File issues for false gaze-away positives.
3. Schedule ethics review per `docs/SAFETY_ETHICS.md`.
