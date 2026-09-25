import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_groq import ChatGroq

from schemas import Action, Diagnosis
from prompts import SYSTEM

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
RUNS_PER_FIXTURE = 5


def load_fixtures() -> list[dict]:
    fixtures = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        fixtures.append({"expected": Action(data["expected_action"]), "text": data["text"]})
    return fixtures


def main() -> None:
    llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0, api_key=os.environ["GROQ_API_KEY"])
    structured = llm.with_structured_output(Diagnosis)
    fixtures = load_fixtures()

    total = valid = correct = 0
    latencies: list[float] = []

    for fx in fixtures:
        for _ in range(RUNS_PER_FIXTURE):
            total += 1
            start = time.time()
            try:
                result = structured.invoke([("system", SYSTEM), ("human", fx["text"])])
                latencies.append(time.time() - start)
                valid += 1
                if result.proposed_action == fx["expected"]:
                    correct += 1
                else:
                    print(f"MISMATCH expected={fx['expected'].value} got={result.proposed_action.value}")
            except Exception as exc:
                print(f"INVALID OUTPUT: {type(exc).__name__}: {str(exc)[:200]}")
            time.sleep(2)

    avg = sum(latencies) / len(latencies) if latencies else 0
    print(f"\nTotal calls:        {total}")
    print(f"Valid schema:       {valid}/{total}")
    print(f"Correct action:     {correct}/{total}")
    print(f"Avg latency (s):    {avg:.2f}")


if __name__ == "__main__":
    main()
