
import dotenv
import json
import requests

from openai import AzureOpenAI
import streamlit as st
from streamlit_chat import message

# Load environment variables
ENV = dotenv.dotenv_values(".env")
with st.sidebar.expander("Environment Variables"):
    st.write(ENV)

default_prompt = """
You an assistant to a clinical coder, it is your role to suggest potential codes based on the user input - it is not your job to actually code the input. Under no circumstances should you guess or give any sort of medical advice whether that relates to coding or anything else.

You should only reply with information from the ICD-11 API, but only when asked to code by the user. You should always provide a disclaimer at the bottom of any reply with potential clinical codes that they are just suggestions from the ICD-11 API and should be double checked by a medical professional.

Many medical entities will have multiple codes, so they should all be presented clearly in a list with the corresponding links to the ICD-11 API after. You should also share the medical term that you extracted from the input and used to search for the codes.
"""

system_prompt = st.sidebar.text_area("System Prompt", default_prompt, height=200)
seed_message = {"role": "system", "content": system_prompt}

# Initialise session state variables
if "generated" not in st.session_state:
    st.session_state["generated"] = []
if "past" not in st.session_state:
    st.session_state["past"] = []
if "messages" not in st.session_state:
    st.session_state["messages"] = [seed_message]
if "model_name" not in st.session_state:
    st.session_state["model_name"] = []

counter_placeholder = st.sidebar.empty()
clear_button = st.sidebar.button("Clear Conversation", key="clear")

if clear_button:
    st.session_state["generated"] = []
    st.session_state["past"] = []
    st.session_state["messages"] = [seed_message]
    st.session_state["number_tokens"] = []
    st.session_state["model_name"] = []

def generate_response(prompt):
    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_icd_11_api",
                "description": "Function to call the ICD-11 API and return suggestions for medical codes based on the user input. It returns a dictionary that contains the input word and the corresponding ICD-11 code and web link.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "string",
                            "description": "The input query from the user that needs to be sent to the ICD-11 API for coding.",
                        },
                        "unit": {"type": "string"},
                    },
                    "required": ["input"],
                },
            },
        }
    ]
    st.session_state["messages"].append({"role": "user", "content": prompt})
    try:
        client = AzureOpenAI(api_key = ENV["AZURE_OPENAI_KEY"], api_version="2024-02-01", azure_endpoint = ENV["AZURE_OPENAI_ENDPOINT"])
        completion = client.chat.completions.create(
            model=ENV["AZURE_OPENAI_DEPLOYMENT_NAME"],
            messages=st.session_state["messages"],
            tools=tools
        ) 
        response = completion.choices[0].message.content
        tool_calls = completion.choices[0].finish_reason
        if tool_calls == "tool_calls":
            available_functions = {
                "query_icd_11_api": query_icd_11_api,
            }
            st.session_state["messages"].append(completion.choices[0].message)
            function = completion.choices[0].message.tool_calls[0].function
            function_name = function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(function.arguments)
            response = function_to_call(
                input=function_args.get("input"),
            )
            st.session_state["messages"].append(
                {
                    "tool_call_id": completion.choices[0].message.tool_calls[0].id,
                    "role": "tool",
                    "name": function_name,
                    "content": response,
                }
            )
            second_response = client.chat.completions.create(
                model=ENV["AZURE_OPENAI_DEPLOYMENT_NAME"],
                messages=st.session_state["messages"]
            ).choices[0].message.content
            total_tokens = completion.usage.total_tokens
            prompt_tokens = completion.usage.prompt_tokens
            completion_tokens = completion.usage.completion_tokens
            return second_response, total_tokens, prompt_tokens, completion_tokens
    except Exception as e:
        response = f"The API could not handle this content: {str(e)}"
        total_tokens = None
        prompt_tokens = None
        completion_tokens = None
    total_tokens = completion.usage.total_tokens
    prompt_tokens = completion.usage.prompt_tokens
    completion_tokens = completion.usage.completion_tokens
    return response, total_tokens, prompt_tokens, completion_tokens

ICD_KEY = ENV['ICD_KEY']
ICD_CLIENT = ENV['ICD_CLIENT']
TOKEN_ENDPOINT = 'https://icdaccessmanagement.who.int/connect/token'
SCOPE = 'icdapi_access'
GRANT_TYPE = 'client_credentials'

def query_icd_11_api(input: str):
    """
    Function to call the ICD-11 API and return suggestions for medical codes based on the user input.
    """
    payload = {'client_id': ICD_CLIENT, 
	   	   'client_secret': ICD_KEY, 
           'scope': SCOPE, 
           'grant_type': GRANT_TYPE}
    r = requests.post(TOKEN_ENDPOINT, data=payload).json()
    token = r['access_token']
    code_mappings = {}
    for word in input.split():
        code_mappings[word] = {}
        word = word.replace(",", "")
        url = f"https://id.who.int/icd/release/11/2019-04/mms/search?q={word}"
        headers = {
            "Accept": "application/json",
            "Authorization":  f"Bearer {token}",
            'API-Version': 'v2',
            'Accept-Language': 'en'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            potential_codes = response.json()['destinationEntities']
            for code_ in potential_codes:
                code = code_.get('theCode')
                link = code_.get('id')
                code_mappings[word].update({code: link})
            return json.dumps(code_mappings)
        else:
            return None

st.title("LLM function calling example for the ICD-11 API (powered by GPT-4)")

# container for chat history
response_container = st.container()
# container for text box
container = st.container()

with container:
    with st.form(key="my_form", clear_on_submit=True):
        user_input = st.text_area("You:", key="input", height=100)
        submit_button = st.form_submit_button(label="Send")

    if submit_button and user_input:
        output, total_tokens, prompt_tokens, completion_tokens = generate_response(
            user_input
        )
        st.session_state["past"].append(user_input)
        st.session_state["generated"].append(output)
        st.session_state["model_name"].append(ENV["AZURE_OPENAI_DEPLOYMENT_NAME"])
        #import pdb; pdb.set_trace()

if st.session_state["generated"]:
    with response_container:
        for i in range(len(st.session_state["generated"])):
            message(
                st.session_state["past"][i],
                is_user=True,
                key=str(i) + "_user",
                avatar_style="shapes",
            )
            message(
                st.session_state["generated"][i], key=str(i), avatar_style="identicon"
            )