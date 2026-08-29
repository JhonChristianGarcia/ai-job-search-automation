from agents import Agent
# from context import prompt
# from tools.emailer import send_email

MODEL="gpt-4o-mini"

chat_agent = Agent(
    name="Job Analyzer Agent",
    # instructions=prompt(),
    model=MODEL,
    # tools=[send_email]
)
