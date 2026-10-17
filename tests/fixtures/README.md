# Synthetic fixtures

`chatgpt-branches.json` is artificial test material, not a real account export. It contains one user node and two child branches, one assistant and one tool response. It verifies preservation of IDs, roles, branches, and an old source timestamp. A local UI smoke test imported it through a clearly labeled test profile; that folder watch was paused afterward.

Additional synthetic exports are constructed in `tests/test_imports_automation.py`. No private account records are included.
