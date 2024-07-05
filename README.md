# AI-Powered Web Research Agent

## Overview
This project implements an AI-powered web research agent that can autonomously search the internet, gather information, and provide comprehensive answers to user queries. The system utilizes a combination of planning and integration agents, along with a web searching tool, to iteratively refine and improve its responses.

## Key Components
1. **Agent**: The main orchestrator that manages the overall process.
2. **WebSearcher**: A tool for performing web searches and scraping content.
3. **Planning Agent**: Generates search strategies based on user queries.
4. **Integration Agent**: Compiles and refines responses based on gathered information.

## Features
* Iterative search and response refinement
* Quality assurance checks on generated responses
* Configurable model selection (e.g., GPT-4)
* Web content scraping with error handling
* Memory management for tracking previous responses

## Setup
1. Clone the repository
2. Install the required dependencies (see `requirements.txt`)
3. Set up your configuration in `config.yaml` (API keys, etc.)
4. Run `agent.py` to start the system

## Usage
Run the `agent.py` script and input your query when prompted. The system will then:
1. Generate a search plan
2. Perform web searches
3. Compile and refine responses
4. Iterate until a satisfactory answer is produced

## Configuration
Adjust the following parameters in `agent.py` as needed:
* `model`: The main language model to use (e.g., 'gpt-4')
* `model_tool`: The model for the WebSearcher tool
* `model_qa`: The model for quality assurance checks
* `iterations`: Maximum number of refinement iterations

## Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## License
MIT license
