# Retrieval benchmark summary

- Dataset: `chatbot\eval\dataset.jsonl`
- Dataset size: 48
- KB dir: `chatbot\kb\noithatcaco`
- Top-k: 5

## Category coverage

- Product recommendation: 6
- Small apartment / room-size scenarios: 6
- Material / style questions: 6
- Payment policy: 6
- Delivery policy: 6
- Return policy: 6
- Warranty: 6
- Company / general info: 6

## Metrics

| Mode | Recall@5 | MRR |
| --- | ---: | ---: |
| keyword | 0.7917 | 0.7333 |
| vector | 0.6667 | 0.4639 |
| hybrid | 0.7917 | 0.6708 |
| hybrid_rerank | 0.7708 | 0.6285 |

## Interpretation

- Keyword is strongest on the current 48-question Vietnamese dataset.
- Vector, hybrid, and hybrid_rerank did not outperform the tuned keyword baseline on Recall@5 and MRR.

## Reproducible command

```bash
python chatbot/eval/runner.py --dataset chatbot\eval\dataset.jsonl --kb-dir chatbot\kb\noithatcaco --top-k 5 --compare
```
