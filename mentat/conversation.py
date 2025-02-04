import openai
from termcolor import cprint

from .code_change import CodeChange
from .code_file_manager import CodeFileManager
from .config_manager import ConfigManager
from .llm_api import CostTracker, choose_model, count_tokens
from .parsing import run_async_stream_and_parse_llm_response
from .prompts import system_prompt


class Conversation:
    def __init__(self, config: ConfigManager, cost_tracker: CostTracker):
        self.messages = []
        self.add_system_message(system_prompt)
        self.allow_32k = config.allow_32k()
        self.cost_tracker = cost_tracker

        if self.allow_32k:
            # check if user actually has access to gpt-4-32k
            available_models = [x["id"] for x in openai.Model.list()["data"]]
            if "gpt-4-32k-0314" not in available_models:
                cprint(
                    (
                        "You set ALLOW_32K to true, but your openAI API key doesn't"
                        " have access to gpt-4-32k-0314. To remove this warning, set"
                        " ALLOW_32K to false until you have access."
                    ),
                    "yellow",
                )
                self.allow_32k = False

    def add_system_message(self, message: str):
        self.messages.append({"role": "system", "content": message})

    def add_user_message(self, message: str):
        self.messages.append({"role": "user", "content": message})

    def add_assistant_message(self, message: str):
        self.messages.append({"role": "assistant", "content": message})

    def get_model_response(
        self, code_file_manager: CodeFileManager, config: ConfigManager
    ) -> (str, list[CodeChange]):
        messages = self.messages.copy()

        code_message = code_file_manager.get_code_message()
        messages.append({"role": "system", "content": code_message})

        model, num_prompt_tokens = choose_model(messages, self.allow_32k)

        state = run_async_stream_and_parse_llm_response(
            messages, model, code_file_manager
        )

        self.cost_tracker.display_api_call_stats(
            num_prompt_tokens,
            count_tokens(state.message),
            model,
            state.time_elapsed,
        )

        self.add_assistant_message(state.message)
        return state.explanation, state.code_changes
