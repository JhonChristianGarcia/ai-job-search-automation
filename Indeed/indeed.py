import asyncio
import json
from pprint import pprint
from urllib.parse import urljoin

import openai
from agents import Runner, trace
from playwright.async_api import Locator, Page

from base_page import BasePage, RunSummarry, Type
from custom_agents.form_evaluator import form_evaluator
from custom_agents.form_fields_extractor import fields_extractor_agent
from utils.indeed_fields_extractor import extract_all_form_fields
from utils.salary_in_range import salary_in_range

INDEED_PAGE_LINK = "https://ph.indeed.com/"


class Indeed(BasePage):
    def __init__(self):
        super().__init__()
        self.search: Locator | None = None

    async def _search_and_filter(
        self, keyword: str = "Software Engineer", listing_time: int = 3
    ):
        self.search = self.page.locator("#text-input-what")
        await self.search.clear()
        await self.search.type(keyword, delay=150)
        await self.page.get_by_role("button", name="Find jobs").click()
        await self.wait_for_timeout(2)
        await self.page.get_by_role("button", name="Date posted filter").click()

        if listing_time == 24:
            await self.page.get_by_text("Last 24 hours").click()
            await self.wait_for_timeout()
            await self.page.get_by_role("button", name="Update").nth(0).click()
            await self.wait_for_timeout()
        else:
            await self.page.get_by_text(f"Last {listing_time} days").click()
            await self.wait_for_timeout()
            await self.page.get_by_role("button", name="Update").nth(0).click()
            await self.wait_for_timeout()

        await self.page.get_by_role("button", name="Job type filter").click()
        await self.wait_for_timeout()
        await (
            self.page.get_by_test_id("selection-pill-option-0")
            .get_by_text("Full-time")
            .click()
        )
        await self.wait_for_timeout()
        await self.page.get_by_role("button", name="Update").nth(0).click()
        await self.wait_for_timeout()

    async def _answer_form_questions(
        self, simplified_form_html: str, new_tab: Page
    ) -> bool:
        max_retries = 1
        error = None

        for attempt in range(max_retries):
            try:
                locators, answers = await self._generate_fields_and_answers(
                    new_tab=new_tab, simplified_form_html=simplified_form_html
                )

                await self._fill_form_fields(
                    locators=locators, answers=answers, new_tab=new_tab
                )

                print("Form answered successfully")
                return True
            except Exception as e:  # noqa: BLE001
                error = str(e)
                print(f"Attempt {attempt + 1}/{max_retries} failed:\n{error}")

                if attempt < max_retries - 1:
                    print("Retrying with error feedback...")
        await new_tab.close()
        return False

    async def _generate_fields_and_answers(
        self, simplified_form_html: str, new_tab: Page
    ) -> tuple[list, dict]:
        with trace(workflow_name="Indeed Field Locator"):
            try:
                agent_input = f"""
                                    Raw HTML Form: {simplified_form_html}
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

                # if any(
                #     answer["label"].strip().lower() == "unknown"
                #     for answer in answers.values()
                # ):
                #     alert_for_unknown_answer()
                #     if await save_job_toggle.count() > 0:
                #         await save_job_toggle.click()
                #     continue

                print("Answers:", answers)
                await self._fill_form_fields(
                    new_tab=new_tab, answers=answers, locators=locators
                )
                return locators, answers
            except openai.BadRequestError as e:
                print("Model error", e)
                raise
            except Exception as error:
                print(f"Unhandled error {error}")
                raise

    async def _fill_form_fields(self, locators: list, answers: dict, new_tab: Page):
        try:
            for field in locators:
                field_answer = answers.get(field["field_name"])
                match field["field_type"]:
                    case "select":
                        select_element = new_tab.locator(
                            f'{field["locator"]}:not([aria-hidden="true"])'
                        )

                        await select_element.scroll_into_view_if_needed()
                        await select_element.select_option(field_answer["label"])

                    case "checkbox" | "checkboxes":
                        answer_list = field_answer["locator"].split(", ")
                        for answer in answer_list:
                            checkbox_element = new_tab.locator(
                                f'{answer}:not([aria-hidden="true"])'
                            )

                            await checkbox_element.check(force=True)
                    case "radio":
                        radio_element = new_tab.locator(
                            f'{field_answer["locator"]}:not([aria-hidden="true"])'
                        )

                        await radio_element.scroll_into_view_if_needed()
                        await radio_element.click()
                    case "textarea" | "text":
                        text_area_element = new_tab.locator(
                            f'{field_answer["locator"]}:not([aria-hidden="true"])'
                        )

                        await text_area_element.scroll_into_view_if_needed()
                        await text_area_element.clear()
                        await text_area_element.fill(field_answer["label"])
                    case "number":
                        number_field = new_tab.locator(
                            f'{field_answer["locator"]}:not([aria-hidden="true"])'
                        )

                        await number_field.scroll_into_view_if_needed()
                        await number_field.fill(field_answer["label"])
        except Exception as e:
            print("Error occured filling in fields", e)
            raise

    async def automate_job_search(self):
        await self.persistent_browser_login(
            page_link=INDEED_PAGE_LINK, profile="IndeedProfile"
        )
        try:
            for key in self.search_keys:
                await self._search_and_filter(keyword=key, listing_time=24)
                job_scroll_pane = self.page.locator(".jobsearch-LeftPane")
                while True:
                    job_cards = job_scroll_pane.locator(
                        '[data-testid="slider_container"]:not([aria-hidden="true"])'
                    )
                    jobs = await job_cards.all()
                    total_jobs = await job_cards.count()
                    if total_jobs == 0:
                        print("No jobs found")
                        break
                    print(f"Found {total_jobs} jobs on this page")
                    for job in jobs:
                        save_job_toggle = job.get_by_role("listitem").get_by_role(
                            "button", name="Save job Toggle", pressed=False
                        )
                        job_quick_details = await job.inner_text()
                        job_link = await job.locator("h3.jobTitle a").get_attribute(
                            "href"
                        )
                        job_link = urljoin("https://ph.indeed.com", job_link)

                        salary_range_element = job.locator(
                            "[data-testid~='salary-snippet-container']"
                        )
                        salary_range = (
                            await salary_range_element.inner_text()
                            if await salary_range_element.count() > 0
                            else ""
                        )

                        if (
                            self._skip_this_job(job_quick_details)
                            or not salary_in_range(salary_range)
                            or not await job.is_visible()
                        ):
                            continue

                        new_tab = None
                        try:
                            await job.scroll_into_view_if_needed()
                            await job.click()

                            await self.page.wait_for_timeout(2000)
                            job_details_container = self.page.get_by_test_id(
                                "viewjob-main-content"
                            ).nth(0)

                            job_header_container = self.page.get_by_test_id(
                                "desktop-job-header"
                            ).nth(0)
                            quick_apply_btn = job_header_container.get_by_test_id(
                                "viewjob-indeed-apply"
                            )
                            job_header_actions = job_header_container.get_by_test_id(
                                "job-header-actions"
                            )
                            save_job_btn = job_header_actions.get_by_test_id(
                                "vj-saveJobButton"
                            )
                            job_title = (
                                await job_header_container.get_by_test_id(
                                    "vj-job-title"
                                )
                                .nth(0)
                                .inner_text()
                            )
                            title_result = await self.evaluate_job_title(
                                job_title=job_title,
                                workflow_name="Indeed Job Title Evaluation",
                            )
                            if (
                                title_result is not None
                                and title_result.final_output.model_dump().get("match")
                                is False
                            ):
                                continue

                            job_description = (
                                await job_details_container.get_by_test_id(
                                    "viewjob-job-content"
                                )
                                .nth(0)
                                .inner_text()
                            )

                            job_evaluation_result = await self.evaluate_job(
                                job_title=job_title,
                                job_description=job_description,
                                workflow_name="Indeed Job Evaluation",
                            )

                            if job_evaluation_result is None:
                                continue
                            run_result = job_evaluation_result.final_output.model_dump()

                            if run_result.get("match") is False:
                                continue

                            has_quick_apply_btn = await quick_apply_btn.count() > 0

                            if (
                                not has_quick_apply_btn
                                and run_result.get("Match") is True
                            ):
                                await save_job_btn.click()
                                self.append_job(
                                    RunSummarry(
                                        type=Type.SAVED,
                                        job_title=job_title,
                                        job_link=job_link,
                                        job_description=job_description,
                                        match=run_result["match"],
                                        percentage=run_result["percentage"],
                                        reasoning=run_result["reasoning"],
                                        matched_skills=run_result["matched_skills"],
                                        missing_skills=run_result["missing_skills"],
                                    )
                                )
                                await self.wait_for_timeout(2)

                                continue
                            if has_quick_apply_btn and run_result.get("match") is True:
                                async with self.page.context.expect_page() as new_page:
                                    await quick_apply_btn.click()
                                new_tab = await new_page.value
                                await new_tab.wait_for_load_state(
                                    state="load", timeout=10_000
                                )
                                await new_tab.wait_for_timeout(5_000)
                                submit_btn = new_tab.get_by_test_id(
                                    "submit-application-button"
                                )
                                error_occured_answering_form = False

                                while await submit_btn.count() == 0:
                                    has_questions = (
                                        await new_tab.locator(".ia-Questions").count()
                                        > 0
                                    )

                                    if has_questions:
                                        form = new_tab.locator(".ia-Questions").nth(0)
                                        form_html_string = await form.evaluate(
                                            "element => element.outerHTML"
                                        )
                                        simplified_form_html = extract_all_form_fields(
                                            form_html_string,
                                        )
                                        successfully_answered_form = await self._answer_form_questions(
                                            new_tab=new_tab,
                                            simplified_form_html=simplified_form_html,
                                        )

                                        await new_tab.wait_for_timeout(2_000)

                                        if not successfully_answered_form:
                                            error_occured_answering_form = True
                                            break

                                        if await submit_btn.count() > 0:
                                            break

                                    continue_btn = new_tab.get_by_test_id(
                                        "continue-button"
                                    )
                                    if await continue_btn.count() == 0:
                                        print(
                                            "Neither continue nor submit button found, aborting application"
                                        )
                                        error_occured_answering_form = True
                                        break

                                    await continue_btn.nth(0).click()
                                    await new_tab.wait_for_timeout(2000)

                                if error_occured_answering_form is False:
                                    await submit_btn.click()
                                    self.append_job(
                                        RunSummarry(
                                            type=Type.APPLIED,
                                            job_title=job_title,
                                            job_description=job_description,
                                            job_link=job_link,
                                            match=run_result["match"],
                                            percentage=run_result["percentage"],
                                            reasoning=run_result["reasoning"],
                                            matched_skills=run_result["matched_skills"],
                                            missing_skills=run_result["missing_skills"],
                                        )
                                    )
                                    await new_tab.wait_for_timeout(2500)
                                    await new_tab.close()
                                else:
                                    continue
                        except Exception as error:  # noqa: BLE001
                            print("Error occured...", error)
                            print("Continuing the loop")
                            if new_tab is not None and not new_tab.is_closed():
                                await new_tab.close()
                            continue
                    next_btn = self.page.get_by_test_id("pagination-page-next")
                    if await next_btn.count() == 0:
                        break
                    await next_btn.click()
                    await self.wait_for_timeout(2)
        except Exception as error:  # noqa: BLE001
            print("Error", error)
            raise

async def main():
    indeed = Indeed()

    try:
        await indeed.automate_job_search()
    except Exception as error:  # noqa: BLE001
        print("Something went wrong:", error)
        print("Retrying...")
        await indeed._clean_up()
        try:
            await indeed.automate_job_search()
        except Exception as retry_error:  # noqa: BLE001
            print("Retry also failed:", retry_error)
    finally:
        await indeed._clean_up()
        print("Execution finished")
        print("Genarating report")
        indeed.generate_html_run_summary(page="indeed")


if __name__ == "__main__":
    asyncio.run(main())
