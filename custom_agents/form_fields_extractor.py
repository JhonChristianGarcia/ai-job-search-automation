from agents import Agent, ModelSettings, Runner, OpenAIChatCompletionsModel
import asyncio
from agents.extensions.models.litellm_model import LitellmModel
from pydantic import BaseModel, Field
from typing import List, Optional

GPT_MODEL = "gpt-4o-mini"

local_qwen_llm_model = LitellmModel(
    model="lm_studio/qwen/qwen3-4b-2507",
    api_key="lm-studio",
    base_url="http://127.0.0.1:1234/v1",
)

local_gemma_llm_model = LitellmModel(
    model="lm_studio/google/gemma-4-e2b",
    api_key="lm-studio",
    base_url="http://127.0.0.1:1234/v1",
)

local_qwen_coder_model = LitellmModel(
    model="lm_studio/qwen/qwen2.5-coder-3b-instruct",
    api_key="lm-studio",
    base_url="http://127.0.0.1:1234/v1",
)

macbook_pro_qwen_2_5_7b_coder_model = LitellmModel(
    model="lm_studio/qwen2.5-coder-7b-instruct",
    api_key="qwen2.5-coder-7b-instruct",
    base_url="http://192.168.0.154:1234/v1",
)

INSTRUCTIONS = """
    You are a Locator Agent.

    You will be provided with a raw HTML string representing a web page or form.
    And a list of fields that you need to extract

    Your task is to inspect the HTML and generate reliable Playwright locators for
    all user-interactable form fields.

    Your output MUST follow the provided structured output schema.
    ## NOTE: Extract EVERY interactable field present in the HTML, including
    fields that already have a selected/checked/filled value. A field
    already having a value does not mean it was accepted - it may need to
    be re-answered, so it must still be included in the output.
    ## OBJECTIVE

    For every relevant form field, identify:

    1. The human-readable name of the field.
    2. A Playwright locator that uniquely identifies the field.
    3. If the field has selectable options, identify ALL available options and generate
    a Playwright locator for each option.

    Relevant fields include, but are not limited to:

    - text inputs
    - email inputs
    - number inputs
    - telephone inputs
    - password inputs
    - textareas
    - select/dropdowns
    - radio buttons
    - checkboxes
    - multi-select fields
    - comboboxes
    - custom dropdowns
    - custom select components
    - date inputs
    - file inputs
    - other user-interactable form controls

    ## LOCATOR RULES

    Generate Playwright-compatible locator strings.

    Prefer selectors in this order:

    1. Stable unique IDs:
    #example-id

    2. Stable data attributes:
    [data-testid="example"]
    [data-test="example"]
    [data-test-automation="example"]

    3. Accessible selectors when they are reliable:
    get_by_role(...)
    get_by_label(...)
    get_by_placeholder(...)

    4. Other stable attributes.

    Avoid selectors based on:

    - dynamically generated class names
    - CSS classes that appear framework-generated
    - nth-child selectors
    - positional selectors
    - absolute XPath
    - deeply nested CSS selectors
    - styles
    - layout-dependent selectors

    Prefer the shortest selector that uniquely identifies the element.

    ## MULTIPLE LOCATORS

    For every field, the `locator` property should contain the BEST selector
    for identifying the field.

    If multiple reliable selectors exist, choose the most stable one as `locator`.

    Do not put alternative selectors into `locator`.

    ## OPTIONS

    If a field contains selectable options, the `options` array MUST contain
    EVERY available option.

    This applies to:

    - <select> options
    - radio buttons
    - checkboxes
    - multi-select options
    - dropdown menu items
    - combobox options
    - custom select components
    - any other selectable UI options

    Each option must contain:

    - `label`: the visible/textual name of the option
    - `locator`: a Playwright-compatible selector that uniquely identifies that option

    For example, if the HTML contains:

    <select id="employment-type">
        <option value="full-time">Full Time</option>
        <option value="part-time">Part Time</option>
        <option value="contract">Contract</option>
    </select>

    The output should conceptually be:

    {
        "field_name": "Employment Type",
        "locator": "#employment-type",
        "options": [
            {
                "label": "Full Time",
                "locator": "#employment-type option[value='full-time']"
            },
            {
                "label": "Part Time",
                "locator": "#employment-type option[value='part-time']"
            },
            {
                "label": "Contract",
                "locator": "#employment-type option[value='contract']"
            }
        ]
    }

    For radio buttons such as:

    <input type="radio" name="employment" value="full-time">
    <label>Full Time</label>

    <input type="radio" name="employment" value="part-time">
    <label>Part Time</label>

    Generate the field locator for the group and generate a locator for
    EVERY individual option.

    ## CUSTOM DROPDOWNS

    Be especially careful with custom dropdowns.

    A custom dropdown may not use a <select> element. It may consist of:

    - a button
    - a div
    - a combobox
    - a listbox
    - role="option"
    - aria attributes
    - data attributes

    Identify the actual interactive element that opens/selects the dropdown.

    Then identify all available options from the HTML.

    ## FIELD NAME

    Determine the field name using, in order of preference:

    1. Associated <label>
    2. aria-label
    3. aria-labelledby
    4. Associated label text
    5. Placeholder
    6. Nearby descriptive text
    7. Name attribute

    Do not use placeholder text as the field name if a better semantic label
    is available.
    
    ## VALIDATION MESSAGES

    You MUST inspect every form field for validation messages, constraints,
    and error/help text associated with that field.

    A validation message may appear as:

    - <span data-validation-message="true">...</span>
    - <div data-validation-message="true">...</div>
    - elements referenced by aria-describedby
    - elements with IDs ending in "-error"
    - elements with error/validation-related data attributes
    - visible text immediately associated with the input
    - HTML5 validation-related attributes such as:
    - required
    - min
    - max
    - minlength
    - maxlength
    - pattern
    - step

    If an explicit validation/error message is present in the HTML, extract
    its exact visible text into the `validation_message` property.

    For example:

    <input
        aria-describedby="numeric-error"
        id="experience"
        type="text"
    />
    <span data-validation-message="true">
        Enter a decimal number larger than 0.0
    </span>

    The output MUST contain:

    {
        "field_name": "Years of experience",
        "field_type": "text",
        "locator": "#experience",
        "options": [],
        "validation_message": "Enter a decimal number larger than 0.0"
    }

    If no explicit validation message exists, set:

    "validation_message": null

    Do NOT invent a validation message from the field name or input type.

    IMPORTANT:
    A validation message is metadata associated with the field. It is NOT
    a separate form field and MUST NOT be returned as a separate FormField.
    ## IMPORTANT

    Do not invent fields or options.

    Only return fields and options that can be identified from the provided HTML.

    Do not return buttons such as:

    - Submit
    - Cancel
    - Close
    - Next
    - Back

    unless they are actually part of a form field interaction.

    Do not return non-interactive elements.

    If a field cannot be given a reliable locator, still identify the field but
    use the best locator that can be derived from the HTML.

    ## OUTPUT

    Return ONLY the structured output defined by the Pydantic output schema.

    Do not return explanations, markdown, comments, or additional text.
"""


