import openai
import anthropic
import time
import random
import os


def retry_with_exponential_backoff(
    func, initial_delay=1, exponential_base=2, jitter=True, max_retries=2
):
    """Retry a function with exponential backoff."""

    def wrapper(*args, **kwargs):
        # Initialize variables
        num_retries = 0
        delay = initial_delay

        # Loop until a successful response or max_retries is hit or an exception is raised
        while True:
            try:
                return func(*args, **kwargs)

            # Retry on specific errors
            except (openai.RateLimitError, anthropic.RateLimitError):
                # Increment retries
                num_retries += 1

                # Check if max retries has been reached
                if num_retries > max_retries:
                    raise Exception(
                        f"Maximum number of retries ({max_retries}) exceeded."
                    )

                # Increment the delay
                delay *= exponential_base * (1 + jitter * random.random())

                # Sleep for the delay
                time.sleep(delay)

            # Raise exceptions for any errors not specified
            except Exception as e:
                raise e

    return wrapper


class OpenAILLM:
    def __init__(self, model="gpt-3.5-turbo"):
        try:
            token = os.environ["OPENAI_API_KEY"]
        except KeyError:
            print("Please set the OPENAI_API_KEY environment variable")
            raise SystemExit(1)

        self.model = model
        self._client = openai.OpenAI(
            api_key=token,
            timeout=600,
            max_retries=0,
        )

    @retry_with_exponential_backoff
    def completion_with_backoff(
        self,
        *,
        model,
        messages,
        frequency_penalty,
        max_tokens,
        presence_penalty,
        stop,
        stream,
        temperature,
        top_p,
    ):
        time.sleep(0.05)
        return self._client.chat.completions.create(
            model=model,
            messages=messages,
            frequency_penalty=frequency_penalty,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            stop=stop,
            stream=stream,
            temperature=temperature,
            top_p=top_p,
            
        )


    def inference(
        self,
        prompt,
        max_tokens = 1024,
        temperature = 1.0,
        top_p = 0.95,
        stop = None,
        frequency_penalty = 0,
        presence_penalty = 0,
    ):
        comp = self.completion_with_backoff(
            model=self.model,
            messages=prompt,
            frequency_penalty=frequency_penalty,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            stop=stop,
            temperature=temperature,
            top_p=top_p,
            stream=False,
        )
    
        return {
            "role": comp.choices[0].message.role,
            "content": comp.choices[0].message.content,
        }
