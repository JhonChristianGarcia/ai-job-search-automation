import asyncio

from agents import Agent, ModelSettings, Runner

# from tools.emailer import send_email
from agents.extensions.models.litellm_model import LitellmModel
from pydantic import BaseModel

from context.context import title_prompt

GPT_MODEL = "gpt-4o-mini"

macbook_pro_qwen_3_5_9b_model = LitellmModel(
    model="lm_studio/qwen3.5-9b-instruct-pure",
    api_key="qwen3.5-9b-instruct-pure",
    base_url="http://192.168.0.154:1234/v1",
)


class AgentOutput(BaseModel):
    match: bool
    reasoning: str


job_title_analyzer_agent = Agent(
    name="Job Title Analyzer Agent",
    instructions=title_prompt(),
    model=macbook_pro_qwen_3_5_9b_model,
    output_type=AgentOutput,
    model_settings=ModelSettings(
        include_usage=True,
        timeout=10_000,
        temperature=0.0,
        extra_body={
            "enable_thinking": False,
        },
    ),
)


async def test_model():
    for title in (
        "Tax Assistant Manager",
        "Service Now Developer",
        "Crypto Operations Associate",
        "Senior Full Stack Developer",
        "Platform Engineer",
    ):
        result = await Runner.run(job_title_analyzer_agent, f"Job Title: {title}")
        print(title, "->", result.final_output)


if __name__ == "__main__":
    asyncio.run(test_model())
