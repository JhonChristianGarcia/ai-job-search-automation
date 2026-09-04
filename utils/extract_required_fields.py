import re

from bs4 import BeautifulSoup, Tag


def extract_required_fields(
    html: str,
    required_fields: list[str],
) -> str:
    """
    Extract only the required form fields.

    Output contains:
        - Question text
        - Input/select/textarea controls
        - Option text
        - Locator-relevant attributes

    Everything else is discarded.
    """

    soup = BeautifulSoup(html, "html.parser")

    def normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().casefold()

    def normalize_required(text: str) -> str:
     
        text = re.sub(
            r"\s*-\s*Please make a selection\s*$",
            "",
            text,
            flags=re.IGNORECASE,
        )

        return normalize(text)

    required = {
        normalize_required(field)
        for field in required_fields
    }

    locator_attrs = {
        "id",
        "name",
        "type",
        "value",
        "placeholder",
        "aria-label",
        "aria-labelledby",
        "data-testid",
        "data-automation",
        "role",
        "for",
        "checked",
        "disabled",
    }
    question_element = None
    question_text = None

    for element in soup.find_all(["strong", "legend", "label"]):
        text = element.get_text(" ", strip=True)

        if not text:
            continue

        normalized = normalize(text)

        for required_question in required:

            if normalized == required_question:
                question_element = element
                question_text = text
                break

        if question_element:
            break

    if not question_element:
        return "<form></form>"


    container = question_element

    while container.parent and isinstance(container.parent, Tag):

        parent = container.parent

        controls = parent.find_all(
            ["input", "select", "textarea"],
        )

        if controls:
            container = parent

       
            if len(controls) >= 1:
                break

        container = parent


    output = BeautifulSoup("<form></form>", "html.parser")
    form = output.form

    field = output.new_tag("div")

    question = output.new_tag("label")
    question.string = question_text
    field.append(question)


    controls = container.find_all(
        ["input", "select", "textarea"]
    )

    seen = set()

    for control in controls:

        key = (
            control.get("id")
            or control.get("name")
            or str(control)
        )

        if key in seen:
            continue

        seen.add(key)

        new_control = output.new_tag(control.name)

        for attr in locator_attrs:

            if attr not in control.attrs:
                continue

            value = control.attrs[attr]

            if isinstance(value, list):
                value = " ".join(value)

            new_control[attr] = value

        if control.name == "select":

            for option in control.find_all("option"):

                new_option = output.new_tag("option")

                if option.get("value") is not None:
                    new_option["value"] = option["value"]

                if option.get("disabled") is not None:
                    new_option["disabled"] = ""

                if option.get("selected") is not None:
                    new_option["selected"] = ""

                new_option.string = option.get_text(
                    " ",
                    strip=True,
                )

                new_control.append(new_option)

        elif control.name == "textarea":

            new_control.string = control.get_text(
                strip=True
            )

        field.append(new_control)


        control_id = control.get("id")

        if control_id:

            label = container.find(
                "label",
                attrs={"for": control_id},
            )

            if label:

                label_text = label.get_text(
                    " ",
                    strip=True,
                )

                if label_text:

                    option = output.new_tag("span")
                    option.string = label_text
                    field.append(option)

    form.append(field)

    return str(output)
