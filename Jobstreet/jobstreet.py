import re
from pathlib import Path
import asyncio
from playwright.async_api import async_playwright, Page, expect, Locator
from agents import Runner, trace
from dotenv import load_dotenv
from custom_agents.job_analyzer import job_analyzer_agent
from custom_agents.form_fields_extractor import fields_extractor_agent
from custom_agents.form_evaluator import form_evaluator
from pydantic import BaseModel
from pprint import pprint
load_dotenv(override=True)
import json
import openai
from utils.salary_in_range import salary_in_range
JOBSTREET_LINK = "https://ph.jobstreet.com/"

class RunSummarry(BaseModel):
    job_title: str
    job_description: str
    match: bool
    percentage: int
    reasoning: str
    matched_skills: list[str]
    missing_skills: list[str]
class Jobstreet:
    
    def __init__(self):
        self._playwright = None
        self._context = None
        self.page: Page | None = None

        #Page elements
        self.search: Locator | None = None
        self.seek_btn: Locator | None = None
        self.work_arrangement: Locator | None = None
        self.remote_option: Locator | None = None
        self.listing_time: Locator | None = None
        self.last_3_days_option: Locator | None = None
        self.run_summary: list[RunSummarry] = []
        
    async def _persistent_browser_login(self):
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
        )

        new_tab = await self._context.new_page()

        for page in list(self._context.pages):
            if page != new_tab:
                await page.close()
            
        self.page = await self._context.new_page()
        await new_tab.close()
        await self.page.goto(JOBSTREET_LINK)

    async def _wait_for_timeout(self, duration: int = 1):
        """Wait for network idle
        :param duration: Integer in seconds
        """
        await self.page.wait_for_load_state('networkidle')
        await self.page.wait_for_timeout(duration * 1000)

    async def _click_outside_modal(self):
        await self.page.locator("body").click(position={"x": 10, "y": 10})


    
    async def _search_and_filter_jobs(self, remote_only: bool = True, keyword: str = "Software Engineer") -> list[Locator]:
        self.search = self.page.locator("#keywords-input")
        await self.search.type(keyword, delay=50)

        self.seek_btn = self.page.get_by_role("button", name="Submit search")
        await expect(self.seek_btn).to_be_visible()
        await self.seek_btn.click()

        await self._wait_for_timeout()

        if remote_only:
            self.work_arrangement = self.page.locator("div").filter(has_text=re.compile(r"^RemoteRemote$")).nth(1)
            await expect(self.work_arrangement).to_be_visible()
            await self.work_arrangement.click()
            self.remote_option = self.page.get_by_role("checkbox", name="Remote")
            await expect(self.remote_option).to_be_visible()
            await self.remote_option.click()
            await self._wait_for_timeout()
            await self._click_outside_modal()

        self.listing_time = self.page.get_by_text("Show date listed refinements.Listing time").nth(1)
        await expect(self.listing_time).to_be_visible()
        await self.listing_time.click()

        self.last_3_days_option = self.page.get_by_role("radio", name="Last 3 days")
        await expect(self.last_3_days_option).to_be_visible()
        await self.last_3_days_option.click()
        await self._click_outside_modal()    
        await self._wait_for_timeout()
        
        # jobs = self.page.get_by_test_id("job-list-item-link-overlay")
        
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
            ]

            description = job_description.lower()

            return (
                any(keyword.lower() in description for keyword in keywords_to_skip)
                or any(company.lower() in description for company in companies_to_skip)
            )

    
    async def automate_job_search(self):
        await self._persistent_browser_login()
        
        await self._search_and_filter_jobs(keyword="Python", remote_only=False)
        has_next_page = await self.page.get_by_role("link", name="Next").count() > 0
        while has_next_page:
            jobs = await self.page.get_by_test_id("job-card").all()
            total_jobs = await self.page.get_by_test_id("job-card").count()
            if total_jobs == 0:
                print("No jobs found")
                break
            print(f"Found {total_jobs} jobs on this page")
            for i, job in enumerate(jobs, start=1):
                job_card_content = await job.inner_text()
                skip_job = self._skip_this_job(job_description=job_card_content)
                salary_locator = job.locator('[data-automation="jobSalary"]').first
                job_salary = await salary_locator.inner_text() if await salary_locator.count() else ""
                
                job_listing_date = await job.locator('[data-automation="jobListingDate"]').nth(0).inner_text()
                already_applied = "Applied" in job_listing_date
                already_saved = (await job.locator('[data-automation="remove-save-job"]').count()) > 0
                viewed = "Viewed" in job_listing_date
                if already_applied or viewed or skip_job or already_saved or not salary_in_range(job_salary):
                    continue
                
                await job.click()
                await self._wait_for_timeout()
                
                job_details_section = self.page.locator('[data-automation="jobDetailsPage"]').nth(0)
                await expect(job_details_section).to_be_visible()
                salary_range_element = job_details_section.locator('[data-automation="job-detail-salary"]')
                salary_range_inside_job_details = await salary_range_element.inner_text() if await salary_range_element.count() else ""
                if not salary_in_range(salary_range_inside_job_details):
                    continue
                quick_apply_btn = job_details_section.locator('[data-automation="job-detail-apply"]', has_text=re.compile(r"quick apply", re.I)).nth(0)
                external_apply_btn = job_details_section.locator('[data-automation="job-detail-apply"]', has_text=re.compile(r"apply", re.I)).nth(0)

                save_btn = job_details_section.get_by_test_id("jdv-savedjob").nth(0)

                if await quick_apply_btn.count() == 0 and await save_btn.count() == 0:
                    print(f"Job has no quick apply or save button. Skipping.")
                    continue
                job_title_element = job_details_section.get_by_role("link").nth(0)
                if(not await job_title_element.inner_text()):
                    job_title_element = job_details_section.get_by_role("link").nth(1)
                job_description_section = job_details_section.locator('[data-automation="jobAdDetails"]')
                
                job_title = await job_title_element.inner_text()
                job_description = await job_description_section.inner_text()
                
                job_input = f"""Job Title: {job_title} \n
                Job Description: \n {job_description}
                """

                already_saved = (await save_btn.inner_text()) == "Unsave"
                if(already_saved):
                    continue

                result = None
                max_retries = 2
                with trace(workflow_name="Job Search Automation"):
                    for attempt in range(max_retries + 1):
                        try:
                            result = await Runner.run(starting_agent=job_analyzer_agent, input=job_input, max_turns=5)
                            break
                        except openai.BadRequestError as e:
                            result = None
                            if "json_validate_failed" in str(e) and attempt < max_retries:
                                print(f"JSON validation failed for '{job_title}'. Retrying ({attempt + 1}/{max_retries})...")
                                continue
                            print("Error occured job title:", job_title)
                            print("Error", e)
                        except KeyError as ke:
                            result = None
                            print(f"Missing key error {ke}")
                            break
                        except Exception as e:
                            result = None
                            print("Error occured job title:", job_title)
                            print("Error", e)
                            break

                if result is None:
                    continue
                
                await self._wait_for_timeout()

                
                run_result = result.final_output.model_dump()
                has_quick_apply_btn = await quick_apply_btn.count() > 0
                # Save if not quick apply for now
                if not has_quick_apply_btn and run_result.get("match") is True and not already_saved:
                    await save_btn.click()
                    continue
                if has_quick_apply_btn and run_result.get("match") is True:
                    async with self.page.context.expect_page() as new_page:
                        await quick_apply_btn.click()
                    new_tab = await new_page.value
                    await new_tab.wait_for_load_state("domcontentloaded")
                    dont_include_a_cover_letter = new_tab.locator("label").filter(has_text="Don't include a cover letter")
                    await dont_include_a_cover_letter.click()
                    continue_btn = new_tab.get_by_test_id("continue-button")
                    
                    while await continue_btn.count() > 0:
                        await continue_btn.nth(0).click()
                        print("Clicked continue button")
                        await new_tab.wait_for_timeout(1000)
                        error_panel = new_tab.locator("#errorPanel")
                        has_errors = await error_panel.count() > 0
                        errors = await error_panel.get_by_role("listitem").all()
                        error_msgs = [await error.inner_text() for error in errors]

                        print("Has errors:", has_errors)
                        if has_errors:
                            form = new_tab.locator("form").nth(0)
                            form_html_string = await form.evaluate("element => element.outerHTML")
                            with trace(workflow_name="Field Locator"):
                                try:
                                    agent_input = f"""
                                                        Required fields: {", ".join(error_msgs)}
                                                        Raw HTML Form: {form_html_string}
                                                    """
                                    locator_result = await Runner.run(starting_agent=fields_extractor_agent, input=agent_input)
                                    locators = locator_result.final_output.model_dump()["fields"]
                                    pprint(locators)

                                    agent_answers = await Runner.run(starting_agent=form_evaluator, input=json.dumps(locators))
                                    answers_dump = agent_answers.final_output.model_dump()["fields"]
                                    answers = {item["field"]: item["answer"] for item in answers_dump}

                                    print("Answers:", answers)
                                    for field in locators:
                                        field_answer = answers.get(field["field_name"])
                                        match field["field_type"]:
                                            case "select":
                                                select_element = new_tab.locator(field["locator"])
                                                await select_element.select_option(field_answer["label"])
                                        
                                            case "checkbox" | "checkboxes":
                                                answers = field_answer["locator"]
                                                answer_list = answers.split(", ")
                                                for answer in answer_list:
                                                    checkbox_element = new_tab.locator(answer)
                                                    await checkbox_element.check()
                                            case "radio":
                                                radio_element = new_tab.locator(field_answer["locator"])
                                                await radio_element.click()
                                                
                                except openai.BadRequestError as e:
                                    print("Model error", e)
                                except Exception as e:
                                    print("Something went wrong", e)
                    await new_tab.get_by_test_id("review-submit-application").click()
                    await new_tab.wait_for_load_state("networkidle")
                    await new_tab.wait_for_timeout(2000)
                    await new_tab.close()
                    self.run_summary.append(RunSummarry(job_title=job_title,
                                                        job_description=job_description,
                                                        match=run_result["match"],
                                                        percentage=run_result["percentage"],
                                                        reasoning=run_result["reasoning"],
                                                        matched_skills=run_result["matched_skills"],
                                                        missing_skills=run_result["missing_skills"]
                                                        ))

            next_btn = self.page.get_by_role("link", name="Next")
            await next_btn.nth(0).click()
            await self._wait_for_timeout()
            # with open("output.json", "w", encoding="utf-8") as f:
            #     json.dump([summary.model_dump() for summary in self.run_summary], f, indent=4, ensure_ascii=False )
            
        await self._clean_up() 

    async def _clean_up(self):
        if self._context:
            await self._context.close()

        if self._playwright:
            await self._playwright.stop()


if __name__ == "__main__":
    jobstreet = Jobstreet()

    try:
        asyncio.run(jobstreet.automate_job_search())
    finally:
        print(f"Applied to {len(jobstreet.run_summary)} jobs")