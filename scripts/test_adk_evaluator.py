import asyncio
from google.adk.evaluation import AgentEvaluator
from google.adk.evaluation.eval_set import EvalSet

async def main():
    eval_set = EvalSet.from_file("tests/adk_evals/cfo_copilot.evalset.json")
    print("Loaded eval_set cases:", len(eval_set.eval_cases))
    evaluator = AgentEvaluator()
    try:
        # evaluate() on evaluator
        res = await evaluator.evaluate_async(
            agent_module_path="app.agents.root_agent",
            eval_set=eval_set,
        )
        print("Result:", res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
