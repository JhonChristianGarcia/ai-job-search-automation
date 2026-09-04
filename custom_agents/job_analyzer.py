from agents import Agent, ModelSettings, Runner, OpenAIChatCompletionsModel
from openai.types.shared import Reasoning
from context.context import prompt
from pydantic import BaseModel
import os
# from tools.emailer import send_email
from agents.extensions.models.litellm_model import LitellmModel
import asyncio
from openai import AsyncOpenAI, OpenAI

GPT_MODEL = "gpt-4o-mini"
groq_client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY"),
)

groq_model = OpenAIChatCompletionsModel(
    model="openai/gpt-oss-120b",
    openai_client=groq_client,
)

qwen_lite_llm_model = LitellmModel(
    model="huggingface/zai-org/GLM-5.3-Flash:baseten",
    api_key=os.environ["HF_TOKEN"],
    # base_url="https://router.huggingface.co/v1"
)

local_qwen_llm_model = LitellmModel(
    model="lm_studio/qwen/qwen3-4b-2507",
    api_key="lm-studio",
    base_url="http://127.0.0.1:1234/v1"
)

local_qwen_llm_model_3b = LitellmModel(
    model="lm_studio/qwen2.5-3b-instruct",
    api_key="lm-studio",
    base_url="http://127.0.0.1:1234/v1"
)

open_router_client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPEN_ROUTER_API_KEY"]
)

open_router_model = OpenAIChatCompletionsModel(
    model="nvidia/nemotron-3.5-lightning:free",
    openai_client=open_router_client
)

macbook_pro_qwen_3_5_9b_model = LitellmModel(
    model="lm_studio/qwen3.5-9b-instruct-pure",
    api_key="qwen3.5-9b-instruct-pure",
    base_url="http://192.168.0.154:1234/v1",
)
class AgentOutput(BaseModel):
    match: bool
    percentage: int
    reasoning: str
    matched_skills: list[str]
    missing_skills: list[str]

    
job_analyzer_agent = Agent(
    name="Job Analyzer Agent", 
    instructions=prompt(),
    model=macbook_pro_qwen_3_5_9b_model,
    output_type=AgentOutput,
    model_settings=ModelSettings(
        include_usage=True,
        timeout=10_000,
        temperature=0.0,
        extra_body={
            "enable_thinking": False,
        }
    ),
    
    # tools=[send_email]
)
async def test_model():
    result = await Runner.run(job_analyzer_agent, """Job Description
If you are looking to join an Australian Telco company recognized as Australia’s most trusted Telco that upholds value and focus on continuously delivering excellent results and customer experience, then this is for you!

The Opportunity

Join a fast-moving engineering team where you’ll build end-to-end solutions across internal tools, SDKs, apps, and customer portals—leveraging modern technologies and industry best practices. If you’re passionate about modernizing legacy systems and driving transformation, this is where your expertise will shine.

Why join us?

Proudly Great Place to Work® certified
Celebrate globally: Company trips (2025: Hong Kong, 2024: Thailand), Culture Champs, Year-end parties, leadership awards & more
Grow with stability: 100+ in our 10-Year Club by 2025
Dynamic talent network: 2,000+ across APAC and beyond
Competitive compensation with annual reviews
Comprehensive medical care for you and your family
Generous paid leave because work-life balance matters
Level up with LinkedIn Learning and tailored training
Flexible work setup
Staff Testimonial

“I’m proud to be part of a team where our work supports hundreds of thousands of Australians with reliable connectivity every day — and where quality service and customer trust truly matter.” – Delivery Lead, ASW Philippines.

What You'll Do

Building end-to-end solutions across a variety of channels (including internal tools, SDK apps and customer-facing portals), shaping the direction of our architecture, design patterns and stack.
Utilize industry best practices and leveraging the latest technologies where possible.
Engage with stakeholders in all stages of the software development life cycle.
Write clean, maintainable code, following best practices and adhering to coding standards.
Work on special projects as directed by the Software Engineering Manager.
Drive automation of business processes to improve efficiency and operational effectiveness.
Assist in the migration and modernization of legacy systems to new platforms.
Key Criteria

At least 3 years + of experience as a Software Engineer or similar roles.
Strong experience with a proven track record using at least 2 of these stacks: PHP, Javascript, and Python
Experience crafting and maintaining software with a test-driven approach that is maintainable and conforms to standards and software development best practices.
Familiarity with Agile/Scrum methodology.
Ideally from a Telco background or similar but not mandatory.
Excellent communication skills, especially when identifying the requirements and delivering what was required.
Work setup:

Manila (BGC, Taguig): Australian hours (6:00am–3:00pm PHT) with a flexible work arrangement.
#LI-ME1""")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(test_model())