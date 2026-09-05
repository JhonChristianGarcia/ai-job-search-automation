import re

from bs4 import BeautifulSoup, Tag


def extract_all_form_fields(html: str) -> str:
    """
    Extracts all form fields, input controls, labels, and relevant
    helper/error text from the HTML.

    Discards classes, layout wrappers, SVGs, and unnecessary clutter.
    """

    soup = BeautifulSoup(html, "html.parser")

    locator_attrs = {
        "id",
        "name",
        "type",
        "value",
        "placeholder",
        "aria-label",
        "aria-labelledby",
        "aria-describedby",
        "data-testid",
        "data-automation",
        "role",
        "for",
        "checked",
        "disabled",
        "required",
        "min",
        "max",
        "step",
    }

    output = BeautifulSoup("<form></form>", "html.parser")
    form = output.form

    processed_control_keys = set()

    all_controls = soup.find_all(["input", "select", "textarea"])

    for control in all_controls:
        control_key = control.get("id") or control.get("name") or str(control)

        if control_key in processed_control_keys:
            continue

        field_div = output.new_tag("div")

        label_text = None
        control_id = control.get("id")

        if control_id:
            matching_label = soup.find(
                "label",
                attrs={"for": control_id},
            )

            if matching_label:
                label_text = matching_label.get_text(
                    " ",
                    strip=True,
                )

        if not label_text:
            container = control

            while container.parent and isinstance(container.parent, Tag):
                parent = container.parent

                if parent.name in ["form", "body"]:
                    break

                sibling_labels = parent.find_all(["label", "strong", "legend"])

                if sibling_labels:
                    label_text = sibling_labels[0].get_text(
                        " ",
                        strip=True,
                    )
                    break

                container = parent

        if label_text:
            label_text = re.sub(
                r"\s+",
                " ",
                label_text,
            ).strip()

            new_label = output.new_tag("label")
            new_label.string = label_text
            field_div.append(new_label)

        described_text = []

        aria_describedby = control.get(
            "aria-describedby",
            "",
        )

        for described_id in aria_describedby.split():
            described_element = soup.find(
                id=described_id,
            )

            if not described_element:
                continue

            text = described_element.get_text(
                " ",
                strip=True,
            )

            if text:
                text = re.sub(
                    r"\s+",
                    " ",
                    text,
                ).strip()

                described_text.append(text)

        if described_text:
            helper_div = output.new_tag("div")
            helper_div["data-context"] = " ".join(described_text)
            helper_div.string = " ".join(described_text)

            field_div.append(helper_div)

        new_control = output.new_tag(control.name)

        for attr in locator_attrs:
            if attr not in control.attrs:
                continue

            val = control.attrs[attr]

            if isinstance(val, list):
                val = " ".join(val)

            new_control[attr] = val

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
            new_control.string = control.get_text(strip=True)

        field_div.append(new_control)
        form.append(field_div)

        processed_control_keys.add(control_key)

    return str(output)
