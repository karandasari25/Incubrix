# Performance Benchmarks

## 1. Catalogue Import Benchmark (1,000 rows)

- **Target**: 1,000 rows in < 300 seconds (5 minutes)
- **Measured time**: 0.086s
- **Throughput**: 11633.52 rows/sec
- **Imported**: 950
- **Duplicates detected**: 30
- **Bad rows rejected**: 20
- **Status**: PASSED

## 2. Recommender Evaluation (Precision@10)

- **Dataset**: `data\labelled\recommender_eval.json`
- **Dataset Status**: `draft_needs_human_review`
- **Test Samples**: 20 content items
- **Mean Precision@10**: 0.285
- **Audit Status**: Subject to final human label review per assessment rules.
