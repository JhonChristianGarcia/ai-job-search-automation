from pathlib import Path

import openai
from agents import Runner, RunResult, trace
from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth

from custom_agents.job_analyzer import job_analyzer_agent


class BasePage:
    def __init__(self):
        self._playwright = None
        self._context = None
        self.page: Page | None = None

    async def handle_new_tab(self, new_tab):
        await Stealth().apply_stealth_async(new_tab)

    async def persistent_browser_login(self, page_link: str):
        self._playwright = await async_playwright().start()

        user_data_dir = Path(
            r"C:\Users\xtian\AppData\Local\BraveSoftware\Brave-Browser\PlaywrightProfile"
        )

        executable_path = (
            r"C:\Program Files\BraveSoftware"
            r"\Brave-Browser\Application\brave.exe"
        )

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            executable_path=executable_path,
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        self._context.on("page", self.handle_new_tab)

        new_tab = await self._context.new_page()

        for page in list(self._context.pages):
            if page != new_tab:
                await page.close()

        self.page = await self._context.new_page()
        await new_tab.close()

        # APPLING STEALTH
        await Stealth().apply_stealth_async(self.page)

        await self.page.goto(page_link)
        await self.page.wait_for_timeout(1500)

    def _skip_this_job(self, job_description: str) -> bool:
        keywords_to_skip = [
            "intern",
            "internship",
            "java",
            "c#",
            ".net",
            "ruby",
            "perl",
            "scala",
            "rust",
            "principal",
            "salesforce developer",
            "wordpress",
            "powerapps",
            "Kotlin",
            "Swift",
            "Objective-C",
            "Elixir",
            "Erlang",
            "Groovy",
            "COBOL",
            "ABAP",
            "Salesforce",
            "ServiceNow",
            "Service Now",
            "QA Engineer",
            "QA Tester",
            "Manual Tester",
            "Test Engineer",
            "Data Analyst",
            "Data Engineer",
            "Business Analyst",
            "Data Scientist",
            "Network Engineer",
            "Network Administrator",
            "System Administrator",
            "IT Support",
            "Technical Support",
            "Help Desk",
        ]

        companies_to_skip = [
            "eclaro",
            "hire feed",
            "quik hire staffing",
            "microsourcing",
            "hunt st",
            "crossing hurdles",
            "crossover",
            "micro1",
            "bjak",
            "ncswhite cloak",
            "power mac",
        ]

        description = job_description.lower()

        return any(
            keyword.lower() in description for keyword in keywords_to_skip
        ) or any(company.lower() in description for company in companies_to_skip)

    async def wait_for_timeout(self, duration: int = 1):
        """Wait for network idle
        :param duration: Integer in seconds
        """

        await self.page.wait_for_timeout(duration * 1000)

    async def evaluate_job(
        self,
        job_title: str,
        job_description: str,
        workflow_name: str = "Jobstreet Job Evaluation",
    ) -> RunResult | None:
        job_input = f"""Job Title: {job_title} \n
                        Job Description: \n {job_description}
                    """
        result = None
        max_retries = 2
        with trace(workflow_name=workflow_name):
            for attempt in range(max_retries + 1):
                try:
                    result = await Runner.run(
                        starting_agent=job_analyzer_agent,
                        input=job_input,
                        max_turns=5,
                    )
                    break
                except openai.BadRequestError as e:
                    result = None
                    if "json_validate_failed" in str(e) and attempt < max_retries:
                        print(
                            f"JSON validation failed for '{job_title}'. Retrying ({attempt + 1}/{max_retries})..."
                        )
                        continue
                    print("Error occured job title:", job_title)
                    print("Error", e)
                except KeyError as ke:
                    result = None
                    print(f"Missing key error {ke}")
                    break
        return result

    async def _clean_up(self):
        if self._context:
            await self._context.close()

        if self._playwright:
            await self._playwright.stop()
