from datetime import datetime
from enum import Enum
from pathlib import Path

import openai
from agents import Runner, RunResult, trace
from jinja2 import Template
from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth
from pydantic import BaseModel

from custom_agents.job_analyzer import job_analyzer_agent
from custom_agents.job_title_analyzer import job_title_analyzer_agent

html_path = Path(__file__).parent / "utils" / "run_summary.html"


class Type(str, Enum):
    APPLIED = "APPLIED"
    SAVED = "SAVED"


class RunSummarry(BaseModel):
    type: Type = Type.APPLIED
    job_title: str
    job_description: str
    job_link: str | None = None
    match: bool
    percentage: int
    reasoning: str
    matched_skills: list[str]
    missing_skills: list[str]


class BasePage:
    def __init__(self):
        self._playwright = None
        self._context = None
        self.page: Page | None = None
        self.search_keys: list = []
        self.run_summary: list[RunSummarry] = []

    async def handle_new_tab(self, new_tab):
        await Stealth().apply_stealth_async(new_tab)

    async def persistent_browser_login(
        self, page_link: str, profile: str = "PlaywrightProfile"
    ):
        self._playwright = await async_playwright().start()
        self.search_keys = [
            "Software Engineer",
            "Full stack developer",
            "Typescript",
            "React",
            "Node.js",
            "Python",
            "Laravel",
            "Software Developer",
            "AWS",
            "DevOps",
        ]
        user_data_dir = Path(
            rf"C:\Users\xtian\AppData\Local\BraveSoftware\Brave-Browser\{profile}"
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
            "ncs philippines",
            "yondu",
            "white cloak",
            "power mac",
            "lago",
            "ncs group",
            "mindrift",
            "hired",
            "amcs",
            "dataannotation",
            "data annotation",
            "pulsetheta",
            "globe telecom",
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

    def _skip_this_company(self, company_name: str) -> bool:
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
            "ncs philippines",
            "yondu",
            "white cloak",
            "power mac",
            "lago",
            "ncs group",
            "mindrift",
            "hired",
            "SYSGEN RPO",
            "cp health innovations",
            "hyremote",
            "webee labs",
            "webee",
        ]
        return any(
            company_name.lower() in company.lower() for company in companies_to_skip
        )

    def append_job(self, run_summary: RunSummarry):
        self.run_summary.append(run_summary)

    def generate_html_run_summary(self, page: str = "jobstreet"):
        template = Template(html_path.read_text(encoding="utf-8"))
        applied_jobs = [
            summary for summary in self.run_summary if summary.type == Type.APPLIED
        ]
        saved_jobs = [
            summary for summary in self.run_summary if summary.type == Type.SAVED
        ]
        average_match = (
            sum(summary.percentage for summary in self.run_summary)
            / len(self.run_summary)
            if self.run_summary
            else 0
        )

        output = template.render(
            total_jobs=len(self.run_summary),
            applied_count=len(applied_jobs),
            saved_count=len(saved_jobs),
            average_match=average_match,
            applied_jobs=applied_jobs,
            saved_jobs=saved_jobs,
        )
        timestamp_folder = datetime.now().strftime("%Y-%m-%d")  # noqa: DTZ005
        timestamp = datetime.now().strftime("%Y-%m-%d_%I-%M %p")  # noqa: DTZ005

        output_path = (
            Path("run_summaries")
            / f"{page}"
            / f"{timestamp_folder}"
            / f"{page}_run_summary_{timestamp}.html"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")

    async def evaluate_job_title(
        self,
        job_title: str,
        workflow_name: str = "Job Title Evaluation",
    ) -> RunResult | None:
        """Cheap, title-only pre-filter run before the full job evaluation.

        Returns None on failure so callers fail open (fall through to the
        full evaluation) instead of silently skipping a possibly good job.
        """
        result = None
        max_retries = 2
        with trace(workflow_name=workflow_name):
            for attempt in range(max_retries + 1):
                try:
                    result = await Runner.run(
                        starting_agent=job_title_analyzer_agent,
                        input=f"Job Title: {job_title}",
                        max_turns=3,
                    )
                    break
                except openai.BadRequestError as e:
                    result = None
                    if "json_validate_failed" in str(e) and attempt < max_retries:
                        print(
                            f"JSON validation failed for title '{job_title}'. Retrying ({attempt + 1}/{max_retries})..."
                        )
                        continue
                    print("Error occured job title:", job_title)
                    print("Error", e)
                except KeyError as ke:
                    result = None
                    print(f"Missing key error {ke}")
                    break
        return result

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
