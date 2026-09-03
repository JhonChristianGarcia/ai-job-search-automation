from agents import Agent, ModelSettings, Runner, OpenAIChatCompletionsModel
import asyncio
from agents.extensions.models.litellm_model import LitellmModel
from pydantic import BaseModel, Field
from context.context import resume
GPT_MODEL = "gpt-4o"

local_qwen_coder_model = LitellmModel(
    model="lm_studio/qwen/qwen2.5-coder-3b-instruct",
    api_key="lm-studio",
    base_url="http://127.0.0.1:1234/v1"
)
additional_context = f"""
    Portfolio link: https://www.jhonchristiangarcia.dev/
    Linkedin profile: https://www.linkedin.com/in/jhonchristiangarcia/
    Mobile number: +63 910 785 7097
    
    Expected monthly salary: PHP85,000 - PHP 95,000 [If the field is a select field, choose the closest option to this range or if it is a USD field convert it to USD using PHP60 = USD1]
    Willing to work remotely: Yes
    Willing to work full on-site: No
    Willing to work hybrid: Yes

    Total years of experience: 3+ years (5+ years including freelance/personal projects)
        Full-stack engineering: 3 years
        Backend engineering: 3 years
        Frontend engineering: 3 years
        Database engineering: 3 years
        AI/ML engineering: 1 year
        Python: 2 years
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

OUTPUT FORMAT:
- Return a dictionary where:
  - The key is the original field_name.
  - The value is the selected answer.
- For SELECT fields, the value MUST exactly match one of the provided option labels.
- NEVER create, modify, or invent an option.
- If the candidate's ideal answer is not available, choose the closest available option.

Resume:
{resume}

Additional Context:
{additional_context}

GENERAL RULES:

- Answer as the candidate.
- Use only information supported by the resume or additional context.
- Never invent information.
- Keep answers concise and suitable for direct form submission.
- Do not provide explanations or reasoning in the answer.
- Do not use AI-style formatting such as em dashes, bullet points, or
  unnecessary elaboration.

OUTPUT FORMAT:

Return the evaluated fields using the required structured output.

For every field:
- field: the original field_name exactly as provided.
- answer.label: the answer to submit.
- answer.locator: the locator corresponding to that exact answer.

For SELECT fields:
- answer.label MUST exactly match one of the provided option labels.
- answer.locator MUST be the locator belonging to that exact option.
- The label and locator MUST come from the same option.
- NEVER invent, modify, or generate a new option.
- NEVER generate a locator.
- ONLY return a locator that was explicitly provided in the input.
- Do not return an option label, index, or object instead of the provided locator.

For example, if the candidate expects:

PHP80,000 - PHP95,000

and the available options are:

₱60K
₱70K
₱80K
₱100K
₱120K

You MUST return either:

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

because those values are not available options.

For numeric SELECT fields:

1. Determine the candidate's actual value or range.
2. Inspect the complete list of available options.
3. Find the closest valid option.
4. Return that option's EXACT `label`.
5. Verify that the returned answer exists in the provided options.

For experience questions, use the candidate's actual experience from the
provided context.

For salary questions, use the candidate's expected salary from the
provided context. If the candidate has a salary range, choose the closest
AVAILABLE option to that range. Do not create an option that does not
exist.

For USD salary questions, convert the candidate's PHP expectation using
the provided exchange rate before comparing against the available
options.

TEXT / TEXTAREA / INPUT:

- Return a concise natural-language answer.
- Answer directly as the candidate.
- Do not add unnecessary explanations.
- Do not invent information.

BOOLEAN / YES-NO:

- Answer according to the candidate's information.
- If explicit options are provided, return the exact option label.

DATE:

- Return the date in the format expected by the field.
- Never invent a date.

NUMBER:

- Return only the requested numerical value.

UNKNOWN INFORMATION:

If the candidate's information is unavailable:

- Do not fabricate an answer.
- For SELECT fields, choose an option only when a reasonable answer can
  be determined.
- Otherwise return "Unknown".

FINAL SELECT VALIDATION:

Before producing the final output for every SELECT field:

1. Extract all available option labels.
2. Check whether the proposed answer exactly equals one of those labels.
3. If YES, return it.
4. If NO, discard the proposed answer and select a valid option.
5. NEVER return a SELECT answer that is not present in the options.

The `field` must contain the original field question.

Return only the requested structured output.
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
    model=local_qwen_coder_model,
    output_type=AgentOutput,
    model_settings=ModelSettings(
            include_usage=True,
            timeout=10_000,
    )
)

async def test_model():
    result = await Runner.run(form_evaluator, """
