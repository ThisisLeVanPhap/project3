# Evaluation dataset notes

- Dataset size: 48 Vietnamese questions in `dataset.jsonl`
- Format unchanged: each line keeps `question` and `ground_truth`
- Ground truth style: short keyword or source/title fragments, not exact full URLs

Category coverage:

- Product recommendation: 6
- Small apartment / room-size scenarios: 6
- Material / style questions: 6
- Payment policy: 6
- Delivery policy: 6
- Return policy: 6
- Warranty: 6
- Company / general info: 6

The set is intentionally intermediate-sized: large enough to make Recall@k and MRR comparisons more credible, but still small enough to review and evolve manually as the KB changes.
