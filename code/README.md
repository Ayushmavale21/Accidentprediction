# Multi-Modal Evidence Review

This submission reads the challenge CSV, resolves the submitted image paths, extracts the actual damage claim from the conversation, and emits `output.csv` with the exact required schema.

## Approach

- The conversation is parsed for object part and damage type using object-specific vocabularies for cars, laptops, and packages.
- Images are treated as the primary evidence. The agent checks that every referenced image exists, is readable, and has basic quality.
- If `OPENAI_API_KEY` is available, the agent sends the readable images plus the extracted claim to a vision-capable model and uses the visual result for support, contradiction, sufficiency, severity, and supporting image IDs.
- If no vision model is configured, the agent does not fabricate image findings. It marks the case as `insufficient` unless direct visual verification is available.
- User history columns, if present, only add risk flags. They never override clear image evidence.

## Run

```powershell
python code/claim_agent.py --input dataset/claims.csv --image-root dataset --user-history dataset/user_history.csv --evidence-requirements dataset/evidence_requirements.csv --output output.csv
```

For the extracted local files in this workspace:

```powershell
python code/claim_agent.py --input challenge_data/claims.csv --image-root challenge_data --output output.csv
```

Optional VLM mode:

```powershell
$env:OPENAI_API_KEY="..."
$env:CLAIM_VLM_MODEL="gpt-4o-mini"
python code/claim_agent.py --input dataset/claims.csv --image-root dataset --user-history dataset/user_history.csv --evidence-requirements dataset/evidence_requirements.csv --output output.csv
```

## Evaluation Workflow

Run predictions on labelled sample rows, then compare to the provided expected fields:

```powershell
python code/claim_agent.py --input dataset/sample_claims.csv --image-root dataset --user-history dataset/user_history.csv --evidence-requirements dataset/evidence_requirements.csv --output code/evaluation/sample_predictions.csv
python code/evaluate.py --expected dataset/sample_claims.csv --predicted code/evaluation/sample_predictions.csv
```

For this workspace's partial extracted CSV-only archive:

```powershell
python code/claim_agent.py --input challenge_data/sample_claims.csv --image-root challenge_data --output challenge_data/sample_predictions.csv
python code/evaluate.py --expected challenge_data/sample_claims.csv --predicted challenge_data/sample_predictions.csv
```

The evaluator reports exact row match and per-column agreement for the key decision fields.

## Packaging

Zip only the `code/` directory for the code submission. Do not include virtual environments, build artifacts, `data/`, `dataset/`, or the image corpus.
