import re
import time
import os

from .utils import FunctionSpec, OutputType, opt_messages_to_list, backoff_create
from funcy import notnone, once, select_values
import anthropic


ANTHROPIC_TIMEOUT_EXCEPTIONS = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
    anthropic.APIStatusError,
)

def get_ai_client(model : str, max_retries=2):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        client = anthropic.Anthropic(api_key=api_key, max_retries=max_retries)
    else:
        # Fallback to Bedrock only if AWS credentials are available
        aws_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("AWS_PROFILE")
        if aws_key:
            client = anthropic.AnthropicBedrock(max_retries=max_retries)
        else:
            raise RuntimeError(
                "No Anthropic credentials found. Set ANTHROPIC_API_KEY for direct API access, "
                "or AWS_ACCESS_KEY_ID/AWS_PROFILE for Bedrock access."
            )
    return client

def _normalize_model(model: str) -> str:
    """Strip Bedrock model ID prefixes to get standard Claude model name."""
    # anthropic.claude-3-5-sonnet-20241022-v2:0 → claude-3-5-sonnet-20241022
    if model.startswith("anthropic."):
        model = model[len("anthropic."):]
    # Remove version suffix like -v2:0
    if ":0" in model:
        model = model.split(":0")[0]
    if model.endswith("-v2"):
        model = model[:-3]
    if model.endswith("-v1"):
        model = model[:-3]
    return model

def query(
    system_message: str | None,
    user_message: str | None,
    func_spec: FunctionSpec | None = None,
    **model_kwargs,
) -> tuple[OutputType, float, int, int, dict]:
    client = get_ai_client(model_kwargs.get("model"), max_retries=0)

    filtered_kwargs: dict = select_values(notnone, model_kwargs)  # type: ignore
    if "max_tokens" not in filtered_kwargs:
        filtered_kwargs["max_tokens"] = 8192  # default for Claude models

    # Normalize model name (strip Bedrock prefixes if using direct API)
    if "model" in filtered_kwargs and isinstance(client, anthropic.Anthropic):
        filtered_kwargs["model"] = _normalize_model(filtered_kwargs["model"])

    if func_spec is not None:
        raise NotImplementedError(
            "Anthropic does not support function calling for now."
        )

    # Anthropic doesn't allow not having a user messages
    # if we only have system msg -> use it as user msg
    if system_message is not None and user_message is None:
        system_message, user_message = user_message, system_message

    # Anthropic passes the system messages as a separate argument
    if system_message is not None:
        filtered_kwargs["system"] = system_message

    messages = opt_messages_to_list(None, user_message)

    t0 = time.time()
    message = backoff_create(
        client.messages.create,
        ANTHROPIC_TIMEOUT_EXCEPTIONS,
        messages=messages,
        **filtered_kwargs,
    )
    req_time = time.time() - t0
    print(filtered_kwargs)

    if "thinking" in filtered_kwargs:
        assert (
            len(message.content) == 2
            and message.content[0].type == "thinking"
            and message.content[1].type == "text"
        )
        output: str = message.content[1].text
    else:
        assert len(message.content) == 1 and message.content[0].type == "text"
        output: str = message.content[0].text

    # Strip <think> tags if present
    if output and '<think>' in output:
        output = re.sub(r'<think>[\s\S]*?</think>', '', output).strip()

    in_tokens = message.usage.input_tokens
    out_tokens = message.usage.output_tokens

    info = {
        "stop_reason": message.stop_reason,
    }

    return output, req_time, in_tokens, out_tokens, info
