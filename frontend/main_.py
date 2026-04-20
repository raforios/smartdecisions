'''    
    This is the main entry point for the AIgent application. It initializes the agent 
    and starts a loop to interact with the user via the command line. 
    The user can input messages, and the agent will generate responses based on those messages. 
    The loop continues until the user decides to exit by typing 'exit', 'quit', or 'bye'.
'''

from core.agent import AIgent


if __name__ == '__main__':
    agent = AIgent()

    while True:
        user_input = input('You: ').strip()

        if not user_input:
            continue

        if user_input.lower() in ('exit', 'quit', 'bye'):
            print('Exiting the AIgent. Goodbye!')
            break

        while True:
            response = agent.generate_response(user_input)

            called_tool = agent.process_response(response)

            if not called_tool:
                break
