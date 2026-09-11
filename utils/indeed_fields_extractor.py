import re

from bs4 import BeautifulSoup, Tag


def extract_all_form_fields(html: str) -> str:
    """
    Extract all form fields and relevant metadata into a simplified HTML
    representation suitable for an LLM.

    Preserves:
    - labels
    - stable locator attributes
    - aria-describedby relationships
    - validation/error messages
    - helper text
    - select options
    - current values
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

        # ---------------------------------------------------------
        # FIELD LABEL
        # ---------------------------------------------------------

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

        # Fallback: search parent containers.
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

        # ---------------------------------------------------------
        # ARIA DESCRIBEDBY
        # ---------------------------------------------------------

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

            if not text:
                continue

            text = re.sub(
                r"\s+",
                " ",
                text,
            ).strip()

            context_div = output.new_tag("div")

            # IMPORTANT:
            # Preserve the referenced ID.
            context_div["id"] = described_id

            described_id_lower = described_id.lower()

            # Explicitly classify the metadata.
            if any(
                keyword in described_id_lower
                for keyword in (
                    "error",
                    "validation",
                    "invalid",
                )
            ):
                context_div["data-validation-message"] = "true"

            elif "helper" in described_id_lower:
                context_div["data-helper-text"] = "true"

            else:
                context_div["data-describedby"] = "true"

            context_div.string = text

            field_div.append(context_div)

        # ---------------------------------------------------------
        # CONTROL
        # ---------------------------------------------------------

        new_control = output.new_tag(control.name)

        for attr in locator_attrs:
            if attr not in control.attrs:
                continue

            val = control.attrs[attr]

            if isinstance(val, list):
                val = " ".join(val)

            new_control[attr] = val

        # ---------------------------------------------------------
        # SELECT OPTIONS
        # ---------------------------------------------------------

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

        # ---------------------------------------------------------
        # TEXTAREA VALUE
        # ---------------------------------------------------------

        elif control.name == "textarea":
            new_control.string = control.get_text(strip=True)

        field_div.append(new_control)
        form.append(field_div)

        processed_control_keys.add(control_key)

    return str(output)
