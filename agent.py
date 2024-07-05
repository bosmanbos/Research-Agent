import os 
import yaml
import json
import requests
from datetime import datetime, timezone, timedelta
from termcolor import colored
from prompts import planning_agent_prompt, integration_agent_prompt, check_response_prompt, check_response_json
from search import WebSearcher
import ast


def load_config(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
        for key, value in config.items():
            os.environ[key] = value
            

def get_current_cet_datetime():
    cet_offset = timedelta(hours=1)
    now_utc = datetime.now(timezone.utc)
    now_cet = now_utc + cet_offset
    current_time_cet = now_cet.strftime("%Y-%m-%d %H:%M:%S %Z")
    return current_time_cet


def save_feedback(response, json_filename="memory.json"):
    feedback_entry = {"feedback": response}
    if os.path.exists(json_filename):
        with open(json_filename, 'r') as json_file:
            data = json.load(json_file)
    else:
        data = []
    data.append(feedback_entry)
    with open(json_filename, 'w') as json_file:
        json.dump(data, json_file, indent=4) 
        
        
def read_feedback(json_filename="memory.json"):
    if os.path.exists(json_filename):
        with open(json_filename, 'r') as json_file:
            data = json.load(json_file)
            json_string = json.dumps(data, indent=4)
            return json_string
    else:
        return ""
        
           
def clear_json_file(json_filename="memory.json"):
    with open(json_filename, 'w') as json_file:
        json.dump([], json_file)
        

def initialize_json_file(json_filename="memory.json"):
    if not os.path.exists(json_filename) or os.path.getsize(json_filename) == 0:
        with open(json_filename, 'w') as json_file:
            json.dump([], json_file)
            

initialize_json_file()


class Agent:
    def __init__(self, model, model_tool, model_qa, tool, temperature=0, max_tokens=10000, planning_agent_prompt=None, integration_agent_prompt=None, check_response_prompt=None, verbose=False, iterations=10, model_endpoint=None, server=None, stop=None):
        self.server = server
        self.model_endpoint = model_endpoint
        load_config('config.yaml')
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tool_specs = tool.__doc__
        self.planning_agent_prompt = planning_agent_prompt
        self.integration_agent_prompt = integration_agent_prompt
        self.model = model
        self.tool = tool(model=model_tool, verbose=verbose, model_endpoint=model_endpoint, server=server, stop=stop)
        self.iterations = iterations
        self.model_qa = model_qa
        self.stop = stop
        
        
    def run_planning_agent(self, query, plan=None, feedback=None):
        system_prompt = self.planning_agent_prompt.format(
            plan=plan,
            feedback=feedback,
            tool_specs=self.tool_specs,
            datetime=get_current_cet_datetime()
        )    
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "stream": False,
            "temperature": 0,
            "stop": self.stop
        }
        del payload["stop"]
        try:
            response = requests.post(self.model_endpoint, headers=self.headers, data=json.dumps(payload))
            print("Response_DEBUG:", response)
            try: 
                response_dict = response.json()
            except json.JSONDecodeError as e:
                response_dict = ast.literal_eval(response)
            response = response_dict['choices'][0]['message']['content']
            print(colored(f"Planning Agent: {response}", 'green'))
            return response
        except Exception as e:
            print("Error in response:", response_dict)
            return f"Error generating plan {e}"
        
        
    def run_integration_agent(self, query, plan, outputs, reason, previous_response):
        system_prompt = self.integration_agent_prompt.format(
            outputs=outputs,
            plan=plan,
            reason=reason,
            sources=outputs.get('sources', ''),
            previous_response=previous_response,
            datetime=get_current_cet_datetime(),
            query=query
        )
        
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "stream": False,
            "temperature": 0,
            "stop": self.stop
        }
        del payload['stop']
        try:
            response = requests.post(self.model_endpoint, headers=self.headers, data=json.dumps(payload))
            print("Response_DEBUG:", response)
            try: 
                response_dict = response.json()
            except json.JSONDecodeError as e:
                response_dict = ast.literal_eval(response)
            response = response_dict['choices'][0]['message']['content']
            print(colored(f"Planning Agent: {response}", 'cyan'))
            return response
        except Exception as e:
            print("Error in response:", response_dict)
            return f"Error generating plan {e}"
        
        
    def check_responses(self, response, query, previous_response, datetime=get_current_cet_datetime()):
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": check_response_prompt
                },
                {
                    "role": "user",
                    "content": f"query: {query} \n\nresponse: {response} \n\nprevious response: {previous_response} \n\ncurrent datetime: {datetime}"
                }
            ],
            "temperature": 0,
            "stop": self.stop,
            "guided_json": check_response_json
        }
        del payload["stop"]
        del payload["guided_json"]
        try: 
            response = requests.post(self.model_endpoint, headers=self.headers, data=json.dumps(payload))  
            try:
                response_dict = response.json()
            except json.JSONDecodeError as e:
                response_dict = ast.literal_eval(response)
            print(f"check_response response_dict type: {type(response_dict)}")
            response_content = response_dict['choices'][0]['message']['content']
            try:
                decision_dict = json.loads(response_content)
            except json.JSONDecodeError as e:
                decision_dict = ast.literal_eval(response_content)
            print("Response Quality Assessment:", decision_dict)
            return decision_dict
        except Exception as e:
            print("Error in assessing response quality:", response_dict)
            return "Error in assessing response quality"
                            
                
    def execute(self):
        query = input(colored(f"Enter your quere: ", "magenta"))
        meets_requirements = False
        plan=None
        outputs=None
        integration_agent_response = None
        reason=None
        iterations=0
        visited_sites = []
        failed_sites = []
        while not meets_requirements and iterations < self.iterations:
            iterations += 1
            feedback = read_feedback(json_filename="memory.json")
            plan = self.run_planning_agent(query, plan=plan, feedback=feedback)
            outputs = self.tool.use_tool(plan=plan, query=query, visited_sites=visited_sites, failed_sites=failed_sites)
            visited_sites.append(outputs.get('source', ''))
            print("VISITED_SITES", visited_sites)
            integration_agent_response = self.run_integration_agent(query=query, plan=plan, outputs=outputs, reason=reason, previous_response=feedback)
            save_feedback(integration_agent_response, json_filename="memory.json")
            response_dict = self.check_responses(response=integration_agent_response, query=query, previous_response=feedback)
            meets_requirements = response_dict.get('pass', '')
            print(f"Response meets requirements: {meets_requirements}")
            if meets_requirements == "True":
                meets_requirements = True
            else:
                meets_requirements = False
                reason = response_dict.get('reason', '')
        clear_json_file()
        print(colored(f"Final Response: {integration_agent_response}", "cyan"))
        
        
if __name__ == "__main__":
    model = 'gpt-4o'
    model_tool = 'gpt-4o'
    model_qa = 'gpt-4o'
    model_endpoint = 'https://api.openai.com/v1/chat/completions'
    stop = None
    server = 'openai'             
                
                
    agent = Agent(
        model = model,
        model_tool=model_tool,
        model_qa=model_qa,
        tool = WebSearcher,
        planning_agent_prompt=planning_agent_prompt,
        integration_agent_prompt=integration_agent_prompt,
        verbose=False,
        iterations=10,
        model_endpoint=model_endpoint,
        server=server
    )
    

    agent.execute()
