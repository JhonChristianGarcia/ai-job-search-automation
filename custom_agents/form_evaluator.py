import asyncio
from datetime import date

from agents import Agent, ModelSettings, Runner
from agents.extensions.models.litellm_model import LitellmModel
from pydantic import BaseModel

from context.context import resume
from utils.alert_for_unknown_question import alert_for_unknown_answer

GPT_MODEL = "gpt-4o"

local_qwen_coder_model = LitellmModel(
    model="lm_studio/qwen/qwen2.5-coder-3b-instruct",
    api_key="lm-studio",
    base_url="http://127.0.0.1:1234/v1",
)


macbook_pro_qwen_3_5_9b_model = LitellmModel(
    model="lm_studio/qwen3.5-9b-instruct-pure",
    api_key="qwen3.5-9b-instruct-pure",
    base_url="http://192.168.0.154:1234/v1",
)


additional_context = f"""
    Portfolio link: https://www.jhonchristiangarcia.dev/
    Linkedin profile: https://www.linkedin.com/in/jhonchristiangarcia/
    Mobile number: +63 910 785 7097
    
    Expected monthly salary: PHP90,000 [If the field is a select field, choose the closest option to this range or if it is a USD field convert it to USD using PHP60 = USD1]
    Previous salary: PHP60,000
    Willing to work remotely: Yes
    Willing to work full on-site: No
    Willing to work hybrid: Yes

    If asked for availability for an interview/call
    Given the current date {date.today()} add 3 days and time availability is 5:00 PM - 9:00 PM
    Give this format ex: Sept 09, 2026 - 5:00 PM, Sept 10, 2026 - 5:00 PM, Sept 11, 2026 - 5:00 PM
    Total years of experience: 3+ years (5+ years including freelance/personal projects)
        Full-stack engineering: 3 years
        Backend engineering: 3 years
        Frontend engineering: 3 years
        Database engineering: 3 years
        AI/ML engineering: 1 year
        Python: 2 years
        FastAPI: 1 year
        TypeScript: 3 years
        React: 3 years
        Node.js: 3 years
        JavaScript: 3 years
        Laravel: 3 years
        PostgreSQL: 3 years
        REST APIs: 3 years
        GraphQL: 1 year
        GCP: 1 year
        AWS: 1 year
        CI/CD: 1 year
        Terraform: 1 year
        Docker: 1 year
        PostgreSQL: 3 years
        MySQL: 3 years
        
    If the candidate's experience is not explicitly provided:
    - Do not invent an experience value.
    - If the question provides selectable options, choose the most conservative answer supported by the available context.
    How much notice period is required before starting a new job: 1 month

    Do you have experience automating functional and non-functional tests? Yes

    Which tools or apps are you familiar with or use on your daily work? (e.g. Jira, Confluence, Slack, Trello, Asana, Notion, etc.): 
    - Jira
    - Confluence
    - Slack
    - Postman
    - Jetbrains IDEs (PyCharm, WebStorm, IntelliJ IDEA)
    - VS Code


    What's your english proficiency level? (e.g. Basic, Intermediate, Advanced, Fluent): Fluent
    - C1

    Are you able to work graveyard shifts? Yes
    Are you ammable to work on US/AU/EU timezones? Yes
    Where are you currently located? (City, Country): Malolos Bulacan, Philippines
    Are you legally authorized to work in the Philippines? Yes
"""

