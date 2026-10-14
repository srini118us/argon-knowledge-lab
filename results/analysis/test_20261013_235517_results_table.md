# Results table: test_20261013_235517

| Arm | Model | Accuracy | Total cost | Cost per question | Mean latency (s) | Median latency (s) | Mean input tokens | Mean output tokens | Mean thought tokens | Cached tokens (total) | Share of input cached | Mean tool calls |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | gemini-3.8-flash | 48/50 | $0.23 | $0.0046 | 20.1 | 18.9 | 2,889 | 205 | 456 | 325 | 0% | 5.3 |
| A | gemini-4-argon | 49/50 | $1.34 | $0.0268 | 23.9 | 18.8 | 16,325 | 229 | 161 | 256,559 | 31% | 5.4 |
| L | gemini-3.8-flash | 50/50 | $0.71 | $0.0142 | 6.6 | 5.9 | 45,633 | 71 | 390 | 1,614,299 | 71% | 0.0 |
| L | gemini-4-argon | 50/50 | $4.56 | $0.0911 | 9.2 | 7.1 | 45,556 | 95 | 73 | 44,075 | 2% | 0.0 |
| R1 | gemini-3.8-flash | 41/50 | $0.25 | $0.0050 | 5.0 | 4.8 | 4,789 | 73 | 303 | 0 | 0% | 0.0 |
| R1 | gemini-4-argon | 41/50 | $0.56 | $0.0111 | 6.0 | 4.9 | 4,922 | 101 | 26 | 0 | 0% | 0.0 |
| R2 | gemini-3.8-flash | 46/50 | $0.25 | $0.0049 | 6.1 | 5.1 | 4,782 | 73 | 290 | 2,531 | 1% | 0.0 |
| R2 | gemini-4-argon | 46/50 | $0.43 | $0.0085 | 12.7 | 4.7 | 4,913 | 104 | 20 | 66,483 | 27% | 0.0 |
