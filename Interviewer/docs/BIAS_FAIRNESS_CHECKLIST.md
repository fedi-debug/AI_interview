# Bias & Fairness Checklist

## Before pilot

- [ ] Document known limitations of gaze estimation on glasses, dark skin tones, low light.
- [ ] Document prosody bias for non-native accents.
- [ ] Disable or down-weight features with high subgroup variance (pilot analysis).

## Face / gaze (MediaPipe)

- [ ] Test gaze_away false positives with glasses and asymmetrical lighting.
- [ ] Do not penalize disability-related gaze or head movement patterns without human override.
- [ ] Cap nonverbal weight at 15% (configurable downward).

## Prosody (openSMILE / librosa)

- [ ] Compare pitch/jitter distributions across accent groups in pilot.
- [ ] Avoid single "ideal" pitch range; use z-score within session baseline when possible (future).

## ASR (whisper.cpp)

- [ ] Use `base` or `small` multilingual model if non-English candidates.
- [ ] Report ASR confidence; low confidence → flag for human review, not auto-fail.

## MCQ generation (LLM)

- [ ] Human spot-check 20% of generated questions for stereotyping.
- [ ] Block deployment of questions with discriminatory content (manual review gate).

## Reporting

- [ ] Include disclaimer on every `report.final`.
- [ ] Show feature breakdown to candidate on request (transparency).

## Ongoing

- [ ] Quarterly re-check with diverse volunteer panel.
- [ ] Log appeals and adjust weights/thresholds.
