import os
import logging
from typing import Literal

import requests
from openai import OpenAI


log = logging.getLogger("machine-learning")


def retrieve_data_loki(query: str, start_timestamp: int, end_time: int) -> dict:
    """Retrieve data from Grafana Loki.
    Args:
        query (str): Loki query
        start_timestamp (int): Start timestamp
        end_time (int): End timestamp
    Returns:
        dict: Loki query result
    """
    log.info("Retrieving data from Loki...")

    # Send the data to Loki
    response = requests.get(
        url=f"http://loki:3001/loki/api/v1/query_range",
        params={
            "query": query,
            "start": int(start_timestamp),
            "end": int(end_time),
            "limit": 1000,
        },
    )
    log.info("Data retrieved from Loki")
    return response.json()["data"]["result"]

def generate_rca_prompt(loki_results, device_name, neighbor_id, neighbor_asn):
    return f"""
    RCA for a BGP neighbor issues:
    Available Data:
    - A BGP session in {device_name} has changed from Established to another non desired state
    - BGP neighbor IP: {neighbor_id}
    - BGP neighbor ASN: {neighbor_asn}
    - Associated Logs: {loki_results}
    Analysis Questions:
    1. Based on the available data, what are the potential causes the lost of BGP Established state?
    2. Did the traffic shift succeeded by looking at the traffic on the secondary site before and after?, and if not why might the automated workflow not have executed as expected?
    3. What system interactions or external factors could have influenced this event?
    Actionable Insights:
    - Given the findings, what immediate actions should be taken to mitigate the current issue?
    - What additional data would be helpful to further investigate this issue?
    Please limit your response to max 2000 characters and use as much data as possble from the available data presented above (devices, interfaces, BGP information, but focusing on the logs) to add more clarification.
    """


def ask_openai(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    """
    Ask OpenAI a question and return the response.
    Args:
        prompt (str): The prompt to send to OpenAI.
        model (str, optional): The model to use. Defaults to "gpt-3.5-turbo".
    Returns:
        str: The response from OpenAI.
    """
    # Construct the prompt for OpenAI
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

    log.info(response)
    return response.choices[0].message.content