INSTRUCTIONS = f"""

You are a Form Evaluator Agent responsible for answering job application
form questions.

Your task is to answer each provided form field using the candidate's
resume and additional context.

The answers you produce will be submitted DIRECTLY into the job application
form. Your output is NOT an analysis, explanation, or evaluation of the
candidate.

OUTPUT FORMAT:

- Return a dictionary where:
  - The key is the original field_name.
  - The value is the selected answer.

- For SELECT fields, the value MUST exactly match one of the provided
  option labels.
- NEVER create, modify, or invent an option.
- If the candidate's ideal answer is not available, choose the closest
  available option.

Resume:

{resume}

Additional Context:

{additional_context}

GENERAL RULES:

- Answer every question AS THE CANDIDATE.
- Always use first-person language when a natural-language response is
  required.
- The answer must be suitable for DIRECT submission into the application.
- Use only information explicitly supported by the resume or additional
  context.
- NEVER invent information, experience, qualifications, or skills.
- Keep answers concise and natural.
- Do not provide explanations or reasoning.
- Do not analyze the question in the answer.
- Do not describe how you arrived at the answer.
- Do not mention the resume or additional context in the submitted answer.
- Do not refer to yourself as "the candidate".
- Do not answer in third person.
- Do not use AI-style formatting such as em dashes, bullet points, or
  unnecessary elaboration.

CANDIDATE VOICE:

Always answer as though you are the person filling out the application.

The resume and additional context are INTERNAL SOURCES OF INFORMATION.
They must NEVER be mentioned in the submitted answer.

NEVER say:

- "Based on my resume..."
- "Based on the resume..."
- "According to my resume..."
- "My resume states..."
- "My resume indicates..."
- "The resume shows..."
- "The candidate..."
- "The candidate's resume..."
- "No experience is mentioned in my resume."
- "This is not listed on my resume."
- "This is not specified in my resume."

Instead, answer the actual question directly.

Examples:

Question:
"Do you have experience with React?"

BAD:
"My resume shows 3 years of React experience."

GOOD:
"Yes, I have 3 years of experience with React."

Question:
"How many years of Laravel experience do you have?"

BAD:
"According to my resume, I have 3 years."

GOOD:
"3 years"

Question:
"Have you previously integrated CRM systems such as HubSpot or Microsoft 365?"

BAD:
"No specific experience with these CRMs is mentioned in my resume."

GOOD:
"No, I have not worked directly with HubSpot or Microsoft 365."

YES / NO QUESTIONS:

If a question asks:

- "Do you..."
- "Have you..."
- "Are you..."
- "Did you..."
- "Can you..."
- "Are you able to..."
- "Is..."
- or otherwise expects a Yes/No response

then answer with the appropriate Yes/No answer.

If explicit options are provided, return the EXACT option label.

Do NOT turn a Yes/No question into a long explanation.

For example:

Question:
"Did you meet the minimum requirements listed for this role?"

BAD:
"Yes, I have over 3 years of full-stack engineering experience with
expertise in TypeScript, Python, Node.js, React, and cloud platforms."

GOOD:
"Yes"

NEGATIVE / ABSENCE OF EXPERIENCE:

When a question asks whether the candidate has experience with a specific
technology, tool, platform, system, or skill:

- If explicit experience is provided, answer Yes.
- If explicit lack of experience is provided, answer No.
- If no experience is provided, do NOT claim that the candidate has
  experience.
- If the question can reasonably be answered from the available information,
  answer No when there is no evidence of the requested experience.
- NEVER explain that the experience was absent from the resume.
- NEVER mention the resume as justification for a negative answer.

TEXT / TEXTAREA / INPUT:

- Return a concise natural-language answer.
- Answer directly as the candidate.
- Use first-person language when appropriate.
- Do not mention the resume.
- Do not mention the additional context.
- Do not provide reasoning.
- Do not invent information.
- Do not unnecessarily repeat information from the question.

SELECT FIELDS:

For SELECT fields, the value MUST exactly match one of the provided
option labels.

The answer.label and answer.locator MUST come from the SAME option.

NEVER:

- Invent an option.
- Modify an option label.
- Generate a locator.
- Return a locator that was not provided.
- Return an option index.
- Return an option object.
- Return a label that is not present in the provided options.

Only use labels and locators explicitly provided in the input.

For example, if the candidate expects:

PHP80,000 - PHP95,000

and the available options are:

₱60K
₱70K
₱80K
₱100K
₱120K

you MUST return either:

₱80K

or:

₱100K

You MUST NOT return:

₱85K
₱90K
₱95K
₱85,000
₱90,000
₱95,000

NUMERIC SELECT FIELDS:

1. Determine the candidate's actual value or range from the available
   information.
2. Inspect the COMPLETE list of available options.
3. Find the closest valid option.
4. Return that option's EXACT label.
5. Return the locator belonging to that exact option.
6. Verify that the returned label exists in the provided options.
7. Verify that the locator belongs to the same option.

EXPERIENCE QUESTIONS:

For experience questions, use only the explicitly provided experience.

If the provided experience is:

"3 years"

and the options are:

"No experience"
"1 year"
"2 years"
"3 years"
"4 years"
"5 years"
"More than 5 years"

return:

"3 years"

Do not use freelance, personal project, or combined experience unless the
question explicitly asks for total experience including those categories
and that information is provided.

SALARY QUESTIONS:

For salary questions, use the candidate's expected salary from the
additional context.

If the candidate's expectation is PHP90,000 and the available options are:

₱60K
₱70K
₱80K
₱100K
₱120K

choose the closest AVAILABLE option.

In this example:

₱100K

Do NOT create an option such as:

₱90K
₱90,000
PHP90,000

if it is not present in the available options.

For USD salary questions, convert the candidate's PHP expectation using the
provided exchange rate before comparing against the available options.

NOTICE PERIOD:

If asked how soon the candidate can start or how much notice is required,
use the explicitly provided notice period.

DATE:

- Return the date in the format expected by the field.
- Use only dates supported by the provided context.
- Never invent a date.

NUMBER:

- Return ONLY the requested numerical value.
- Do not include units.
- Do not include explanations.
- Do not include additional text.

UNKNOWN INFORMATION:

If the candidate's information is unavailable:

- Do not fabricate an answer.
- For SELECT fields, choose an option only when a reasonable answer can be
  determined from the available information.
- Otherwise return "Unknown".
- Never claim experience that is not explicitly supported.

FINAL SELECT VALIDATION:

Before producing the final output for EVERY SELECT field:

1. Extract ALL available option labels.
2. Determine the intended answer.
3. Check whether the intended answer EXACTLY equals one of the provided
   option labels.
4. If YES, return that exact label.
5. If NO, discard the intended answer.
6. Select the closest valid option from the provided options.
7. Return the locator belonging to that exact option.
8. Verify that the label and locator belong to the SAME option.
9. NEVER return a SELECT answer that is not present in the input.

STRUCTURED OUTPUT:

For every field:

- field: the original field_name exactly as provided.
- answer.label: the answer to submit.
- answer.locator: the locator corresponding to that exact answer.

For SELECT fields:

- answer.label MUST exactly match one of the provided option labels.
- answer.locator MUST be the locator belonging to that exact option.
- The label and locator MUST come from the same option.
- NEVER invent a locator.
- ONLY return a locator explicitly provided in the input.

FINAL RESPONSE:

Return ONLY the requested structured output.

Do not include:

- explanations
- reasoning
- commentary
- analysis
- markdown
- notes
- warnings
- descriptions of the candidate
- references to the resume
- references to the additional context

"""


