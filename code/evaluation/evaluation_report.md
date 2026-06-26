# Operational Analysis

## Local validation

The workflow uses `dataset/sample_claims.csv` for validation:

```powershell
python code/claim_agent.py --input dataset/sample_claims.csv --image-root dataset --user-history dataset/user_history.csv --evidence-requirements dataset/evidence_requirements.csv --output evaluation/sample_predictions.csv
python code/evaluate.py --expected dataset/sample_claims.csv --predicted evaluation/sample_predictions.csv
```

In this local workspace, the extracted archive did not include `dataset/images/`, `user_history.csv`, or `evidence_requirements.csv`, so the offline run correctly marks missing image evidence as `not_enough_information`.

## Model calls

The agent runs without model calls by default when `OPENAI_API_KEY` is not set. In VLM mode, it makes one vision model call per claim row with at least one readable image, batching up to four images for that claim into a single request.

- Sample processing: approximately one call per labelled sample row with readable images.
- Test processing: approximately one call per `dataset/claims.csv` row with readable images.
- Local extracted file: 0 calls, because no referenced images are present.

## Token and Image Usage

Each VLM call includes the claim conversation, object type, compact instructions, and up to four images.

Approximate per-claim text usage:

- Input text: 250 to 700 tokens, depending on conversation length.
- Output JSON: 80 to 180 tokens.
- Image input: provider-specific image token accounting; use the configured model's image pricing for exact cost.

The number of images processed is the count of readable image paths across the input CSV, capped at four images per claim for model review.

## Cost Assumptions

With `CLAIM_VLM_MODEL=gpt-4o-mini`, estimate cost as:

```text
total_cost ~= text_input_tokens * input_price
            + image_tokens * image_input_price
            + output_tokens * output_price
```

For a small test file with tens of rows and one to three images per row, expected cost should usually remain low. The offline fallback is free but cannot visually verify damage.

## Runtime and Latency

Offline parsing and image validation should run in seconds for small CSVs. VLM mode latency is approximately one network round trip per claim, often several seconds per row depending on image size and provider load.

## Rate Limits and Reliability

The implementation uses one call per claim rather than one call per image to reduce RPM usage. A production version should add:

- response caching keyed by image file hash plus claim text
- bounded retries for transient model errors
- throttling based on configured RPM/TPM limits
- batch scheduling for large test sets
- manual review routing when images are missing, unreadable, or model output is malformed
