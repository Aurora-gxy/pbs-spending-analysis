# Spot-check of the LLM judge

Four answers the judge marked down (held-out test set, Haiku 5.5). Each claim was checked by
re-running SQL on the data. The number check (`run_eval.py`) passed all four.

| Answer | Judge's claim | Checked against the data | Judge right? |
|---|---|---|---|
| v2 Q107 "Is heart medication spending going up?" | YoY growth is wrong: FY2024 should be +5.1%, not +2.1%; FY2025 +2.1%, not +2.0% | Group C total cost: FY2023 A$2.187B, FY2024 A$2.299B (+5.1%), FY2025 A$2.346B (+2.1%), FY2026 A$2.424B (+3.3%) | Yes. The first-line total (+10.9%) was correct, so the number check passed |
| v2 Q105 抗癌药的处方量占比 | First line swaps numerator and denominator | Answer reads "6.83M 张处方中的 338.97M 张中的一部分"; it should be 6.83M of 338.97M | Yes (garbled wording; the 2.0% is correct) |
| v1 Q110 优惠患者处方占比 | Says every year is 58–59%, but FY2023 is 59.2% | Concessional share: FY2023 59.2%, FY2024 58.7%, FY2025 58.8%, FY2026 58.2% | Yes (minor) |
| v1 Q103 前 10 种药占比 | "前三名依次为" lists only two drugs | Answer lists the 2nd and 3rd drugs after naming the 1st separately | Yes (wording) |

Result: 4 of 4 judge claims confirmed. This is a small check, not a full validation of the judge.
