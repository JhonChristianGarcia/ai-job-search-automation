import asyncio
import json
from pprint import pprint

import openai
from agents import Runner, trace
from playwright.async_api import Locator

from base_page import BasePage
from custom_agents.form_evaluator import form_evaluator
from custom_agents.form_fields_extractor import fields_extractor_agent
from custom_agents.job_analyzer import job_analyzer_agent
from utils.alert_for_unknown_question import alert_for_unknown_answer
from utils.indeed_fields_extractor import extract_all_form_fields
from utils.salary_in_range import salary_in_range

INDEED_PAGE_LINK = "https://ph.indeed.com/"


class Indeed(BasePage):
    def __init__(self):
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

    async def automate_job_search(self):
        await self.persistent_browser_login(INDEED_PAGE_LINK)

        search_keys = [
            "Node.js",
            "Laravel",
            "React",
            "Software Engineer",
            "AWS",
            "DevOps",
        ]
        for key in search_keys:
            await self._search_and_filter(keyword=key)

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
                for i, job in enumerate(jobs, start=1):
                    job_quick_details = await job.inner_text()
                    salary_range_element = job.locator(
                        "[data-testid~='salary-snippet-container']"
                    )
                    salary_range = (
                        await salary_range_element.inner_text()
                        if await salary_range_element.count() > 0
                        else ""
                    )
                    print("SALARY RANGE", salary_range)
                    if (
                        self._skip_this_job(job_quick_details)
                        or not salary_in_range(salary_range)
                        or not await job.is_visible()
                    ):
                        continue

                    await job.scroll_into_view_if_needed()
                    await job.click()

                    await self.page.wait_for_selector("#jobsearch-ViewjobPaneWrapper")
                    await self.page.wait_for_timeout(2000)
                    job_details_container = self.page.locator(
                        "#jobsearch-ViewjobPaneWrapper"
                    ).nth(0)

                    job_header_container = self.page.locator(
                        ".jobsearch-HeaderContainer"
                    ).nth(0)
                    quick_apply_btn = job_header_container.get_by_role(
                        "button", name="Apply with Indeed opens in a new tab"
                    )
                    job_title = (
                        await job_header_container.get_by_test_id(
                            "jobsearch-JobInfoHeader-title"
                        )
                        .nth(0)
                        .inner_text()
                    )
                    job_description = (
                        await job_details_container.locator("#jobDescriptionText")
                        .nth(0)
                        .inner_text()
                    )

                    job_input = f"""Job Title: {job_title} \n
                                        Job Description: \n {job_description}
                                        """
                    result = None
                    max_retries = 2
                    with trace(workflow_name="Job Search Automation"):
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
                                if (
                                    "json_validate_failed" in str(e)
                                    and attempt < max_retries
                                ):
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

                    if result is None:
                        continue
                    run_result = result.final_output.model_dump()

                    if run_result.get("match") is False:
                        continue

                    has_quick_apply_btn = await quick_apply_btn.count() > 0

                    if not has_quick_apply_btn:
                        continue

                    if has_quick_apply_btn and run_result.get("match") is True:
                        async with self.page.context.expect_page() as new_page:
                            await quick_apply_btn.click()
                        new_tab = await new_page.value
                        await new_tab.wait_for_timeout(2500)
                        await new_tab.wait_for_load_state("domcontentloaded")
                        continue_btn = new_tab.get_by_role("button", name="Continue")

                        while await continue_btn.count() > 0:
                            await continue_btn.nth(0).click()
                            await new_tab.wait_for_load_state("domcontentloaded")
                            await new_tab.wait_for_timeout(2000)
                            has_questions = (
                                await new_tab.locator(".ia-Questions").count() > 0
                            )

                            if has_questions:
                                form = new_tab.locator(".ia-Questions").nth(0)
                                form_html_string = await form.evaluate(
                                    "element => element.outerHTML"
                                )
                                simplified_form_html = extract_all_form_fields(
                                    form_html_string,
                                )
                                print(simplified_form_html)

                                with trace(workflow_name="Field Locator"):
                                    try:
                                        agent_input = f"""
                                                        Raw HTML Form: {simplified_form_html}
                                                        """
                                        locator_result = await Runner.run(
                                            starting_agent=fields_extractor_agent,
                                            input=agent_input,
                                        )
                                        locators = (
                                            locator_result.final_output.model_dump()[
                                                "fields"
                                            ]
                                        )
                                        pprint(locators)

                                        agent_answers = await Runner.run(
                                            starting_agent=form_evaluator,
                                            input=json.dumps(locators),
                                        )
                                        answers_dump = (
                                            agent_answers.final_output.model_dump()[
                                                "fields"
                                            ]
                                        )
                                        answers = {
                                            item["field"]: item["answer"]
                                            for item in answers_dump
                                        }

                                        if any(
                                            answer["label"].strip().lower() == "unknown"
                                            for answer in answers.values()
                                        ):
                                            alert_for_unknown_answer()
                                            await new_tab.pause()

                                        print("Answers:", answers)
                                        for field in locators:
                                            field_answer = answers.get(
                                                field["field_name"]
                                            )
                                            match field["field_type"]:
                                                case "select":
                                                    select_element = new_tab.locator(
                                                        f'{field["locator"]}:not([aria-hidden="true"])'
                                                    )
                                                    if not await select_element.is_visible():
                                                        continue
                                                    await select_element.scroll_into_view_if_needed()
                                                    await select_element.select_option(
                                                        field_answer["label"]
                                                    )

                                                case "checkbox" | "checkboxes":
                                                    answer_list = field_answer[
                                                        "locator"
                                                    ].split(", ")
                                                    for answer in answer_list:
                                                        checkbox_element = new_tab.locator(
                                                            f'{answer}:not([aria-hidden="true"])'
                                                        )
                                                        if not await checkbox_element.is_visible():
                                                            continue
                                                        await checkbox_element.check(
                                                            force=True
                                                        )
                                                case "radio":
                                                    radio_element = new_tab.locator(
                                                        f'{field_answer["locator"]}:not([aria-hidden="true"])'
                                                    )
                                                    if not await radio_element.is_visible():
                                                        continue
                                                    await radio_element.scroll_into_view_if_needed()
                                                    await radio_element.click()
                                                case "textarea" | "text":
                                                    text_area_element = new_tab.locator(
                                                        f'{field_answer["locator"]}:not([aria-hidden="true"])'
                                                    )
                                                    if not await text_area_element.is_visible():
                                                        continue
                                                    await text_area_element.scroll_into_view_if_needed()
                                                    await text_area_element.clear()
                                                    await text_area_element.fill(
                                                        field_answer["label"]
                                                    )
                                                case "number":
                                                    number_field = new_tab.locator(
                                                        f'{field_answer["locator"]}:not([aria-hidden="true"])'
                                                    )
                                                    if not await number_field.is_visible():
                                                        continue
                                                    await number_field.scroll_into_view_if_needed()
                                                    await number_field.fill(
                                                        field_answer["label"]
                                                    )
                                    except openai.BadRequestError as e:
                                        print("Model error", e)
                                        continue
                        await new_tab.get_by_test_id(
                            "submit-application-button"
                        ).click()
                        await new_tab.wait_for_timeout(2500)
                        await new_tab.close()

                next_btn = self.page.get_by_test_id("pagination-page-next")
                if await next_btn.count() == 0:
                    break
                await next_btn.click()
                await self.wait_for_timeout(2)

        await self.page.pause()


if __name__ == "__main__":
    indeed = Indeed()

    try:
        asyncio.run(indeed.automate_job_search())
    finally:
        print("Execution finished")
