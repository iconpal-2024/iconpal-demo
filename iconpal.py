import argparse
import json


from policy_validator import is_valid_policy, is_valid_snippet
from openai_llm import OpenAILLM


SYSTEM_CONTEXT_TEXT_TO_POLICY = "\nYou are a plain text to formal policy translator. I will teach you how to translate a plain text to formal policy with a tutorial and some examples.\n"
SYSTEM_CONTEXT_POLICY_TO_TEXT = "\nYou are a formal policy to plain text translator. I will teach you how to translate a formal policy to plain text with a tutorial and some examples.\n"
USER_QUERY_TEXT_TO_POLICY = "\nTranslate the following natural text to formal policy. Only provide the translated formal policy itself without any explanations or extra words.\n"
USER_QUERY_POLICY_TO_TEXT = "\nTranslate the following formal policy to plain text. Only provide the translation itself in plain text without any explanations or extra words.\n"
USER_QUERY_EQUIVALENCE = "\nAre the following two policies equivalent? Consider only action and condition. Answer Yes or No\n\n"


def extract_policy(policy):
    policy_components = policy.split("\n")
    valid_components = []
    for policy_component in policy_components:
        if is_valid_snippet(policy_component):
            valid_components.append(policy_component)

    extracted_policy = "\n".join(valid_components)
    is_valid, _ = is_valid_policy(extracted_policy)
    if is_valid:
        return is_valid, extracted_policy
    return False, policy


class PolicyTranslator:
    def __init__(
        self, *, context, model="gpt-3.5-turbo", temperature=1.0, dry_run=True
    ):
        self.dry_run = dry_run
        self.temperature = temperature
        self.llm = OpenAILLM(model=model)

        learning_prompt = SYSTEM_CONTEXT_TEXT_TO_POLICY
        learning_prompt += "Tutorial:\n" + str(context["tutorial"]) + "\n\n"
        learning_prompt += "Example Translations:\n"
        for example in context["examples"]:
            learning_prompt += "Text:\n" + example["text"] + "\n"
            learning_prompt += "Policy:\n" + example["policy"] + "\n\n"
        else:
            learning_prompt += "No examples provided\n\n"
        self.learning_prompt = learning_prompt

    def translate_text_to_policy(
        self, text, old_translation=None, retry_instruction=None
    ):
        messages = [
            {"role": "system", "content": self.learning_prompt},
            {"role": "user", "content": USER_QUERY_TEXT_TO_POLICY + '"' + text + '"\n'},
        ]
        if old_translation:
            messages.append({"role": "assistant", "content": old_translation})
            messages.append({"role": "user", "content": retry_instruction})
        output = ""
        if not self.dry_run:
            result = self.llm.inference(
                messages,
                temperature=self.temperature,
            )
            if result:
                output = result["content"]

        _, output = extract_policy(output)
        return output


class SemanticValidator:
    def __init__(self, context, model="gpt-3.5-turbo", temperature=1.0, dry_run=False):
        self.temperature = temperature
        self.dry_run = dry_run
        learning_prompt = SYSTEM_CONTEXT_POLICY_TO_TEXT
        learning_prompt += "Tutorial: \n" + str(context["tutorial"]) + "\n\n"
        learning_prompt += "Examples:\n"
        if context["examples"]:
            for example in context["examples"]:
                learning_prompt += "Policy:\n" + example["policy"] + "\n\n"
                learning_prompt += "Text:\n" + example["text"] + "\n"

        else:
            learning_prompt += "No examples provided\n\n"
        self.learning_prompt = learning_prompt

        self.llm = OpenAILLM(model=model)

    def translate_policy_to_text(self, policy):
        prompt = USER_QUERY_POLICY_TO_TEXT + '"' + policy + '"\n'
        output = ""
        if not self.dry_run:
            result = self.llm.inference(
                [
                    {"role": "system", "content": self.learning_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
            )
            if result:
                output = result["content"]
        return output

    def is_semantically_valid(self, actual_policy_text, generated_policy_text):
        prompt = USER_QUERY_EQUIVALENCE
        prompt += "1: " + actual_policy_text + "\n"
        prompt += "2: " + generated_policy_text + "\n"

        output = "No"
        if not self.dry_run:
            response = self.llm.inference(
                [{"role": "user", "content": prompt}], temperature=self.temperature
            )
            output = response["content"]

        return output.strip(" .").lower() in ["yes", "true", "correct"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Translate natural policy text to formal policy")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument(
        "-m",
        "--model",
        default="gpt-3.5-turbo",
        choices=["gpt-3.5-turbo", "gpt-4-turbo"],
        help="Model to use",
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Debug mode")

    args = parser.parse_args()

    if args.dry_run and args.debug:
        print("[DEBUG] Dry run mode")

    with open("knowledge-base/examples.json", "r") as f:
        examples = json.load(f)

    with open("knowledge-base/tutorial.md", "r") as f:
        tutorial = f.read()

    with open("inputs.json", "r") as f:
        inputs = json.load(f)

    for input in inputs:
        print("\nText: " + input["text"])
        context = {
            "tutorial": tutorial,
            "examples": [
                example
                for example in examples
                if example["category"] == input["category"]
            ],
        }
        translator = PolicyTranslator(
            context=context, model=args.model, temperature=0.5, dry_run=args.dry_run
        )
        translated_policy = translator.translate_text_to_policy(input["text"])
        syntactically_valid, reason = is_valid_policy(translated_policy)
        retry_count = 1
        while not syntactically_valid and retry_count <= 3:
            if args.debug:
                print("[DEBUG] Failed Translation:\n" + translated_policy)
                print("[DEBUG] Reason:\n" + reason)
            retry_count += 1
            retry_instruction = (
                "Your translation is invalid due to following reason.\n"
                + "Reason:\n"
                + reason
                + "\nPlease try again."
            )
            translated_policy = translator.translate_text_to_policy(
                input["text"], translated_policy, retry_instruction
            )
            syntactically_valid, reason = is_valid_policy(translated_policy)
        if syntactically_valid:
            print("\nTranslated Policy:\n-----------------\n" + translated_policy)
            semantic_validator = SemanticValidator(
                context, model=args.model, temperature=0.7, dry_run=args.dry_run
            )
            translated_text = semantic_validator.translate_policy_to_text(
                translated_policy
            )
            semantically_valid = semantic_validator.is_semantically_valid(
                input["text"], translated_text
            )
            print("\nSemantically valid: " + str(semantically_valid))
        else:
            print("Tranlation failed")
            print("Reason: " + reason)
