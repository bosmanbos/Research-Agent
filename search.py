import requests
from bs4 import BeautifulSoup
import json
import yaml
from termcolor import colored
import os
import chardet
import string
import ast
from prompts import generate_searches_prompt, get_search_page_prompt, generate_searches_json, get_search_page_json

def load_config(file_path):
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
        for key, value in config.items():
            os.environ[key] = value


class WebSearcher:
    """
    Input:
    Search Engine Query: The primary input to the tool is a search engine query intended for Google Search. This query is generated based on a specified plan and user query.
    Output:
    Dictionary of Website Content: The output of the tool is a dictionary where:
    The key is the URL of the website that is deemed most relevant based on the search results.
    The value is the content scraped from that website, presented as plain text.
    The source is useful for citation purposes in the final response to the user query.
    The content is used to generate a comprehensive response to the user query.
    """
    def __init__(self, model, verbose=False, model_endpoint=None, server=None, stop=None):
        self.server = server
        self.model_endpoint = model_endpoint
        load_config('config.yaml')
        self.api_key = os.getenv('OPENAI_API_KEY')
        self.headers = {
            'Content-Type': 'application/json',
            "Authorization": f'Bearer {self.api_key}'
        }
        self.model = model
        self.verbose = verbose
        self.stop = stop
        
    
    def generate_searches(self, plan, query):
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": generate_searches_prompt
                },
                {
                    "role": "user",
                    "content": f"Query: {query}\n\nPlan: {plan}"
                }
            ],
            "temperature": 0
        }
        
        try: 
            response = requests.post(self.model_endpoint, headers=self.headers, data=json.dumps(payload))
            print(f"Response_DEBUG: {response}")
            try:
                response_dict = response.json()
            except json.JSONDecodeError:
                response_dict = ast.literal_eval(response.content)

            response_content = response_dict['choices'][0]['message']['content']

            try:
                response_json = json.loads(response_content)
            except json.JSONDecodeError:
                response_json = ast.literal_eval(response_content)

            search_query = response_json.get('response', '')
            
            print(f"Search Query: {search_query}")
            return search_query
        
        except Exception as e:
            print("Error in response:", response_dict)
            return "Error generating search query"
        
        
    def get_search_page(self, plan, query, search_results, failed_sites=[], visited_sites=[]):
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": get_search_page_prompt
                },
                {
                    "role": "user",
                    "content": f"Query: {query}\n\nPlan: {plan}\n\nSearch Results: {search_results}\n\nFailed Sites: {failed_sites}\n\nVisited Sites: {visited_sites}"
                }
            ],
            "temperature": 0
        }
        
        try: 
            response = requests.post(self.model_endpoint, headers=self.headers, data=json.dumps(payload))
            try:
                response_dict = response.json()
            except json.JSONDecodeError:
                response_dict = ast.literal_eval(response.content)

            response_content = response_dict['choices'][0]['message']['content']

            try:
                response_json = json.loads(response_content)
            except json.JSONDecodeError:
                response_json = ast.literal_eval(response_content)

            search_query = response_json.get('response', '')
        
            return search_query
    
        except Exception as e:
            print("Error in response:", response_dict)
            return "Error getting search page URL"
            
        
        
        
        
    def format_results(self, organic_results):
        result_strings = []
        for result in organic_results:
            title = result.get('title', 'No Title')
            link = result.get('link', '#')
            snippet = result.get('snippet', 'No snippet available.')
            result_strings.append(f"Title: {title}\n\nLink: {link}\n\nSnippet: {snippet}\n---")
            
        return '\n'.join(result_strings)
    
    
    def fetch_search_results(self, search_queries):
        search_url = "https://google.serper.dev/search"
        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': os.environ['SERPER_API_KEY']
        }
        payload = json.dumps({"q": search_queries})
        
        try: 
            response = requests.post(search_url, headers=headers, data=payload)
            response.raise_for_status()
            results = response.json()
            
            if 'organic' in results:
                return self.format_results(results['organic'])
            else:
                return "No organic results found"
            
        except requests.exceptions.HTTPError as http_err:
            return f"HTTP error occurred: {http_err}"
        except requests.exceptions.RequestException as req_err:
            return f"Request exception occurred: {req_err}"
        except KeyError as key_err:
            return f"Key error in handling response: {key_err}"   
        
        
    def scrape_website_content(self, website_url, failed_sites=[]):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Accept-Encoding': 'gzip, deflate, br'
        }
        
        def is_garbled(text):
            non_ascii_chars = sum(1 for char in text if char not in string.printable)
            try:
                return non_ascii_chars / len(text) > 0.2
            except ZeroDivisionError:
                return False
            

        try:
            response = requests.get(website_url, headers=headers, timeout=20)
            response.raise_for_status()
            
            detected_encoding = chardet.detect(response.content)
            response.encoding = detected_encoding['encoding'] if detected_encoding['confidence'] > 0.5 else 'utf-8'
            
            try:
                content = response.text
            except UnicodeDecodeError:
                content = response.content.decode('utf-8', errors='replace')
                
            soup = BeautifulSoup(content, 'html.parser')
            text = soup.get_text(separator='\n')
            clean_text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])
            split_text = clean_text.split()
            first_5k_words = split_text[:4000]
            clean_text_5k = ' '.join(first_5k_words)
            
            if is_garbled(clean_text):
                print(f"Failed to retrieve content from {website_url} due to garbled text.")
                failed = {"source": website_url, "content": "Failed to retrieve content due to garbled text"}
                failed_sites.append(website_url)
                return failed, failed_sites, False
            
            return {"source": website_url, "content": clean_text_5k}, "N/A", True
        
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving content from {website_url}: {e}")
            failed = {"source": website_url, "content": f"Failed to retrieve content due to an error: {e}"}
            failed_sites.append(website_url)
            return failed, failed_sites, False
        
        
    def use_tool(self, plan=None, query=None, visited_sites=[], failed_sites=[]):
        search_queries = self.generate_searches(plan, query)
        search_results = self.fetch_search_results(search_queries)
        best_page = self.get_search_page(plan, query, search_results, visited_sites=visited_sites)  
        results_dict, failed_sites, response = self.scrape_website_content(best_page, failed_sites=failed_sites)
        
        attempts = 0
        
        while not response and attempts < 5:
            print(f"Failed to retrieve content from {best_page}...Trying a different page")
            print(f"Failed Sites: {failed_sites}")
            best_page = self.get_search_page(plan, query, search_results, failed_sites=failed_sites)
            results_dict, failed_sites, response = self.scrape_website_content(best_page)
            
            attempts += 1
            
        if self.verbose:
            print(f"Search Engine Query: {search_queries}")
            print(colored(f"SEARCH RESULTS {search_results}", 'yellow'))
            print(f"BEST PAGE {best_page}")
            print(f"Scraping URL: {best_page}")
            print(colored(f"RESULTS DICT {results_dict}", 'yellow'))
            
        return results_dict
   
    
if __name__ == '__main__':
    search = WebSearcher(model='gpt-4o', model_endpoint='https://api.openai.com/v1/chat/completions', server='openai')
    search.use_tool()
