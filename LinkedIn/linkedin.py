import asyncio
import json
import re
from pprint import pprint

import openai
from agents import Runner, trace
from playwright.async_api import FrameLocator, Locator

from base_page import BasePage
from custom_agents.form_evaluator import form_evaluator
from custom_agents.form_fields_extractor import fields_extractor_agent
from utils.linked_in_extract_required_fields import linked_in_xtract_required_fields

LINKEDIN_PAGE_LINK = "https://www.linkedin.com/jobs/"


class LinkedIn(BasePage):
    def __init__(self):
        self.search: Locator | None = None
        self.frame = FrameLocator | None

    async def _handle_form_failure(self, modal: Locator):
        print("Unable to answer questions, closing...")
        try:
            await modal.get_by_role("button", name="Dismiss").nth(0).click()
            await modal.get_by_role("button", name="Discard").nth(0).click()
        except Exception as e:  # noqa: BLE001
            print(f"Failed to close modal: {e}")

    async def fill_in_form_fields(
        self,
        locators: list,
        answers: dict,
        modal: Locator,
    ):
        for field in locators:
            field_name = field["field_name"]

            try:
                field_answer = answers.get(field_name)

                if not field_answer:
                    raise ValueError(f"No answer found for: {field_name}")

                match field["field_type"]:
                    case "select":
                        select_element = modal.locator(field["locator"])
                        await select_element.select_option(label=field_answer["label"])

                    case "checkbox" | "checkboxes":
                        answer_locators = field_answer["locator"]
                        answer_list = answer_locators.split(", ")

                        for answer in answer_list:
                            checkbox_element = modal.locator(answer)
                            await checkbox_element.check()

                    case "radio":
                        radio_element = modal.locator(
                            f"[data-test-text-selectable-option__label="
                            f"'{field_answer['label']}']"
                        )
                        await radio_element.click()

                    case "textarea" | "text":
                        element = modal.locator(field_answer["locator"])
                        await element.fill(field_answer["label"])

                    case "input" | "text input":
                        element = modal.locator(f"input{field_answer['locator']}")
                        await element.fill(field_answer["label"])

                    case _:
                        raise ValueError(
                            f"Unsupported field type '{field['field_type']}' allowed field types: [select, checkbox, checkboxes,radio, textarea, text, input ] "
                            f"for field: {field_name}"
                        )

            except Exception as e:
                print(
                    f"Failed to fill field: {field_name}\n"
                    f"Field type: {field.get('field_type')}\n"
                    f"Answer: {field_answer if 'field_answer' in locals() else None}\n"
                    f"Error: {e}"
                )
                raise

    async def extract_and_generate_answers(
        self, form_str: str, error: str | None
    ) -> tuple[list, dict]:
        with trace(workflow_name="LinkedIn Field Locator"):
            try:
                agent_input = f"""
                                Raw HTML Form: {form_str}
                            """
                if error:
                    agent_input += f"""
                        Previous attempt failed with this error:
                        {error}

                        Use this error to correct the field locator or answer that caused
                        the failure. Do not repeat the same mistake.
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

                answers_dump = agent_answers.final_output.model_dump().get("fields")

                print("answers:\n", answers_dump)

                answers = {item["field"]: item["answer"] for item in answers_dump}

                print("Agent answers", answers)
                return locators, answers
            except openai.BadRequestError as e:
                print(f"Model error: {e}")
                raise

            except Exception as error:
                print("Error occured", error)
                raise

    async def _answer_form_questions(
        self,
        form_str: str,
        modal: Locator,
    ) -> bool:
        max_retries = 1
        error = None

        for attempt in range(max_retries):
            try:
                print(f"Answering form — attempt {attempt + 1}/{max_retries}")

                locators, answers = await self.extract_and_generate_answers(
                    form_str=form_str,
                    error=error,
                )

                await self.fill_in_form_fields(
                    locators,
                    answers,
                    modal,
                )

                print("Form answered successfully")
                return True

            except Exception as e:  # noqa: BLE001
                error = str(e)

                print(f"Attempt {attempt + 1}/{max_retries} failed:\n{error}")

                if attempt < max_retries - 1:
                    print("Retrying with error feedback...")

        await self._handle_form_failure(modal)
        return False

    # async def answer_form_questions(self, form_str: str, modal: Locator):
    #     with trace(workflow_name="LinkedIn Field Locator"):
    #         try:
    #             agent_input = f"""
    #                     Raw HTML Form: {form_str}
    #                 """

    #             locator_result = await Runner.run(
    #                 starting_agent=fields_extractor_agent,
    #                 input=agent_input,
    #             )

    #             locators = locator_result.final_output.model_dump()["fields"]

    #             pprint(locators)

    #             agent_answers = await Runner.run(
    #                 starting_agent=form_evaluator,
    #                 input=json.dumps(locators),
    #             )

    #             answers_dump = agent_answers.final_output.model_dump().get("fields")

    #             print("answers:\n", answers_dump)

    #             answers = {item["field"]: item["answer"] for item in answers_dump}

    #             print("Agent answers", answers)

    #             for field in locators:
    #                 field_answer = answers.get(field["field_name"])

    #                 if not field_answer:
    #                     raise ValueError(f"No answer found for: {field['field_name']}")

    #                 match field["field_type"]:
    #                     case "select":
    #                         select_element = modal.locator(field["locator"])

    #                         await select_element.select_option(
    #                             label=field_answer["label"]
    #                         )

    #                     case "checkbox" | "checkboxes":
    #                         answer_locators = field_answer["locator"]
    #                         answer_list = answer_locators.split(", ")

    #                         for answer in answer_list:
    #                             checkbox_element = modal.locator(answer)
    #                             await checkbox_element.check()

    #                     case "radio":
    #                         radio_element = modal.locator(
    #                             f"[data-test-text-selectable-option__label='{field_answer['label']}']"
    #                         )

    #                         await radio_element.click()

    #                     case "textarea" | "text":
    #                         element = modal.locator(field_answer["locator"])

    #                         await element.fill(field_answer["label"])

    #                     case "input" | "text input":
    #                         element = modal.locator(f"input{field_answer['locator']}")

    #                         await element.fill(field_answer["label"])

    #                     case _:
    #                         print(
    #                             "Field Not found",
    #                             field["field_type"],
    #                         )

    #         except openai.BadRequestError as e:
    #             print(f"Model error: {e}")
    #             raise

    #         except Exception as error:  # noqa: BLE001
    #             print("Error occured", error)

    async def automate_job_search(self):
        await self.persistent_browser_login(page_link=LINKEDIN_PAGE_LINK)
        self.frame = self.page.locator('[data-testid="interop-iframe"]').content_frame
        search_keys = [
            "Laravel",
            "React",
            "Node.js",
            "Python",
            "Software Engineer",
            "Software Developer",
            "AWS",
            "DevOps",
        ]
        try:
            for key in search_keys:
                await self._search_and_filter(keyword=key, listing_time=7)
                while True:
                    job_cards = self.frame.locator(
                        'li[data-occludable-job-id]:not([aria-hidden="true"])'
                    )
                    count = await job_cards.count()
                    print(f"Found {count} jobs in this page")

                    for i in range(count):
                        # Locate the card freshly in each iteration to avoid stale element references
                        card = job_cards.nth(i)

                        card_details = await card.inner_text()
                        applied = "Applied" in card_details
                        viewed = "Viewed" in card_details

                        if (
                            self._skip_this_job(card_details)
                            or applied
                            or viewed
                            or "Perform" in card_details
                            or "Pear Tree" in card_details
                        ):
                            continue

                        await card.evaluate(
                            "el => el.scrollIntoView({ block: 'center', behavior: 'smooth' })"
                        )
                        await self.page.wait_for_timeout(500)

                        clickable_target = card.locator(
                            '.job-card-container:not([aria-hidden="true"])'
                        ).first

                        await clickable_target.click()
                        await self.page.wait_for_timeout(1500)

                        job_details_section = self.frame.locator(".jobs-details").first

                        already_applied = (
                            "Applied" in await job_details_section.inner_text()
                        )
                        if already_applied:
                            continue

                        job_title = await job_details_section.locator(
                            ".job-details-jobs-unified-top-card__job-title"
                        ).inner_text()
                        job_description = await job_details_section.locator(
                            "#job-details"
                        ).inner_text()

                        job_evaluation_result = await self.evaluate_job(
                            job_title=job_title,
                            job_description=job_description,
                            workflow_name="LinkedIn Job Evaluation",
                        )

                        if job_evaluation_result is None:
                            continue
                        run_result = job_evaluation_result.final_output.model_dump()

                        if run_result.get("match") is False:
                            continue

                        easy_apply_btn = self.frame.get_by_role(
                            "button", name=re.compile(r"easy apply", re.IGNORECASE)
                        )
                        ### INFO: Clicked easy apply btn - opens up the modal
                        await easy_apply_btn.nth(0).click()

                        try:
                            await self.page.wait_for_timeout(1500)
                            modal = self.frame.locator("[data-test-modal]")

                            next_btn = modal.get_by_role(
                                "button", name="Continue to next step"
                            )
                            if await next_btn.count() == 0:
                                await modal.get_by_role(
                                    "button", name="Submit application"
                                ).click()
                                await self.page.wait_for_timeout(1500)
                                await self.frame.get_by_role(
                                    "button", name="Not now"
                                ).click()
                                continue

                            able_to_answer_form = True
                            while await next_btn.count() == 1:
                                ### INFO: Clicked next button
                                await next_btn.click()
                                await self.page.wait_for_load_state("domcontentloaded")
                                await self.page.wait_for_timeout(1000)
                                has_errors = (
                                    await modal.locator(
                                        "[data-test-form-element-error-messages]"
                                    ).count()
                                    > 0
                                )

                                while has_errors:
                                    form_to_fill = (
                                        await self.frame.locator("[data-test-modal]")
                                        .locator("form")
                                        .nth(0)
                                        .evaluate("element => element.outerHTML")
                                    )
                                    fields_to_fill = linked_in_xtract_required_fields(
                                        html=form_to_fill, only_unanswered=True
                                    )

                                    success = await self._answer_form_questions(
                                        form_str=fields_to_fill, modal=modal
                                    )
                                    if not success:
                                        able_to_answer_form = False
                                        break
                                    await next_btn.click()
                                    await self.page.wait_for_load_state(
                                        "domcontentloaded"
                                    )
                                    await self.page.wait_for_timeout(1000)
                                    break
                                if not able_to_answer_form:
                                    break
                                review_application_btn = self.frame.locator(
                                    "[data-test-modal]"
                                ).get_by_role("button", name="Review your application")

                                if await review_application_btn.count() > 0:
                                    await review_application_btn.click()
                                    print(
                                        "Review application clicked 1 (TO TRIGGERR THE FORM TO SHOW THE FIELDS)"
                                    )
                                    break

                            if not able_to_answer_form:
                                print("Not able to answer form... breaking the loop")
                                continue
                            # REVIEW APPLICATIONS STAGE (PAST ALL THE NEXT)
                            form = (
                                self.frame.locator("[data-test-modal]")
                                .locator("form")
                                .filter(has_text="Additional Questions")
                            )
                            submit_application_btn = modal.get_by_role(
                                "button", name="Submit application"
                            )
                            if (
                                await form.count() == 0
                                and await submit_application_btn.count() == 1
                            ):
                                await submit_application_btn.click()
                                await self.page.wait_for_timeout(1000)
                                await self.page.keyboard.press("Escape")
                                continue
                            form_html_string = await form.evaluate(
                                "element => element.outerHTML"
                            )
                            print("form_html_string", form_html_string)
                            simplified_form_html = linked_in_xtract_required_fields(
                                html=form_html_string, only_unanswered=True
                            )
                            print(simplified_form_html)
                            successfull = await self._answer_form_questions(
                                form_str=simplified_form_html, modal=modal
                            )
                            # not_now_btn = self.frame.get_by_role("button", name="Not now")
                            if not successfull:
                                continue
                            await review_application_btn.click()
                            print(
                                "Review application clicked 2 - ACTUAL SUBMISSION OF THE FORM"
                            )
                            await self.page.wait_for_load_state("domcontentloaded")
                            await self.page.wait_for_timeout(1000)
                            has_errors = (
                                await modal.locator(
                                    "[data-test-form-element-error-messages]"
                                ).count()
                                > 0
                            )
                            able_to_answer_form = True
                            while has_errors:
                                form = (
                                    self.frame.locator("[data-test-modal]")
                                    .locator("form")
                                    .filter(has_text="Additional Questions")
                                )

                                form_html_string = await form.evaluate(
                                    "element => element.outerHTML"
                                )

                                simplified_form_html = linked_in_xtract_required_fields(
                                    form_html_string, only_unanswered=True
                                )
                                # note that this fn also handles the closing of the modal
                                successfull = await self._answer_form_questions(
                                    form_str=simplified_form_html, modal=modal
                                )
                                if not successfull:
                                    able_to_answer_form = False
                                    break
                                await review_application_btn.click()
                                print(
                                    "Review application clicked 3 - RETRY OF FILLING THE FORM"
                                )
                                await self.page.wait_for_timeout(1000)
                                break
                            if not able_to_answer_form:
                                print("LINE 449 UNABLE TO ANSWER FORM CONTINUING")
                                continue
                            checkbox = modal.locator("#follow-company-checkbox").first

                            if (
                                await checkbox.is_checked()
                                and await checkbox.count() == 1
                            ):
                                label = modal.locator(
                                    "label[for='follow-company-checkbox']"
                                ).first
                                await label.click()

                                assert not await checkbox.is_checked()
                            await submit_application_btn.click()
                            await self.page.wait_for_timeout(1500)
                            await self.page.keyboard.press("Escape")
                        except Exception as error:  # noqa: BLE001
                            print("Error occured ", error)
                            await self._handle_form_failure(modal=modal)
                            continue
                    next_page = self.frame.get_by_role("button", name="View next page")
                    if not await next_page.count() > 0:
                        break
                    await next_page.click()
                    await self.page.wait_for_timeout(1000)
        except Exception as error:  # noqa: BLE001
            print(error)
            await self.page.pause()

    async def _search_and_filter(
        self, keyword: str = "Software Engineer", listing_time: int | None = None
    ):
        basic_search = self.page.get_by_role("textbox", name="Title, skill or Company")
        if await basic_search.count() > 0:
            self.search = basic_search
        else:
            self.search = self.frame.get_by_role(
                "combobox", name="Search by title, skill, or"
            )

        await self.search.clear()
        await self.search.type(keyword, delay=50)
        await self.page.keyboard.press("Enter")
        await self.wait_for_timeout(2)

        if listing_time is not None:
            date_posted_btn = self.frame.get_by_role(
                "button", name="Date posted filter."
            )
            await date_posted_btn.click()
            match listing_time:
                case 30:
                    await (
                        self.page.locator('[data-testid="interop-iframe"]')
                        .content_frame.locator("label")
                        .filter(has_text="Past month Filter by Past")
                        .click()
                    )
                case 7:
                    await (
                        self.page.locator('[data-testid="interop-iframe"]')
                        .content_frame.locator("label")
                        .filter(has_text="Past week Filter by Past week")
                        .click()
                    )
                case 1:
                    await (
                        self.page.locator('[data-testid="interop-iframe"]')
                        .content_frame.locator("label")
                        .filter(has_text="Past 24 hours Filter by Past")
                        .click()
                    )
            await self.page.wait_for_timeout(500)
            await (
                self.page.locator('[data-testid="interop-iframe"]')
                .content_frame.get_by_role(
                    "button", name=re.compile(r"Show.*results", re.IGNORECASE)
                )
                .click()
            )
            await self.page.wait_for_timeout(500)
            await (
                self.page.locator('[data-testid="interop-iframe"]')
                .content_frame.get_by_role("radio", name="Easy Apply filter.")
                .click()
            )
            await self.page.wait_for_timeout(1000)
        await self.page.wait_for_timeout(2000)


if __name__ == "__main__":
    linkedin = LinkedIn()

    try:
        asyncio.run(linkedin.automate_job_search())
    finally:
        print("Execution finished")
