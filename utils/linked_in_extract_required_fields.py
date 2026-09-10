import re

from bs4 import BeautifulSoup, Tag


def linked_in_xtract_required_fields(
    html: str,
    required_fields: list[str] | None = None,
    only_unanswered: bool = False,
) -> str:
    """
    Extract only required form fields from LinkedIn-style HTML.

    Output contains:
    - The actual question/field label
    - Required controls
    - Locator-relevant attributes
    - Radio/checkbox options
    - Select options
    - Validation messages when present

    It intentionally removes:
    - Layout wrappers
    - Styling classes
    - Decorative elements
    - Unrelated form content

    When ``only_unanswered`` is True, fields whose container has no active
    LinkedIn validation message are dropped. A field's ``value``/``checked``/
    ``selected`` HTML attributes don't reflect what was actually typed or
    selected (those are live DOM properties, not attributes, so they never
    show up in an outerHTML snapshot), so "already answered" can't be
    detected that way. LinkedIn's own client-side validation is reliable
    though: after clicking Next/Review, it populates
    ``[data-test-form-element-error-messages]`` next to exactly the fields
    still missing/invalid, so that's the signal used here.
    """

    soup = BeautifulSoup(html, "html.parser")

    output = BeautifulSoup("<form></form>", "html.parser")
    output_form = output.form

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip().lower()

    def copy_attributes(source: Tag, target: Tag) -> None:
        """
        Copy only attributes useful for locating/interacting with
        the control through Playwright.
        """
        allowed = {
            "id",
            "name",
            "type",
            "value",
            "placeholder",
            "inputmode",
            "aria-label",
            "aria-labelledby",
            "aria-describedby",
            "aria-required",
            "aria-autocomplete",
            "aria-activedescendant",
            "aria-expanded",
            "role",
            "required",
            "checked",
            "disabled",
            "data-testid",
            "data-automation",
            "data-test-form-element",
            "data-test-text-selectable-option__input",
        }

        for attr, value in source.attrs.items():
            if attr in allowed:
                target[attr] = value

    def is_required_control(control: Tag) -> bool:
        """
        Determine whether THIS control is required.

        Do not walk arbitrary ancestors looking for required markers.
        Doing so can incorrectly mark unrelated controls as required.
        """
        if control.has_attr("required"):
            return True

        aria_required = control.get("aria-required", "")
        if isinstance(aria_required, list):
            aria_required = " ".join(aria_required)

        return str(aria_required).strip().lower() == "true"

    def find_field_container(control: Tag) -> Tag:
        """
        Find the logical LinkedIn form field.

        LinkedIn normally provides:
            div[data-test-form-element]

        This is especially important for radio groups, where several
        inputs belong to one question.
        """
        container = control.find_parent(attrs={"data-test-form-element": True})

        if container:
            return container

        # Fallbacks for non-LinkedIn / slightly different markup.
        for parent in control.parents:
            if not isinstance(parent, Tag):
                continue

            if parent.name in {"fieldset", "form"}:
                if parent.name == "fieldset":
                    return parent
                break

            # Stop before accidentally consuming a huge form section.
            if parent.name in {"section", "article"}:
                break

        return control.parent if isinstance(control.parent, Tag) else control

    def find_question(container: Tag, controls: list[Tag]) -> str:
        """
        Find the actual question.

        Priority is deliberate:

        1. <legend> for radio/checkbox groups
        2. LinkedIn-specific question/title selectors
        3. <label for="control-id">
        4. Normal field label
        5. Avoid option labels entirely
        """

        # --------------------------------------------------------------
        # 1. Radio / checkbox groups
        # --------------------------------------------------------------
        #
        # LinkedIn:
        #
        # <fieldset>
        #   <legend>
        #       <span ...title>QUESTION</span>
        #   </legend>
        #
        # This MUST be checked before generic <label>.
        #
        legend = container.find("legend")

        if legend:
            # Prefer LinkedIn's explicit question selector.
            title = legend.select_one(
                "[data-test-form-builder-radio-button-form-component__title]"
            )

            if title:
                text = title.get_text(" ", strip=True)
                if text:
                    return text

            # Fallback: legend text, excluding "Required".
            legend_copy = BeautifulSoup(
                str(legend),
                "html.parser",
            )

            for hidden in legend_copy.select(
                ".visually-hidden, "
                "[data-test-form-builder-radio-button-form-component__required]"
            ):
                hidden.decompose()

            text = legend_copy.get_text(" ", strip=True)

            if text:
                return text

        # --------------------------------------------------------------
        # 2. LinkedIn-specific field titles
        # --------------------------------------------------------------

        selectors = [
            "[data-test-text-entity-list-form-title]",
            "[data-test-single-typeahead-entity-form-title]",
            "[data-test-form-builder-radio-button-form-component__title]",
        ]

        for selector in selectors:
            element = container.select_one(selector)

            if element:
                text = element.get_text(" ", strip=True)

                if text:
                    return text

        # --------------------------------------------------------------
        # 3. Match label using the control's ID
        # --------------------------------------------------------------

        for control in controls:
            control_id = control.get("id")

            if control_id:
                label = container.find(
                    "label",
                    attrs={"for": control_id},
                )

                if label:
                    text = label.get_text(" ", strip=True)

                    if text:
                        return text

        # --------------------------------------------------------------
        # 4. Generic field label
        # --------------------------------------------------------------
        #
        # IMPORTANT:
        # Never use option labels here.
        #
        # LinkedIn radio options look like:
        #
        # <label data-test-text-selectable-option__label="Yes">
        #
        # Those are answers, not questions.
        #

        for label in container.find_all("label"):
            if label.has_attr("data-test-text-selectable-option__label"):
                continue

            if label.find_parent(attrs={"data-test-text-selectable-option": True}):
                continue

            text = label.get_text(" ", strip=True)

            if text:
                return text

        return ""

    def find_validation_message(container: Tag) -> str:
        """
        Extract an existing LinkedIn validation/error message.
        """
        error = container.select_one("[data-test-form-element-error-messages]")

        if not error:
            return ""

        message = error.select_one(".artdeco-inline-feedback__message")

        if message:
            return message.get_text(" ", strip=True)

        text = error.get_text(" ", strip=True)

        return text

    # ------------------------------------------------------------------
    # Find all required controls
    # ------------------------------------------------------------------

    required_controls = []

    for control in soup.find_all(["input", "textarea", "select"]):
        if is_required_control(control):
            required_controls.append(control)

    # ------------------------------------------------------------------
    # Group controls by logical field container
    # ------------------------------------------------------------------

    field_groups = []
    seen_containers = set()

    for control in required_controls:
        container = find_field_container(control)

        container_key = id(container)

        if container_key not in seen_containers:
            seen_containers.add(container_key)

            field_groups.append(
                {
                    "container": container,
                    "controls": [],
                }
            )

        for group in field_groups:
            if id(group["container"]) == container_key:
                group["controls"].append(control)
                break

    # ------------------------------------------------------------------
    # Optional required_fields filtering
    # ------------------------------------------------------------------

    normalized_required_fields = {
        normalize(field) for field in (required_fields or []) if normalize(field)
    }

    # ------------------------------------------------------------------
    # Build simplified output
    # ------------------------------------------------------------------

    for group in field_groups:
        container = group["container"]
        controls = group["controls"]

        question = find_question(
            container,
            controls,
        )

        # If required_fields was supplied, only retain matching fields.
        if normalized_required_fields:
            normalized_question = normalize(question)

            if not any(
                required == normalized_question
                or required in normalized_question
                or normalized_question in required
                for required in normalized_required_fields
            ):
                continue

        validation_message = find_validation_message(container)

        # A field with no active validation message has already been
        # answered (or was never required in the first place).
        if only_unanswered and not validation_message:
            continue

        # --------------------------------------------------------------
        # Create field container
        # --------------------------------------------------------------

        field_output = output.new_tag(
            "div",
            attrs={"data-required": "true"},
        )

        # --------------------------------------------------------------
        # Add question
        # --------------------------------------------------------------

        if question:
            label_output = output.new_tag("label")
            label_output.string = question
            field_output.append(label_output)

        # --------------------------------------------------------------
        # Determine field type
        # --------------------------------------------------------------

        control_types = {
            (control.get("type") or "").lower()
            for control in controls
            if control.name == "input"
        }

        has_radio = "radio" in control_types
        has_checkbox = "checkbox" in control_types
        has_select = any(control.name == "select" for control in controls)

        # --------------------------------------------------------------
        # Radio / checkbox
        # --------------------------------------------------------------

        if has_radio or has_checkbox:
            # For grouped options, include ALL options from the
            # logical container, not only the required input list.
            #
            # This prevents losing "No" if only one option happens
            # to carry the required marker.
            group_controls = container.find_all(["input"])

            seen_control_ids = set()

            for control in group_controls:
                control_type = (control.get("type") or "").lower()

                if control_type not in {
                    "radio",
                    "checkbox",
                }:
                    continue

                control_id = control.get("id")

                if control_id and control_id in seen_control_ids:
                    continue

                if control_id:
                    seen_control_ids.add(control_id)

                input_output = output.new_tag("input")

                copy_attributes(
                    control,
                    input_output,
                )

                field_output.append(input_output)

                # ------------------------------------------------------
                # Find the option label
                # ------------------------------------------------------

                option_label = None

                if control_id:
                    option_label = container.find(
                        "label",
                        attrs={"for": control_id},
                    )

                if option_label is None:
                    option_value = control.get("value")

                    if option_value:
                        option_label = container.find(
                            "label",
                            string=lambda text: (
                                normalize(text) == normalize(option_value)
                                if text
                                else False
                            ),
                        )

                if option_label:
                    option_text = option_label.get_text(
                        " ",
                        strip=True,
                    )

                    if option_text:
                        option_output = output.new_tag(
                            "span",
                            attrs={"data-option-label": "true"},
                        )

                        option_output.string = option_text
                        field_output.append(option_output)

        # --------------------------------------------------------------
        # Select
        # --------------------------------------------------------------

        elif has_select:
            # Only process the actual select controls.
            for control in controls:
                if control.name != "select":
                    continue

                select_output = output.new_tag("select")

                copy_attributes(
                    control,
                    select_output,
                )

                # Preserve every option because the agent needs the
                # actual valid choices.
                for option in control.find_all(
                    "option",
                    recursive=False,
                ):
                    option_output = output.new_tag("option")

                    copy_attributes(
                        option,
                        option_output,
                    )

                    if option.has_attr("value"):
                        option_output["value"] = option["value"]

                    option_text = option.get_text(
                        " ",
                        strip=True,
                    )

                    if option_text:
                        option_output.string = option_text

                    select_output.append(option_output)

                field_output.append(select_output)

        # --------------------------------------------------------------
        # Text / number / other inputs
        # --------------------------------------------------------------

        else:
            for control in controls:
                input_output = output.new_tag(control.name)

                copy_attributes(
                    control,
                    input_output,
                )

                if control.name == "textarea":
                    input_output.string = control.get_text(
                        "",
                        strip=True,
                    )

                field_output.append(input_output)

        # --------------------------------------------------------------
        # Validation message
        # --------------------------------------------------------------

        if validation_message:
            validation_output = output.new_tag(
                "span",
                attrs={"data-validation-message": "true"},
            )

            validation_output.string = validation_message

            field_output.append(validation_output)

        output_form.append(field_output)

    return str(output)
