Python Code: DIAL API Key Usage Example
from openai import AzureOpenAI

client = AzureOpenAI(
  api_key = "",  # Put your DIAL API Key here  api_version = "2025-04-01-preview",
  azure_endpoint = "https://ai-proxy.lab.epam.com")
 deployment_name = "gpt-5.6-terra-2026-07-09"# Please only use this one if you absolutely need it. It's more expensive.
# deployment_name = "anthropic.claude-sonnet-5"
# deployment_name = "gemini-3.6-flash"
# Use a GET request to the https://ai-proxy.lab.epam.com/openai/models endpoint to get the full list of currently available models.
# You can also retrieve embeddings, but small private models may perform better and be cheaper.
# https://huggingface.co/spaces/mteb/leaderboard
#
# Example usage for embeddings:
# embedding_model = "text-embedding-3-small-1"
# print(client.embeddings.create(
#     model=embedding_model,
#     input="Your text here"
# ))print(client.chat.completions.create(
  model=deployment_name,
  temperature=0,
  messages=[
      {
        "role": "user",
        "content": "how are you?",
      },
  ],
))
Python Code: View Available Models and Limits for the DIAL API Key
import jsonimport requestsfrom concurrent.futures import ThreadPoolExecutor

api_key = ""  # Put your DIAL API Key here
all_models = requests.get("https://ai-proxy.lab.epam.com/openai/models", headers={"Api-Key": api_key}).json()["data"]
def get_model_limits(model):
    try:
        limits = requests.get(f"https://ai-proxy.lab.epam.com/v1/deployments/{model['id']}/limits", headers={"Api-Key": api_key}).json()
        minute_limit = limits.get("minuteTokenStats", {}).get("total", 0)
        day_limit = limits.get("dayTokenStats", {}).get("total", 0)
        if minute_limit > 0 or day_limit > 0:
            return {model['id']: {"limits": {"minute": minute_limit, "day": day_limit}}}
    except:
        pass
limits_per_available_model = {}with ThreadPoolExecutor(max_workers=128) as executor:
    for model_limits in executor.map(get_model_limits, all_models):
        if model_limits:  # Only include models with nonzero limits (available to you)            limits_per_available_model.update(model_limits)
print(json.dumps(limits_per_available_model, indent=4))
 

 variables to use : 
 AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_ENDPOINT=https://ai-proxy.lab.epam.com
AZURE_OPENAI_API_VERSION=2025-04-01-preview
DEPLOYMENT_NAME=gpt-5-mini-2025-08-07


 