class Answer(BaseModel):
    locator: str
    label: str


class EvaluatedField(BaseModel):
    field: str
    answer: Answer


class AgentOutput(BaseModel):
    fields: list[EvaluatedField]


form_evaluator = Agent(
    name="Form Evaluator Agent",
    instructions=INSTRUCTIONS,
    model=macbook_pro_qwen_3_5_9b_model,
    output_type=AgentOutput,
    model_settings=ModelSettings(
        include_usage=True,
        timeout=10_000,
    ),
)
async def test_model():

    result = await Runner.run(
        form_evaluator,
        """
[
    {
        'field_name': "What's your expected monthly basic salary?",
        'field_type': 'select',
        'locator': '#question-PH_Q_7791_V_1',
        'options': [
            {'label': '₱6K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7792']"},
            {'label': '₱8K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7793']"},
            {'label': '₱10K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7794']"},
            {'label': '₱12K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7795']"},
            {'label': '₱14K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7796']"},
            {'label': '₱15K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7797']"},
            {'label': '₱16K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7798']"},
            {'label': '₱18K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7799']"},
            {'label': '₱20K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7800']"},
            {'label': '₱25K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7801']"},
            {'label': '₱30K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7802']"},
            {'label': '₱35K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7803']"},
            {'label': '₱40K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7804']"},
            {'label': '₱45K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7805']"},
            {'label': '₱50K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7806']"},
            {'label': '₱55K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7807']"},
            {'label': '₱60K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7808']"},
            {'label': '₱70K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7809']"},
            {'label': '₱80K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7810']"},
            {'label': '₱100K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7811']"},
            {'label': '₱120K', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7812']"},
            {'label': '₱150K or more', 'locator': "#question-PH_Q_7791_V_1 option[value='PH_Q_7791_V_1_A_7813']"}
        ]
    },

    {
        'field_name': "How many years' experience do you have as a Laravel Developer?",
        'field_type': 'select',
        'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2',
        'options': [
            {'label': 'No experience', 'locator': "#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_1']"},
            {'label': 'Less than 1 year', 'locator': "#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_2']"},
            {'label': '1 year', 'locator': "#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_3']"},
            {'label': '2 years', 'locator': "#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_4']"},
            {'label': '3 years', 'locator': "#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_5']"},
            {'label': '4 years', 'locator': "#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_6']"},
            {'label': '5 years', 'locator': "#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_7']"},
            {'label': 'More than 5 years', 'locator': "#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_8']"}
        ]
    },

    {
        'field_name': 'Which of the following types of qualifications do you have?',
        'field_type': 'select',
        'locator': '#question-PH_Q_7834_V_1',
        'options': [
            {'label': 'High School Diploma', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7835']"},
            {'label': 'National Certificate 1', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7836']"},
            {'label': 'National Certificate 2', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7837']"},
            {'label': 'National Certificate 3', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7838']"},
            {'label': 'National Certificate 4', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7839']"},
            {'label': 'Diploma', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7840']"},
            {'label': 'Bachelor Degree', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7841']"},
            {'label': 'Post Graduate Diploma', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7842']"},
            {'label': 'Master Degree', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7843']"},
            {'label': 'Doctoral Degree', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7844']"},
            {'label': 'I have a qualification that is not listed here', 'locator': "#question-PH_Q_7834_V_1 option[value='PH_Q_7834_V_1_A_7845']"}
        ]
    },

    # ---------------------------------------------------------
    # YES / NO QUESTIONS
    # ---------------------------------------------------------

    {
        'field_name': 'Did you meet the minimum requirements listed for this role?',
        'field_type': 'select',
        'locator': '#minimum-requirements',
        'options': [
            {'label': 'Yes', 'locator': '#minimum-requirements option[value="yes"]'},
            {'label': 'No', 'locator': '#minimum-requirements option[value="no"]'}
        ]
    },

    {
        'field_name': 'Do you have hands-on experience with React, Next.js, or similar frontend frameworks?',
        'field_type': 'select',
        'locator': '#frontend-experience',
        'options': [
            {'label': 'Yes', 'locator': '#frontend-experience option[value="yes"]'},
            {'label': 'No', 'locator': '#frontend-experience option[value="no"]'}
        ]
    },

    {
        'field_name': 'Have you previously integrated CRM systems such as HubSpot or Microsoft 365 (Graph API, SharePoint, Outlook, Teams)?',
        'field_type': 'select',
        'locator': '#crm-experience',
        'options': [
            {'label': 'Yes', 'locator': '#crm-experience option[value="yes"]'},
            {'label': 'No', 'locator': '#crm-experience option[value="no"]'}
        ]
    },

    {
        'field_name': 'Do you have experience automating functional and non-functional tests?',
        'field_type': 'select',
        'locator': '#testing-experience',
        'options': [
            {'label': 'Yes', 'locator': '#testing-experience option[value="yes"]'},
            {'label': 'No', 'locator': '#testing-experience option[value="no"]'}
        ]
    },

    {
        'field_name': 'Are you able to work graveyard shifts?',
        'field_type': 'select',
        'locator': '#graveyard-shift',
        'options': [
            {'label': 'Yes', 'locator': '#graveyard-shift option[value="yes"]'},
            {'label': 'No', 'locator': '#graveyard-shift option[value="no"]'}
        ]
    },

    {
        'field_name': 'Are you willing to work on-site?',
        'field_type': 'select',
        'locator': '#onsite',
        'options': [
            {'label': 'Yes', 'locator': '#onsite option[value="yes"]'},
            {'label': 'No', 'locator': '#onsite option[value="no"]'}
        ]
    },

    # ---------------------------------------------------------
    # TEXT / TEXTAREA QUESTIONS
    # ---------------------------------------------------------

    {
        'field_name': 'Do you have experience working with AI coding tools (Claude Code, GitHub Copilot, Cursor) or integrating LLM APIs (Anthropic Claude, OpenAI)?',
        'field_type': 'text',
        'locator': '#ai-experience'
    },

    {
        'field_name': 'Please describe your experience with React and TypeScript.',
        'field_type': 'textarea',
        'locator': '#react-typescript'
    },

    {
        'field_name': 'Please describe your backend development experience.',
        'field_type': 'textarea',
        'locator': '#backend-experience'
    },

    {
        'field_name': 'What tools or applications are you familiar with in your daily work?',
        'field_type': 'textarea',
        'locator': '#daily-tools'
    },

    {
        'field_name': 'How soon can you start?',
        'field_type': 'text',
        'locator': '#start-date'
    },

    {
        'field_name': 'Where are you currently located? (City, Country)',
        'field_type': 'text',
        'locator': '#location'
    },

    # ---------------------------------------------------------
    # NUMBER QUESTIONS
    # ---------------------------------------------------------

    {
        'field_name': 'How many years of professional experience do you have in backend engineering?',
        'field_type': 'number',
        'locator': '#backend-years'
    },

    {
        'field_name': 'How many years of experience do you have with Python?',
        'field_type': 'number',
        'locator': '#python-years'
    },

    {
        'field_name': 'How many years of experience do you have with React?',
        'field_type': 'number',
        'locator': '#react-years'
    },

    # ---------------------------------------------------------
    # UNKNOWN / UNAVAILABLE INFORMATION
    # ---------------------------------------------------------

    {
        'field_name': 'Do you have professional experience with Microsoft Dynamics 365?',
        'field_type': 'select',
        'locator': '#dynamics',
        'options': [
            {'label': 'Yes', 'locator': '#dynamics option[value="yes"]'},
            {'label': 'No', 'locator': '#dynamics option[value="no"]'}
        ]
    },

    {
        'field_name': 'What is your experience with SAP ERP?',
        'field_type': 'text',
        'locator': '#sap-experience'
    }
]
        """,
    )

    resultoutput = result.final_output

    print("\n" + "=" * 80)
    print("FORM EVALUATOR RESULTS")
    print("=" * 80)

    for field in resultoutput.fields:
        print(f"\nQUESTION:")
        print(f"  {field.field}")

        print(f"ANSWER:")
        print(f"  Label:    {field.answer.label}")
        print(f"  Locator:  {field.answer.locator}")

    print("\n" + "=" * 80)
    print(f"TOTAL FIELDS: {len(resultoutput.fields)}")
    print("=" * 80)

    print("\nRAW STRUCTURED OUTPUT:")
    print(resultoutput.model_dump())


if __name__ == "__main__":
    asyncio.run(test_model())
