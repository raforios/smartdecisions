'''    
    AIgent module to interact with OpenAI API using a structured configuration.
    This module defines the AIgent class, which utilizes the OpenAI API to generate
    responses based on user input. The configuration is managed through a TypedDict
    for better type checking and clarity.
'''

import json
import os
from typing import TypedDict

from openai import OpenAI
from .environment import load_and_validate_env_vars

ENV_VARS = load_and_validate_env_vars(
    {
        'OPENAI_KEY': str,
    }
)

class AgentConfig(TypedDict):
    '''
        TypedDict to define the expected structure and types of database parameters.
        Ensures better type checking and clarity for AIgent configuration.
    '''
    OPEN_KEY: str

DB_PARAMETERS: AgentConfig = {
    'OPEN_KEY': ENV_VARS['OPENAI_KEY']
}


class AIgent:
    '''
        AIgent class to interact with OpenAI API using the provided configuration.
    '''
    def __init__(self, ):
        self.config = DB_PARAMETERS
        self.client = OpenAI(api_key = self.config['OPEN_KEY'])
        self.messages = [
            {'role': 'system', 'content': 'You are a helpful assistant.'}
        ]
        self.setup_tools()
        
    def setup_tools(self):
        self.tools = [
            {
                'type': 'function',
                'name': 'list_files_in_directory',
                'description': 'List all files in the current directory.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'directory': {
                            'type': 'string',
                            'description': 'The directory to list files in.'
                        }
                    },
                    'required': []
                    }
            },
            {
                'type': 'function',
                'name': 'read_file',
                'description': 'Read the contents of a file.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'file_path': {
                            'type': 'string',
                            'description': 'The path to the file to read.'
                        }
                    },
                    'required': ['file_path']
                }
            },
            {
                'type': 'function',
                'name': 'edit_file',
                'description': 'Edit an existing file by overwriting it with new content. Creates the file if it does not exist.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'file_path': {
                            'type': 'string',
                            'description': 'The path to the file to edit.'
                        },
                        'old_content': {
                            'type': 'string',
                            'description': 'The old content to be replaced in the file.'
                        },
                        'new_content': {
                            'type': 'string',
                            'description': 'The new content to write to the file.'
                        }
                    },
                    'required': ['file_path', 'new_content']
                }
            }
        ]

    def generate_response(self, prompt: str) -> str:
        '''
            Method to generate a response from the OpenAI API based on the provided prompt.
        '''
        self.messages.append({'role': 'user', 'content': prompt})
        response = self.client.responses.create(
            model = 'gpt-5-nano',
            tools = self.tools,
            input = self.messages
        )
        return response
    
    def read_file(self, file_path: str = '.') -> str:
        '''
            Utility function to read the contents of a file. 
            This can be used for various purposes, such as loading prompts or configurations.
        '''
        print(f'⚙️  Reading file: {file_path}')
        try:
            with open(file_path, encoding = 'utf-8') as file:
                content = file.read()
            return content
        except FileNotFoundError:
            print(f'File "{file_path}" not found.')
            return ''

    def edit_file(self, file_path: str = '.', old_content: str = '', new_content: str = '') -> None:
        '''
            Utility function to edit an existing file by overwriting it with new content.
            This can be used for various purposes, such as updating prompts or configurations.
        '''
        print(f'⚙️  Editing file: {file_path}')
        try:
            if os.path.exists(file_path) and old_content:
                content = self.read_file(file_path)
                if old_content not in content:
                    return f'Old content not found in file "{file_path}". No changes made.'
                
                content = content.replace(old_content, new_content)

            else:
                dir_name = os.path.dirname(file_path)
                if dir_name and not os.path.exists(dir_name):
                    os.makedirs(dir_name, exist_ok = True)
                content = new_content

            with open(file_path, 'w', encoding = 'utf-8') as file:
                file.write(content)

            action = 'Edited' if os.path.exists(file_path) else 'Created'
            print(f'{action} file "{file_path}" successfully.')
        except PermissionError:
            print(f'Permission denied when trying to edit file "{file_path}".')
        except FileNotFoundError:
            print(f'File "{file_path}" not found. Creating new file.')
            self.write_file(file_path, new_content)
        except Exception as e:
            print(f'Error editing file "{file_path}": {e}')

    def list_files_in_directory(self, directory: str = '.') -> list[str]:
        '''
            Utility function to list all files in a given directory.
            This can be used for various purposes, such as loading prompts or configurations.
        '''
        print('⚙️  Listing files in directory')
        try:
            files = os.listdir(directory)
            return {
                'files': files
            }
        except FileNotFoundError:
            print(f'Directory "{directory}" not found.')
            return {
                'files': []
            }

    def process_response(self, response):
        '''
            Method to process the response from the OpenAI API, handling both messages and function calls.
        '''

        self.messages += response.output

        for output in response.output:
            if output.type == 'function_call':
                function_name = output.name
                function_args = json.loads(output.arguments)
                
                print(f' - Function:  {function_name}')
                print(f' - Arguments: {function_args}')

                if function_name == 'list_files_in_directory':
                    result = self.list_files_in_directory(**function_args)

                elif function_name == 'read_file':
                    result = self.read_file(**function_args)

                elif function_name == 'edit_file':
                    result = self.edit_file(**function_args)

                self.messages.append({
                    'type': 'function_call_output',
                    'call_id': output.call_id,
                    'output': json.dumps({
                        'files': result
                    })
                })

                print('------------------')
                return True

            if output.type == 'message':
                reply = '\n'.join(part.text for part in output.content) 
                print(f'Agent: {reply}')
                print('------------------')
        
        return False