class FieldOption(BaseModel):
    label: str
    locator: str


class FormField(BaseModel):
    field_name: str
    field_type: str
    locator: str
    options: List[FieldOption] = Field(default_factory=list)
    validation_message: str | None = None


class AgentOutput(BaseModel):
    fields: List[FormField]


fields_extractor_agent = Agent(
    name="Fields Extractor Agent",
    instructions=INSTRUCTIONS,
    model=macbook_pro_qwen_2_5_7b_coder_model,
    output_type=AgentOutput,
    model_settings=ModelSettings(
        include_usage=True,
        timeout=10_000,
        temperature=0.0,
        extra_body={
            "enable_thinking": False,
        },
    ),
)


async def test_model():
    result = await Runner.run(
        fields_extractor_agent,
        """Required Fields: What's your expected monthly basic salary?, How would you rate your English language skills? - Please make a selection
,
    Form: <form class="_242qvk0"><div class="_242qvk0 pwyvhm59 pwyvhmhh pwyvhm75"><div class="_242qvk0 pwyvhm59 pwyvhmhh pwyvhm6t"><div class="_242qvk0 pwyvhm59 pwyvhmhh pwyvhm6t pwyvhmi9"><span class="_242qvk0 pwyvhm59 pwyvhmh5"><label for="question-PH_Q_7791_V_1"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511t _1ed78518 _1dgqso14"><strong class="_1ed78513">What's your expected monthly basic salary?</strong></span></label></span></div><div class="_242qvk0 pwyvhm59 pwyvhmhh pwyvhm6p"><div class="_242qvk0 pwyvhm5d pwyvhm65 pwyvhm59 _1ed785110  pwyvhm33"><select class="_242qvk0 _242qvk1 _242qvk6 _242qvk7 _242qvk8 _242qvkb pwyvhmp pwyvhmb9 pwyvhm65 _19d9r0r0 _9wr1370 _9wr1371 _1ed78510 _1ed78511 _1ed78511u _1ed7851e _1ed78511y _1ed785110  pwyvhm33" id="question-PH_Q_7791_V_1" name="questionnaire.PH_Q_7791_V_1" aria-describedby="_r_1k_"><option value="" disabled="" selected=""></option><option value="PH_Q_7791_V_1_A_7792">₱6K</option><option value="PH_Q_7791_V_1_A_7793">₱8K</option><option value="PH_Q_7791_V_1_A_7794">₱10K</option><option value="PH_Q_7791_V_1_A_7795">₱12K</option><option value="PH_Q_7791_V_1_A_7796">₱14K</option><option value="PH_Q_7791_V_1_A_7797">₱15K</option><option value="PH_Q_7791_V_1_A_7798">₱16K</option><option value="PH_Q_7791_V_1_A_7799">₱18K</option><option value="PH_Q_7791_V_1_A_7800">₱20K</option><option value="PH_Q_7791_V_1_A_7801">₱25K</option><option value="PH_Q_7791_V_1_A_7802">₱30K</option><option value="PH_Q_7791_V_1_A_7803">₱35K</option><option value="PH_Q_7791_V_1_A_7804">₱40K</option><option value="PH_Q_7791_V_1_A_7805">₱45K</option><option value="PH_Q_7791_V_1_A_7806">₱50K</option><option value="PH_Q_7791_V_1_A_7807">₱55K</option><option value="PH_Q_7791_V_1_A_7808">₱60K</option><option value="PH_Q_7791_V_1_A_7809">₱70K</option><option value="PH_Q_7791_V_1_A_7810">₱80K</option><option value="PH_Q_7791_V_1_A_7811">₱100K</option><option value="PH_Q_7791_V_1_A_7812">₱120K</option><option value="PH_Q_7791_V_1_A_7813">₱150K or more</option></select><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 pwyvhm3x pwyvhm3y"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm3p pwyvhm3u"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _9wr1375 pwyvhm3z pwyvhm44"></span><div class="_242qvk0 pwyvhm5h pwyvhm59 pwyvhmgl pwyvhmgx pwyvhmi pwyvhmo pwyvhmq pwyvhmj pwyvhmm"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511t _1ed7851e"><span class="_242qvk0 pwyvhm55"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 _1lndpbg0 pwyvhm55 pwyvhm5d _1h1zpem0 _1h1zpem2 _1h1zpem3 _1h1zpem4" aria-hidden="true"><path d="M20.7 7.3c-.4-.4-1-.4-1.4 0L12 14.6 4.7 7.3c-.4-.4-1-.4-1.4 0s-.4 1 0 1.4l8 8c.2.2.5.3.7.3s.5-.1.7-.3l8-8c.4-.4.4-1 0-1.4z"></path></svg></span></span></div></div><div class="_242qvk0 pwyvhm59 pwyvhmh1 pwyvhmi9" id="_r_1k_"><div class="_242qvk0 pwyvhmi5"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511m _1ed78516 _1dgqso14"><span class="_242qvk0 pwyvhm59"><span class="_242qvk0 pwyvhm4x pwyvhm9x pwyvhmi1 pwyvhmhx pwyvhmr"><span class="_242qvk0 pwyvhm55"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" focusable="false" fill="currentColor" class="_242qvk0 _1ed78511m pwyvhm55 pwyvhm5d _1h1zpem0 _1h1zpem2 _1h1zpem3 _1h1zpem4" aria-hidden="true"><path d="M12 22.997a2.977 2.977 0 0 1-2.121-.877h-.001L1.88 14.121c-.566-.564-.877-1.317-.877-2.121s.311-1.557.877-2.122L9.879 1.88c1.129-1.131 3.112-1.131 4.243 0l7.998 7.999c.566.564.877 1.317.877 2.121s-.311 1.557-.877 2.122l-7.999 7.998a2.975 2.975 0 0 1-2.121.877Zm0-19.994a.988.988 0 0 0-.706.29l-8 8c-.188.187-.291.438-.291.707s.103.52.291.706l7.999 8h.001c.373.375 1.039.375 1.412 0l8-7.999c.188-.187.291-.438.291-.707s-.103-.52-.29-.706l-8-8A.992.992 0 0 0 12 3.003Z"></path><circle cx="12" cy="16" r="1"></circle><path d="M11.978 13a1 1 0 0 1-1-1V8a1 1 0 1 1 2 0v4a1 1 0 0 1-1 1Z"></path></svg></span></span><span class="_242qvk0 pwyvhm4x pwyvhmr">Please make a selection</span></span></span></div></div></div></div><div class="_242qvk0 pwyvhm59 pwyvhmhh pwyvhm6t"><div class="_242qvk0 pwyvhm59 pwyvhmhh pwyvhm6t pwyvhmi9"><span class="_242qvk0 pwyvhm59 pwyvhmh5"><label for="question-PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511t _1ed78518 _1dgqso14"><strong class="_1ed78513">How many years' experience do you have as a Wordpress Developer?</strong></span></label></span></div><div class="_242qvk0 pwyvhm59 pwyvhmhh pwyvhm6p"><div class="_242qvk0 pwyvhm5d pwyvhm65 pwyvhm59 _1ed785110  pwyvhm33"><select class="_242qvk0 _242qvk1 _242qvk6 _242qvk7 _242qvk8 _242qvkb pwyvhmp pwyvhmb9 pwyvhm65 _19d9r0r0 _9wr1370 _9wr1371 _1ed78510 _1ed78511 _1ed78511u _1ed7851e _1ed78511y _1ed785110  pwyvhm33" id="question-PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4" name="questionnaire.PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4" aria-describedby="_r_1n_"><option value="" disabled="" selected=""></option><option value="PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4_A_2070FB8512B82F356DEC1C11FC139C8F_1">No experience</option><option value="PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4_A_2070FB8512B82F356DEC1C11FC139C8F_2">Less than 1 year</option><option value="PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4_A_2070FB8512B82F356DEC1C11FC139C8F_3">1 year</option><option value="PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4_A_2070FB8512B82F356DEC1C11FC139C8F_4">2 years</option><option value="PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4_A_2070FB8512B82F356DEC1C11FC139C8F_5">3 years</option><option value="PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4_A_2070FB8512B82F356DEC1C11FC139C8F_6">4 years</option><option value="PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4_A_2070FB8512B82F356DEC1C11FC139C8F_7">5 years</option><option value="PH_Q_2070FB8512B82F356DEC1C11FC139C8F_V_4_A_2070FB8512B82F356DEC1C11FC139C8F_8">More than 5 years</option></select><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 pwyvhm3x pwyvhm3y"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm3p pwyvhm3u"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _9wr1375 pwyvhm3z pwyvhm44"></span><div class="_242qvk0 pwyvhm5h pwyvhm59 pwyvhmgl pwyvhmgx pwyvhmi pwyvhmo pwyvhmq pwyvhmj pwyvhmm"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511t _1ed7851e"><span class="_242qvk0 pwyvhm55"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 _1lndpbg0 pwyvhm55 pwyvhm5d _1h1zpem0 _1h1zpem2 _1h1zpem3 _1h1zpem4" aria-hidden="true"><path d="M20.7 7.3c-.4-.4-1-.4-1.4 0L12 14.6 4.7 7.3c-.4-.4-1-.4-1.4 0s-.4 1 0 1.4l8 8c.2.2.5.3.7.3s.5-.1.7-.3l8-8c.4-.4.4-1 0-1.4z"></path></svg></span></span></div></div><div class="_242qvk0 pwyvhm59 pwyvhmh1 pwyvhmi9" id="_r_1n_"><div class="_242qvk0 pwyvhmi5"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511m _1ed78516 _1dgqso14"><span class="_242qvk0 pwyvhm59"><span class="_242qvk0 pwyvhm4x pwyvhm9x pwyvhmi1 pwyvhmhx pwyvhmr"><span class="_242qvk0 pwyvhm55"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" focusable="false" fill="currentColor" class="_242qvk0 _1ed78511m pwyvhm55 pwyvhm5d _1h1zpem0 _1h1zpem2 _1h1zpem3 _1h1zpem4" aria-hidden="true"><path d="M12 22.997a2.977 2.977 0 0 1-2.121-.877h-.001L1.88 14.121c-.566-.564-.877-1.317-.877-2.121s.311-1.557.877-2.122L9.879 1.88c1.129-1.131 3.112-1.131 4.243 0l7.998 7.999c.566.564.877 1.317.877 2.121s-.311 1.557-.877 2.122l-7.999 7.998a2.975 2.975 0 0 1-2.121.877Zm0-19.994a.988.988 0 0 0-.706.29l-8 8c-.188.187-.291.438-.291.707s.103.52.291.706l7.999 8h.001c.373.375 1.039.375 1.412 0l8-7.999c.188-.187.291-.438.291-.707s-.103-.52-.29-.706l-8-8A.992.992 0 0 0 12 3.003Z"></path><circle cx="12" cy="16" r="1"></circle><path d="M11.978 13a1 1 0 0 1-1-1V8a1 1 0 1 1 2 0v4a1 1 0 0 1-1 1Z"></path></svg></span></span><span class="_242qvk0 pwyvhm4x pwyvhmr">Please make a selection</span></span></span></div></div></div></div><div class="_242qvk0 pwyvhm59 pwyvhmhh pwyvhm6x"><div class="_242qvk0 pwyvhm59 pwyvhmhh pwyvhm6t pwyvhmi9"><span class="_242qvk0 pwyvhm59 pwyvhmh5"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511t _1ed78518 _1dgqso14"><strong class="_1ed78513">How would you rate your English language skills?</strong></span></span></div><div class="_242qvk0 pwyvhm5d"><div class="_242qvk0 pwyvhm59 pwyvhmi9"><input class="_242qvk0 _242qvk1 _242qvk6 _242qvk7 _242qvk8 _242qvkd pwyvhm5h pwyvhm8 pwyvhmh pwyvhm6 _116r4r44 _116r4r42" id="PH_Q_7545_V_5_A_7548" aria-checked="false" data-testid="PH_Q_7545_V_5_A_7548PH_Q_7545_V_5" type="checkbox" name="questionnaire.PH_Q_7545_V_5"><div class="_242qvk0 pwyvhmhx pwyvhm5d pwyvhm65 _116r4r45 _116r4r42 _1ed785110  pwyvhm33"><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _116r4r49 _1ed785111 _1ed785113 pwyvhm21 pwyvhm22"><div class="_242qvk0 pwyvhmn pwyvhmx pwyvhm5d _116r4r4c _116r4r4e"><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx pwyvhm6"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511t" aria-hidden="true"><path d="M18 11H6c-.6 0-1 .4-1 1s.4 1 1 1h12c.6 0 1-.4 1-1s-.4-1-1-1z"></path></svg></div><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx pwyvhm6"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511t" aria-hidden="true"><path d="M19.7 6.3c-.4-.4-1-.4-1.4 0L9 15.6l-3.3-3.3c-.4-.4-1-.4-1.4 0s-.4 1 0 1.4l4 4c.2.2.4.3.7.3s.5-.1.7-.3l10-10c.4-.4.4-1 0-1.4z"></path></svg></div></div></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm3x pwyvhm3y"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm3p pwyvhm3u"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _116r4r4b pwyvhm3z pwyvhm44"><div class="_242qvk0 pwyvhmn pwyvhmx pwyvhm5d _116r4r4c _116r4r4e"><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx pwyvhm6"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511s" aria-hidden="true"><path d="M18 11H6c-.6 0-1 .4-1 1s.4 1 1 1h12c.6 0 1-.4 1-1s-.4-1-1-1z"></path></svg></div><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511s" aria-hidden="true"><path d="M19.7 6.3c-.4-.4-1-.4-1.4 0L9 15.6l-3.3-3.3c-.4-.4-1-.4-1.4 0s-.4 1 0 1.4l4 4c.2.2.4.3.7.3s.5-.1.7-.3l10-10c.4-.4.4-1 0-1.4z"></path></svg></div></div></span></div><div class="_242qvk0 pwyvhmb5 pwyvhmi5"><div class="_242qvk0 pwyvhm59 _116r4r42 _116r4r46"><label class="_242qvk0 pwyvhm4 pwyvhm4x pwyvhmh _8f1g0v0" for="PH_Q_7545_V_5_A_7548"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511t _1ed78518 _1dgqso14">Speaks proficiently in a professional setting</span></label></div></div></div></div><div class="_242qvk0 pwyvhm5d"><div class="_242qvk0 pwyvhm59 pwyvhmi9"><input class="_242qvk0 _242qvk1 _242qvk6 _242qvk7 _242qvk8 _242qvkd pwyvhm5h pwyvhm8 pwyvhmh pwyvhm6 _116r4r44 _116r4r42" id="PH_Q_7545_V_5_A_7546" aria-checked="false" data-testid="PH_Q_7545_V_5_A_7546PH_Q_7545_V_5" type="checkbox" name="questionnaire.PH_Q_7545_V_5"><div class="_242qvk0 pwyvhmhx pwyvhm5d pwyvhm65 _116r4r45 _116r4r42 _1ed785110  pwyvhm33"><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _116r4r49 _1ed785111 _1ed785113 pwyvhm21 pwyvhm22"><div class="_242qvk0 pwyvhmn pwyvhmx pwyvhm5d _116r4r4c _116r4r4e"><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx pwyvhm6"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511t" aria-hidden="true"><path d="M18 11H6c-.6 0-1 .4-1 1s.4 1 1 1h12c.6 0 1-.4 1-1s-.4-1-1-1z"></path></svg></div><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx pwyvhm6"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511t" aria-hidden="true"><path d="M19.7 6.3c-.4-.4-1-.4-1.4 0L9 15.6l-3.3-3.3c-.4-.4-1-.4-1.4 0s-.4 1 0 1.4l4 4c.2.2.4.3.7.3s.5-.1.7-.3l10-10c.4-.4.4-1 0-1.4z"></path></svg></div></div></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm3x pwyvhm3y"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm3p pwyvhm3u"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _116r4r4b pwyvhm3z pwyvhm44"><div class="_242qvk0 pwyvhmn pwyvhmx pwyvhm5d _116r4r4c _116r4r4e"><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx pwyvhm6"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511s" aria-hidden="true"><path d="M18 11H6c-.6 0-1 .4-1 1s.4 1 1 1h12c.6 0 1-.4 1-1s-.4-1-1-1z"></path></svg></div><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511s" aria-hidden="true"><path d="M19.7 6.3c-.4-.4-1-.4-1.4 0L9 15.6l-3.3-3.3c-.4-.4-1-.4-1.4 0s-.4 1 0 1.4l4 4c.2.2.4.3.7.3s.5-.1.7-.3l10-10c.4-.4.4-1 0-1.4z"></path></svg></div></div></span></div><div class="_242qvk0 pwyvhmb5 pwyvhmi5"><div class="_242qvk0 pwyvhm59 _116r4r42 _116r4r46"><label class="_242qvk0 pwyvhm4 pwyvhm4x pwyvhmh _8f1g0v0" for="PH_Q_7545_V_5_A_7546"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511t _1ed78518 _1dgqso14">Writes proficiently in a professional setting</span></label></div></div></div></div><div class="_242qvk0 pwyvhm5d"><div class="_242qvk0 pwyvhm59 pwyvhmi9"><input class="_242qvk0 _242qvk1 _242qvk6 _242qvk7 _242qvk8 _242qvkd pwyvhm5h pwyvhm8 pwyvhmh pwyvhm6 _116r4r44 _116r4r42" id="PH_Q_7545_V_5_A_7547" aria-checked="false" data-testid="PH_Q_7545_V_5_A_7547PH_Q_7545_V_5" type="checkbox" name="questionnaire.PH_Q_7545_V_5"><div class="_242qvk0 pwyvhmhx pwyvhm5d pwyvhm65 _116r4r45 _116r4r42 _1ed785110  pwyvhm33"><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _116r4r49 _1ed785111 _1ed785113 pwyvhm21 pwyvhm22"><div class="_242qvk0 pwyvhmn pwyvhmx pwyvhm5d _116r4r4c _116r4r4e"><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx pwyvhm6"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511t" aria-hidden="true"><path d="M18 11H6c-.6 0-1 .4-1 1s.4 1 1 1h12c.6 0 1-.4 1-1s-.4-1-1-1z"></path></svg></div><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx pwyvhm6"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511t" aria-hidden="true"><path d="M19.7 6.3c-.4-.4-1-.4-1.4 0L9 15.6l-3.3-3.3c-.4-.4-1-.4-1.4 0s-.4 1 0 1.4l4 4c.2.2.4.3.7.3s.5-.1.7-.3l10-10c.4-.4.4-1 0-1.4z"></path></svg></div></div></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm3x pwyvhm3y"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm3p pwyvhm3u"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _116r4r4b pwyvhm3z pwyvhm44"><div class="_242qvk0 pwyvhmn pwyvhmx pwyvhm5d _116r4r4c _116r4r4e"><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx pwyvhm6"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511s" aria-hidden="true"><path d="M18 11H6c-.6 0-1 .4-1 1s.4 1 1 1h12c.6 0 1-.4 1-1s-.4-1-1-1z"></path></svg></div><div class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmx"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" xml:space="preserve" focusable="false" fill="currentColor" width="16" height="16" class="_242qvk0 pwyvhmp pwyvhmn pwyvhm4x _1ed78511s" aria-hidden="true"><path d="M19.7 6.3c-.4-.4-1-.4-1.4 0L9 15.6l-3.3-3.3c-.4-.4-1-.4-1.4 0s-.4 1 0 1.4l4 4c.2.2.4.3.7.3s.5-.1.7-.3l10-10c.4-.4.4-1 0-1.4z"></path></svg></div></div></span></div><div class="_242qvk0 pwyvhmb5 pwyvhmi5"><div class="_242qvk0 pwyvhm59 _116r4r42 _116r4r46"><label class="_242qvk0 pwyvhm4 pwyvhm4x pwyvhmh _8f1g0v0" for="PH_Q_7545_V_5_A_7547"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511t _1ed78518 _1dgqso14">Limited proficiency</span></label></div></div></div></div><div class="_242qvk0 pwyvhm59 pwyvhmh1 pwyvhmi9" id="PH_Q_7545_V_5-message"><div class="_242qvk0 pwyvhmi5"><span class="_242qvk0 pwyvhm4x _1ed78510 _1ed78511 _1ed78511m _1ed78516 _1dgqso14"><span class="_242qvk0 pwyvhm59"><span class="_242qvk0 pwyvhm4x pwyvhm9x pwyvhmi1 pwyvhmhx pwyvhmr"><span class="_242qvk0 pwyvhm55"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" focusable="false" fill="currentColor" class="_242qvk0 _1ed78511m pwyvhm55 pwyvhm5d _1h1zpem0 _1h1zpem2 _1h1zpem3 _1h1zpem4" aria-hidden="true"><path d="M12 22.997a2.977 2.977 0 0 1-2.121-.877h-.001L1.88 14.121c-.566-.564-.877-1.317-.877-2.121s.311-1.557.877-2.122L9.879 1.88c1.129-1.131 3.112-1.131 4.243 0l7.998 7.999c.566.564.877 1.317.877 2.121s-.311 1.557-.877 2.122l-7.999 7.998a2.975 2.975 0 0 1-2.121.877Zm0-19.994a.988.988 0 0 0-.706.29l-8 8c-.188.187-.291.438-.291.707s.103.52.291.706l7.999 8h.001c.373.375 1.039.375 1.412 0l8-7.999c.188-.187.291-.438.291-.707s-.103-.52-.29-.706l-8-8A.992.992 0 0 0 12 3.003Z"></path><circle cx="12" cy="16" r="1"></circle><path d="M11.978 13a1 1 0 0 1-1-1V8a1 1 0 1 1 2 0v4a1 1 0 0 1-1 1Z"></path></svg></span></span><span class="_242qvk0 pwyvhm4x pwyvhmr">Please make a selection</span></span></span></div></div></div><div class="_242qvk0 pwyvhm59 pwyvhmh5 pwyvhmgl pwyvhmhd"><div class="_242qvk0 pwyvhmi1 pwyvhmhx"><button class="_242qvk0 _242qvk7 _242qvk8 pwyvhm59 pwyvhmp pwyvhm65 pwyvhmh _1mbd6o0" type="button" data-testid="continue-button"><span class="_242qvk0 pwyvhm65 pwyvhmp pwyvhm5d pwyvhm59 pwyvhmgl pwyvhmgx pwyvhmid pwyvhm4 _1mbd6o5 _1mbd6o2 _1mbd6o7 _1ed785111 _1ed785113 pwyvhm21 pwyvhm22"><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _1mbd6o4 _1ed785111 _1ed785113 pwyvhm25 pwyvhm26"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _1mbd6o3 _1ed785111 _1ed785113 pwyvhm23 pwyvhm24"></span><span class="_242qvk0 pwyvhmax pwyvhm9t pwyvhm5d pwyvhm59 pwyvhmgx pwyvhmi5 pwyvhmhp pwyvhm0 pwyvhmi _1mbd6oa"><span class="_242qvk0 pwyvhm4x pwyvhmid _1ed78510 _1ed78512 _1ed78511t _1ed78518 _1dgqso14">Continue<span class="_242qvk0 pwyvhmb1 _1dr00xr0 x90lbj3f" aria-hidden="true">⁠<span class="_242qvk0 pwyvhm55"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" focusable="false" fill="currentColor" class="_242qvk0 vcevw40 pwyvhm55 pwyvhm5d _1h1zpem0 _1h1zpem2 _1h1zpem3 _1h1zpem4 vcevw43" aria-hidden="true"><path d="m11.293 4.293-7 7a1 1 0 1 0 1.414 1.414L11 7.414V19a1 1 0 1 0 2 0V7.414l5.293 5.293a1 1 0 1 0 1.414-1.414l-7-7a1 1 0 0 0-1.414 0Z"></path></svg></span></span></span></span></span></button></div><div class="_242qvk0 x90lbj2d x90lbj3h"><div class="_242qvk0 pwyvhm5d"><button class="_242qvk0 _242qvk7 _242qvk8 pwyvhm59 pwyvhmp pwyvhm65 pwyvhmh _1mbd6o0" type="button" data-testid="back-button"><span class="_242qvk0 pwyvhm65 pwyvhmp pwyvhm5d pwyvhm59 pwyvhmgl pwyvhmgx pwyvhmid pwyvhm4 _1mbd6o5 _1mbd6o2 _1mbd6o7 _1mbd6o9"><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _1mbd6o4 _1mbd6of _1ed785110 _1ed785113 pwyvhm2b pwyvhm2m"></span><span class="_242qvk0 pwyvhmj pwyvhmk pwyvhml pwyvhmm pwyvhm5h pwyvhmi pwyvhm65 pwyvhmx pwyvhm6 _1mbd6o3 _1mbd6og _1ed785110 _1ed785113 pwyvhm29 pwyvhm2k"></span><span class="_242qvk0 pwyvhmb9 pwyvhma5 pwyvhm5d pwyvhm59 pwyvhmgx pwyvhmi5 pwyvhmhp pwyvhm0 pwyvhmi _1mbd6oa"><span class="_242qvk0 pwyvhm4x pwyvhmid _1ed78510 _1ed78512 _1ed78511s _1ed78518 _1dgqso14"><span class="_242qvk0 pwyvhm9x _1dr00xr0" aria-hidden="true"><span class="_242qvk0 pwyvhm55"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" focusable="false" fill="currentColor" class="_242qvk0 vcevw40 pwyvhm55 pwyvhm5d _1h1zpem0 _1h1zpem2 _1h1zpem3 _1h1zpem4 vcevw43 vcevw44" aria-hidden="true"><path d="m11.293 4.293-7 7a1 1 0 1 0 1.414 1.414L11 7.414V19a1 1 0 1 0 2 0V7.414l5.293 5.293a1 1 0 1 0 1.414-1.414l-7-7a1 1 0 0 0-1.414 0Z"></path></svg></span>⁠</span>Back</span></span></span></button></div></div></div></div></form>
                              """,
    )
    print(result.final_output.model_dump())


if __name__ == "__main__":
    asyncio.run(test_model())
