import os
import logging
from typing import Literal
from prefect import flow, task, tags
import requests
from openai import OpenAI
from datetime import datetime, timedelta


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
    print("Retrieving data from Loki...")

    response = requests.get(
        url=f"http://loki:3001/loki/api/v1/query_range",
        params={
            "query": query,
            "start": int(start_timestamp),
            "end": int(end_time),
            "limit": 1000,
        },
    )
    print("Data retrieved from Loki")
    return response.json()["data"]["result"]


@flow(log_prints=True)
def generate_rca_prompt(loki_results, device_name, interface):
    return f"""
   RCA for a BGP neighbor issue
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
   Please limit your response to max 2000 characters and use as much data as possible from the available data presented above (devices, interfaces, BGP information, but focusing on the logs) to add more clarification.
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
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    print(response)
    return response.choices[0].message.content


@flow(log_prints=True)
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
        # Look back for 10 minutes
        start_timestamp=int(datetime.timestamp(now - timedelta(hours=0, minutes=10))),
        end_time=int(datetime.timestamp(now)),
    )
    print(f"Loki logs: {loki_logs}")

    prompt = generate_rca_prompt(loki_logs, device, interface)

    rca_response = ask_openai(prompt)

    print(f"RCA Analysis: {rca_response}")
