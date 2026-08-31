import re
from pathlib import Path
import asyncio
from playwright.async_api import async_playwright, Page, expect, Locator
from agents import Runner, trace
from dotenv import load_dotenv
from custom_agents.job_analyzer import job_analyzer_agent
from custom_agents.form_evaluator import fields_extractor_agent
from pydantic import BaseModel
from pprint import pprint
load_dotenv(override=True)
import json
import openai
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

    async def _wait_for_timeout(self, duration: int = 1):
        """Wait for network idle
        :param duration: Integer in seconds
        """
        await self.page.wait_for_load_state('networkidle')
        await self.page.wait_for_timeout(duration * 1000)

    async def _click_outside_modal(self):
        await self.page.locator("body").click(position={"x": 10, "y": 10})


    async def _search_and_filter_jobs(self, keyword:str="Software Engineer") -> list[Locator]:
        await self._persistent_browser_login()
    
        await self.page.goto(JOBSTREET_LINK)
        self.search = self.page.locator("#keywords-input")
        await self.search.type(keyword, delay=50)

        self.seek_btn = self.page.get_by_role("button", name="Submit search")
        await expect(self.seek_btn).to_be_visible()
        await self.seek_btn.click()

        await self._wait_for_timeout()

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
        await self._wait_for_timeout()
        await self._click_outside_modal()    
        jobs = self.page.get_by_test_id("job-list-item-link-overlay")
        assert await jobs.count() > 1 
        return await jobs.all()
    
    async def goto_page(self):
        jobs = await self._search_and_filter_jobs(keyword="Java")

        for i, job in enumerate(jobs, start=1):
            if len(self.run_summary) > 1:
                break
            await job.click()
            await self._wait_for_timeout(2)

            job_details_section = self.page.locator('[data-automation="jobDetailsPage"]').nth(0)
            await expect(job_details_section).to_be_visible()
            
            quick_apply_btn = job_details_section.locator('[data-automation="job-detail-apply"]', has_text=re.compile(r"quick apply", re.I))
            external_apply_btn = job_details_section.locator('[data-automation="job-detail-apply"]', has_text=re.compile(r"apply", re.I))

            save_btn = job_details_section.get_by_test_id("jdv-savedjob").nth(0)
            
            job_title_element = job_details_section.get_by_role("link").nth(0)
            if(not await job_title_element.inner_text()):
                job_title_element = job_details_section.get_by_role("link").nth(1)
            job_description_section = job_details_section.locator('[data-automation="jobAdDetails"]')
            
            job_title = await job_title_element.inner_text()
            job_description = await job_description_section.inner_text()
            
            job_input = f"""Job Title: {job_title} \n
            Job Description: \n {job_description}
            """
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
            
            await self._wait_for_timeout(3)

            already_saved = (await save_btn.inner_text()) == "Unsave"
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
                await continue_btn.click()
                await self._wait_for_timeout()
                await continue_btn.click()
                error_panel = new_tab.locator("#errorPanel")
                has_errors = await error_panel.count() > 0
                errors = await error_panel.get_by_role("listitem").all()
                error_msgs = [await error.inner_text() for error in errors]

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
                            locators = locator_result.final_output.model_dump()
                            pprint(locators)
                        except openai.BadRequestError as e:
                            print("Model error", e)
                        except Exception as e:
                            print("Something went wrong", e)
                            
                
                await self.page.pause()
                # self.run_summary.append(RunSummarry(job_title=job_title, job_description=job_description, match=run_result["match"], percentage=run_result["percentage"], reasoning=run_result["reasoning"], matched_skills=run_result["matched_skills"], missing_skills=run_result["missing_skills"]))

        # with open("output.json", "w", encoding="utf-8") as f:
        #     json.dump([summary.model_dump() for summary in self.run_summary], f, indent=4, ensure_ascii=False )
        await self.page.pause()
        await self._clean_up()

    async def _clean_up(self):
        if self._context:
            await self._context.close()

        if self._playwright:
            await self._playwright.stop()


if __name__ == "__main__":
    jobstreet = Jobstreet()

    try:
        asyncio.run(jobstreet.goto_page())
    finally:
        print(f"Applied to {len(jobstreet.run_summary)} jobs")