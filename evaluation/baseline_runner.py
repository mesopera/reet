"""
Runs baseline conditions (no_automation and rule_based).
These use fixed MTTD/MTTR values based on literature.
"""
from fault_injection.scenario_runner import run_all


def run_no_automation(output_csv: str, reps: int = 5):
    """
    No automation baseline.
    Human detection ~15 min, resolution ~60 min for software faults.
    """
    run_all('no_automation', output_csv, reps)


def run_rule_based(output_csv: str, reps: int = 5):
    """
    Rule-based baseline.
    Threshold detection ~2 min, scripted fix ~5 min.
    """
    run_all('rule_based', output_csv, reps)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--condition',
                        choices=['no_automation', 'rule_based'],
                        required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--reps', type=int, default=5)
    args = parser.parse_args()

    if args.condition == 'no_automation':
        run_no_automation(args.output, args.reps)
    else:
        run_rule_based(args.output, args.reps)