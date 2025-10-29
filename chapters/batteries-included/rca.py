import os
import logging
from typing import Literal
from prefect import flow, task, tags
import requests
from openai import OpenAI
from datetime import datetime, timedelta
from prefect.blocks.system import Secret


@flow(log_prints=True)
def retrieve_data_loki(query: str, start_timestamp: int, end_time: int) -> dict:
    """Retrieve data from Grafana Loki.
    Args:
        query (str): Loki query
        start_timestamp (int): Start timestamp
        end_time (int): End timestamp
    Returns:
        dict: Loki query result
    """
    response = requests.get(
        url=f"http://loki:3001/loki/api/v1/query_range",
        params={
            "query": query,
            "start": int(start_timestamp),
            "end": int(end_time),
            "limit": 1000,
        },
    )
    return response.json()["data"]["result"]


@flow(log_prints=True)
def generate_rca_prompt(loki_results, device_name, interface):
    return f"""
   Generate a Root Cause Analysis (RCA) for a potential BGP neighbor issue
   Available Data:
   - A BGP session may have changed in {device_name} from Established to another non-desired state
   - Associated Interface: {interface}
   - Associated Logs: {loki_results}
   Analysis Questions:
   - Based on the available data, what are the potential causes for the loss of BGP Established state?
   - What system interactions or external factors could have influenced this event?
   Actionable Insights:
   - Given the findings, what immediate actions should be taken to mitigate the current issue?
   - What additional data would be helpful to further investigate this issue?
   - Verify if someone made any recent configuration changes on {device_name} or related network devices.
   Please format your response as follows:
   - Limit your response to max 2000 characters
   - Suggest clear actions with a directive tone
   - Format your response for Slack message using bold (wrapping with only one '*') and code blocks where appropriate
   - Organize in sections with headings:
    - Potential Causes from Data Available
    - Immediate Actions to Mitigate the Issue
    - Additional Data for Further Investigation
   - Be concise and to the point with the most probable root cause, do not add too much fluff
   - Use bullet points for clarity
   - Add references to the device name, interface, IP addresses where applicable
   """


@flow(log_prints=True)
def ask_openai(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    """
    Ask OpenAI a question and return the response.
    Args:
        prompt (str): The prompt to send to OpenAI.
        model (str, optional): The model to use. Defaults to "gpt-3.5-turbo".
    Returns:
        str: The response from OpenAI.
    """
    client = OpenAI(api_key=Secret.load("openai-token").get())  # type: ignore
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )
    return response.choices[0].message.content


@flow(log_prints=True, flow_run_name="Root Cause Analysis | {device}:{interface}")
def generate_rca(device: str, interface: str) -> None:
    """
    Generate a Root Cause Analysis (RCA) report for a given device and interface.

    Args:
        device (str): The name or identifier of the network device.
        interface (str): The name or identifier of the network interface.
    """
    print(f"Generating RCA report for device: {device}, interface: {interface}")

    now = datetime.now()
    loki_logs = retrieve_data_loki(
        query=f'{{device="{device}"}}',
        start_timestamp=int(datetime.timestamp(now - timedelta(hours=0, minutes=5))),
        end_time=int(datetime.timestamp(now)),
    )
    prompt = generate_rca_prompt(loki_logs, device, interface)
    return ask_openai(prompt)  # type: ignore
