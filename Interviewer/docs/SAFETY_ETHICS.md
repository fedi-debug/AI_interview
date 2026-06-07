# HireNest Safety & Ethics

## Hiring decisions

**Never use the automated score as the sole basis for hiring.** HireNest outputs are decision-support only.

## Transparency (show candidates)

- What is recorded: microphone audio, camera video.
- Where processing happens: locally on the interview machine (no cloud).
- What is measured: transcript, speech fluency, voice prosody, gaze/face metrics.
- How the score is computed: weighted fusion (content 50%, fluency 20%, prosody 15%, nonverbal 15%).
- Retention: data stored in local SQLite; delete on request.

## Human review & appeal

1. Every report includes `human_review_required: true`.
2. Recruiter reviews transcript + feature breakdown before sharing with hiring manager.
3. Candidate may request re-interview or manual review within 5 business days.
4. Appeal outcome logged outside HireNest (HRIS).

## Privacy

- Minimal PII: optional `candidate_id`, no SSN/address in DB.
- Consent checkbox required (`POST /interview/start` with `consent: true`).
- All artifacts remain on local disk under `hirenest/data/`.

## Bias & fairness

See `docs/BIAS_FAIRNESS_CHECKLIST.md`. Monitor score gaps across demographic pilot subgroups.
