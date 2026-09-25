import asyncio
import re
from pprint import pprint
from urllib.parse import urljoin

from agents import Runner, trace
from dotenv import load_dotenv
from playwright.async_api import Locator, Page, expect

from custom_agents.form_evaluator import form_evaluator
from custom_agents.form_fields_extractor import fields_extractor_agent

load_dotenv(override=True)
import json

import openai

from base_page import BasePage, RunSummarry, Type

# from utils.html_simplifier import simplify_form_html
from utils.extract_required_fields import extract_required_fields
from utils.salary_in_range import salary_in_range

JOBSTREET_LINK = "https://ph.jobstreet.com/"


class Jobstreet(BasePage):
    def __init__(self):
        super().__init__()

        # Page elements
        self.search: Locator | None = None
        self.seek_btn: Locator | None = None
        self.work_arrangement: Locator | None = None
        self.remote_option: Locator | None = None
        self.listing_time: Locator | None = None
        self.listing_time_option: Locator | None = None

    async def _wait_for_timeout(self, duration: int = 1):
        """Wait for network idle
        :param duration: Integer in seconds
        """
        # await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(duration * 1000)

    async def _click_outside_modal(self):
        await self.page.locator("body").click(position={"x": 10, "y": 10})

    async def _search_and_filter_jobs(
        self,
        remote_only: bool = True,
        listing_time: int | str = 3,
        keyword: str = "Software Engineer",
    ) -> list[Locator]:
        self.search = self.page.locator("#keywords-input")
        search_input = self.page.locator("#keywords-input")
        if not await search_input.count() > 0:
            await self.page.locator(
                '[data-automation="minimisedSearchBarPlaceholder"]'
            ).click()
        await search_input.clear()
        print(f"Searching for {keyword}")
        await search_input.type(keyword, delay=50)

        self.seek_btn = self.page.get_by_role("button", name="Submit search")
        await expect(self.seek_btn).to_be_visible()
        await self.seek_btn.click()

        await self._wait_for_timeout()

        if remote_only:
            self.work_arrangement = (
                self.page.locator("div")
                .filter(has_text=re.compile(r"^RemoteRemote$"))
                .nth(1)
            )
            await expect(self.work_arrangement).to_be_visible()
            await self.work_arrangement.click()
            self.remote_option = self.page.get_by_role("checkbox", name="Remote")
            await expect(self.remote_option).to_be_visible()
            await self.remote_option.click()
            await self._wait_for_timeout()
            await self._click_outside_modal()

        self.listing_time = self.page.locator(
            '[data-automation="toggleDateListedPanel"]'
        ).nth(1)
        await expect(self.listing_time).to_be_visible()
        await self.listing_time.click()
        listing_time_name = (
            f"Last {listing_time} days"
            if isinstance(listing_time, int)
            else listing_time
        )
        self.listing_time_option = self.page.get_by_role(
            "radio", name=listing_time_name
        )
        await expect(self.listing_time_option).to_be_visible()
        await self.listing_time_option.click()
        await self._click_outside_modal()
        await self._wait_for_timeout()

        # jobs = self.page.get_by_test_id("job-list-item-link-overlay")

    async def answer_form(
        self, error_msgs: list[str], simplified_form_html: str, new_tab: Page
    ):
        retries = 1
        max_retries = 3
        error_encountered = []
        while retries <= max_retries:
            with trace(workflow_name="Jobstreet Field Locator"):
                try:
                    agent_input = f"""
                                Required fields: {", ".join(error_msgs)}
                                Raw HTML Form: {simplified_form_html}
                                {
                        '''
                            IMPORTANT: The previous generated locator(s) failed to fill the form.

                            Review the errors below and re-check the Raw HTML Form carefully.
                            Do NOT repeat the same locator strategy that caused the error.
                            If possible, generate a more specific and reliable locator based on
                            the actual HTML structure, labels, attributes, or relationships.

                            Previous errors:
                            '''
                        + "\n".join(error_encountered)
                        if error_encountered
                        else ""
                    }
                                """
                    locator_result = await Runner.run(
                        starting_agent=fields_extractor_agent,
                        input=agent_input,
                    )
                    locators = locator_result.final_output.model_dump()["fields"]
                    pprint(locators)

                    agent_answers = await Runner.run(
                        starting_agent=form_evaluator,
                        input=json.dumps(locators),
                    )
                    answers_dump = agent_answers.final_output.model_dump()["fields"]
                    answers = {item["field"]: item["answer"] for item in answers_dump}

                    print("Answers:", answers)
                    for field in locators:
                        field_answer = answers.get(field["field_name"])
                        try:
                            match field["field_type"]:
                                case "select":
                                    select_element = new_tab.locator(field["locator"])
                                    await select_element.select_option(
                                        field_answer["label"]
                                    )

                                case "checkbox" | "checkboxes":
                                    answer_locators = field_answer["locator"]
                                    answer_list = answer_locators.split(", ")
                                    for answer in answer_list:
                                        checkbox_element = new_tab.locator(answer)
                                        await checkbox_element.check()
                                case "radio":
                                    radio_element = new_tab.locator(
                                        field_answer["locator"]
                                    )
                                    await radio_element.click(force=True)
                                case "textarea" | "text":
                                    text_area_element = new_tab.locator(
                                        field_answer["locator"]
                                    )
                                    await text_area_element.fill(field_answer["label"])
                        except Exception as e:
                            error_encountered.append(
                                f"""
                                Field: {field["field_name"]}
                                Type: {field["field_type"]}
                                Generated locator: {field.get("locator")}
                                Error: {e}
                                """.strip()
                            )
                            raise
                    return True
                except openai.BadRequestError as e:
                    print("Model error", e)
                    retries += 1
                except Exception as e:  # noqa: BLE001 Ruff comment
                    print("Something went wrong", e)
                    retries += 1
        return False

    async def automate_job_search(self):
        await self.persistent_browser_login(
            page_link=JOBSTREET_LINK, profile="JobstreetProfile"
        )
        try:
            for key in self.search_keys:
                await self._search_and_filter_jobs(
                    keyword=key, remote_only=False, listing_time="Today"
                )
                has_next_page = (
                    await self.page.locator(
                        'a[rel="nofollow next"][data-automation^="page-"]:not([aria-hidden="true"])'
                    ).count()
                    > 0
                )
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
                        salary_locator = job.locator(
                            '[data-automation="jobSalary"]'
                        ).first
                        job_salary = (
                            await salary_locator.inner_text()
                            if await salary_locator.count()
                            else ""
                        )

                        job_listing_date = (
                            await job.locator('[data-automation="jobListingDate"]')
                            .nth(0)
                            .inner_text()
                        )
                        already_applied = "Applied" in job_listing_date
                        already_saved = (
                            await job.locator(
                                '[data-automation="remove-save-job"]'
                            ).count()
                        ) > 0
                        viewed = "Viewed" in job_listing_date
                        started_applying = "Started applying" in job_listing_date

                        if (
                            already_applied
                            or viewed
                            or skip_job
                            or already_saved
                            or started_applying
                            or not salary_in_range(job_salary)
                        ):
                            continue
                        new_tab = None
                        try:
                            await self._click_outside_modal()
                            await job.scroll_into_view_if_needed()
                            await job.click()
                            await self._wait_for_timeout()

                            job_details_section = self.page.locator(
                                '[data-automation="jobDetailsPage"]'
                            ).nth(0)
                            await expect(job_details_section).to_be_visible()
                            salary_range_element = job_details_section.locator(
                                '[data-automation="job-detail-salary"]'
                            )
                            salary_range_inside_job_details = (
                                await salary_range_element.inner_text()
                                if await salary_range_element.count()
                                else ""
                            )
                            if not salary_in_range(salary_range_inside_job_details):
                                continue
                            quick_apply_btn = job_details_section.locator(
                                '[data-automation="job-detail-apply"]',
                                has_text=re.compile(r"quick apply", re.I),
                            ).nth(0)
                            job_details_section.locator(
                                '[data-automation="job-detail-apply"]',
                                has_text=re.compile(r"apply", re.I),
                            ).nth(0)

                            save_btn = job_details_section.get_by_test_id(
                                "jdv-savedjob"
                            ).nth(0)

                            if (
                                await quick_apply_btn.count() == 0
                                and await save_btn.count() == 0
                            ):
                                print(
                                    "Job has no quick apply or save button. Skipping."
                                )
                                continue
                            job_title_element = job_details_section.get_by_role(
                                "link"
                            ).nth(0)
                            job_url = await job_title_element.get_attribute("href")
                            job_url = urljoin(self.page.url, job_url)
                            print(job_url)
                            if not await job_title_element.inner_text():
                                job_title_element = job_details_section.get_by_role(
                                    "link"
                                ).nth(1)
                            job_description_section = job_details_section.locator(
                                '[data-automation="jobAdDetails"]'
                            )

                            already_saved = (await save_btn.inner_text()) == "Unsave"
                            if already_saved:
                                continue

                            job_title = await job_title_element.inner_text()

                            title_result = await self.evaluate_job_title(
                                job_title=job_title,
                                workflow_name="Jobstreet Job Title Evaluation",
                            )
                            if (
                                title_result is not None
                                and title_result.final_output.model_dump().get("match")
                                is False
                            ):
                                continue

                            job_description = await job_description_section.inner_text()

                            job_evaluation_result = await self.evaluate_job(
                                job_title=job_title,
                                job_description=job_description,
                                workflow_name="Jobstreet Job Evaluation",
                            )

                            if job_evaluation_result is None:
                                continue

                            await self._wait_for_timeout()

                            run_result = job_evaluation_result.final_output.model_dump()
                            has_quick_apply_btn = await quick_apply_btn.count() > 0
                            if (
                                not has_quick_apply_btn
                                and run_result.get("match") is True
                                and run_result.get("percentage") >= 80
                                and not already_saved
                            ):
                                await save_btn.click()
                                self.append_job(
                                    RunSummarry(
                                        type=Type.SAVED,
                                        job_title=job_title,
                                        job_description=job_description,
                                        job_link=job_url,
                                        match=run_result["match"],
                                        percentage=run_result["percentage"],
                                        reasoning=run_result["reasoning"],
                                        matched_skills=run_result["matched_skills"],
                                        missing_skills=run_result["missing_skills"],
                                    )
                                )
                                continue
                            if has_quick_apply_btn and run_result.get("match") is True:
                                async with self.page.context.expect_page() as new_page:
                                    await quick_apply_btn.click()
                                new_tab = await new_page.value
                                await new_tab.wait_for_load_state("domcontentloaded")
                                dont_include_a_cover_letter = new_tab.locator(
                                    "label"
                                ).filter(has_text="Don't include a cover letter")
                                await dont_include_a_cover_letter.click()
                                continue_btn = new_tab.get_by_test_id("continue-button")

                                while await continue_btn.count() > 0:
                                    await continue_btn.nth(0).click()
                                    print("Clicked continue button")
                                    await new_tab.wait_for_timeout(1000)
                                    error_panel = new_tab.locator("#errorPanel")
                                    has_errors = await error_panel.count() > 0
                                    errors = await error_panel.get_by_role(
                                        "listitem"
                                    ).all()
                                    error_msgs = [
                                        await error.inner_text() for error in errors
                                    ]

                                    print("Has errors:", has_errors)
                                    if has_errors:
                                        form = new_tab.locator("form").nth(0)
                                        form_html_string = await form.evaluate(
                                            "element => element.outerHTML"
                                        )
                                        simplified_form_html = extract_required_fields(
                                            html=form_html_string,
                                            required_fields=error_msgs,
                                        )

                                        able_to_answer = await self.answer_form(
                                            error_msgs=error_msgs,
                                            simplified_form_html=simplified_form_html,
                                            new_tab=new_tab,
                                        )
                                        if able_to_answer is False:
                                            raise Exception("Failed to answer form")  # noqa: TRY002
                                await new_tab.get_by_test_id(
                                    "review-submit-application"
                                ).click()
                                await new_tab.wait_for_load_state("networkidle")
                                await new_tab.wait_for_timeout(2000)
                                await new_tab.close()
                                self.append_job(
                                    RunSummarry(
                                        job_title=job_title,
                                        job_description=job_description,
                                        job_link=job_url,
                                        match=run_result["match"],
                                        percentage=run_result["percentage"],
                                        reasoning=run_result["reasoning"],
                                        matched_skills=run_result["matched_skills"],
                                        missing_skills=run_result["missing_skills"],
                                    )
                                )
                        except Exception as error:  # noqa: BLE001
                            print("Error occured", error)
                            if new_tab is not None and not new_tab.is_closed():
                                await new_tab.close()
                            continue

                    next_btn = self.page.locator(
                        'a[rel="nofollow next"][data-automation^="page-"]:not([aria-hidden="true"])'
                    )
                    print(await next_btn.count())
                    if await next_btn.count() == 0:
                        break
                    await next_btn.nth(0).scroll_into_view_if_needed()
                    await next_btn.nth(0).click(force=True)
                    await self._wait_for_timeout()
                    # with open("output.json", "w", encoding="utf-8") as f:
                    #     json.dump([summary.model_dump() for summary in self.run_summary], f, indent=4, ensure_ascii=False )

        except Exception as error:
            print("Something went wrong", error)
            raise


async def main():
    jobstreet = Jobstreet()

    try:
        await jobstreet.automate_job_search()
    except Exception as error:  # noqa: BLE001
        print("Something went wrong:", error)
        print("Retrying...")
        await jobstreet._clean_up()
        try:
            await jobstreet.automate_job_search()
        except Exception as retry_error:  # noqa: BLE001
            print("Retry also failed:", retry_error)
    finally:
        print("Generating HTML report...")
        jobstreet.generate_html_run_summary(page="jobstreet")
        await jobstreet._clean_up()


if __name__ == "__main__":
    asyncio.run(main())