[{'field_name': "What's your expected monthly basic salary?",
  'field_type': 'select',
  'locator': '#question-PH_Q_7791_V_1',
  'options': [{'label': '₱6K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7792']"},
              {'label': '₱8K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7793']"},
              {'label': '₱10K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7794']"},
              {'label': '₱12K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7795']"},
              {'label': '₱14K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7796']"},
              {'label': '₱15K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7797']"},
              {'label': '₱16K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7798']"},
              {'label': '₱18K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7799']"},
              {'label': '₱20K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7800']"},
              {'label': '₱25K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7801']"},
              {'label': '₱30K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7802']"},
              {'label': '₱35K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7803']"},
              {'label': '₱40K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7804']"},
              {'label': '₱45K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7805']"},
              {'label': '₱50K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7806']"},
              {'label': '₱55K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7807']"},
              {'label': '₱60K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7808']"},
              {'label': '₱70K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7809']"},
              {'label': '₱80K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7810']"},
              {'label': '₱100K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7811']"},
              {'label': '₱120K',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7812']"},
              {'label': '₱150K or more',
               'locator': '#question-PH_Q_7791_V_1 '
                          "option[value='PH_Q_7791_V_1_A_7813']"}]},
 {'field_name': "How many years' experience do you have as a Laravel "
                'Developer?',
  'field_type': 'select',
  'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2',
  'options': [{'label': 'No experience',
               'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 '
                          "option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_1']"},
              {'label': 'Less than 1 year',
               'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 '
                          "option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_2']"},
              {'label': '1 year',
               'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 '
                          "option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_3']"},
              {'label': '2 years',
               'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 '
                          "option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_4']"},
              {'label': '3 years',
               'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 '
                          "option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_5']"},
              {'label': '4 years',
               'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 '
                          "option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_6']"},
              {'label': '5 years',
               'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 '
                          "option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_7']"},
              {'label': 'More than 5 years',
               'locator': '#question-PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2 '
                          "option[value='PH_Q_5900B4925F26ED6B5F8B1590C44A99E1_V_2_A_5900B4925F26ED6B5F8B1590C44A99E1_8']"}]},
 {'field_name': 'Which of the following types of qualifications do you have?',
  'field_type': 'select',
  'locator': '#question-PH_Q_7834_V_1',
  'options': [{'label': 'High School Diploma',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7835']"},
              {'label': 'National Certificate 1',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7836']"},
              {'label': 'National Certificate 2',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7837']"},
              {'label': 'National Certificate 3',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7838']"},
              {'label': 'National Certificate 4',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7839']"},
              {'label': 'Diploma',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7840']"},
              {'label': 'Bachelor Degree',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7841']"},
              {'label': 'Post Graduate Diploma',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7842']"},
              {'label': 'Master Degree',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7843']"},
              {'label': 'Doctoral Degree',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7844']"},
              {'label': 'I have a qualification that is not listed here',
               'locator': '#question-PH_Q_7834_V_1 '
                          "option[value='PH_Q_7834_V_1_A_7845']"}]}]
                              """)
    resultoutput = result.final_output
    print(resultoutput.model_dump())

if __name__ == "__main__":
    asyncio.run(test_model())