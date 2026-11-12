from agent_reliability_lab.cli import demo

if __name__ == "__main__":
    raise SystemExit(demo("reports/demo.json", inject_fault=True))
