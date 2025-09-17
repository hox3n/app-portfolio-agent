# App Portfolio Analytics Bot

This is a modularized Slack bot that uses an AI agent to query and analyze app portfolio data stored in a DuckDB database. It supports natural language queries, SQL generation via Ollama, conversation history, data export to CSV, and observability via LangSmith.

## Structure
- `models.py`: Defines data models (TypedDicts) for query results and agent state.
- `utils.py`: Contains utility functions for formatting responses, history, SQL cleaning, and CSV creation.
- `agent.py`: The core `AppPortfolioAgent` class that handles query processing, SQL generation/execution, and workflow via LangGraph.
- `slackbot.py`: Sets up the Slack bot integration, handles events/messages, and runs the agent.
- `database.py`: Manages the DuckDB database, including schema creation and sample data generation.

## Requirements
To install the required dependencies, run:
```bash
pip install -r requirements.txt
```

The `requirements.txt` file includes:
- `duckdb`: For database operations
- `langchain-core`: Core LangChain functionality
- `langchain-ollama`: Ollama integration for LangChain
- `langgraph`: For building the agent workflow
- `langsmith`: For observability and tracing
- `python-dotenv`: For environment variable management
- `slack-bolt`: For Slack bot integration
- `typing_extensions`: For advanced type hints
- `faker`: For generating sample data in `database.py`


## Slack app setup
1. Create a Slack App:

- Go to https://api.slack.com/apps and click "Create New App".
- Choose "From scratch" and give your app a name (e.g., "PortfolioBot") and select your workspace.
- In the app's "Basic Information" page, add an app icon and description if desired.

2. Configure OAuth & Permissions (Bot Token Scopes):

- Navigate to "OAuth & Permissions" in the left sidebar.
- Under "Scopes" > "Bot Token Scopes", add the following scopes (as shown in the provided screenshot):

  - app_mentions:read: 
  - chat:write: 
  - files:write: 
  - im:read:  
  - im:write:
  - users:read: 
  
- Scroll up to "OAuth Tokens for Your Workspace" and click "Install to Workspace" (or "Request to Install" if in an organization). This will generate your SLACK_BOT_TOKEN (starts with xoxb-).

3. Enable Socket Mode and Get App Token:

- Navigate to "Basic Information" > "App Credentials".

- Go to "Socket Mode" in the left sidebar and toggle it on.
  - This generates the SLACK_APP_TOKEN (starts with xapp-).

4. Subscribe to Events:
- Navigate to "Event Subscriptions" in the left sidebar
- Toggle "Enable Events" on.
- Under "Subscribe to bot events", add the following events (as defined in the code):

  - app_mention
  - message.im 
  - app_home_opened
  
## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Set up environment variables in a `.env` file:
   - `SLACK_BOT_TOKEN`: Your Slack bot token
   - `SLACK_APP_TOKEN`: Your Slack app token for Socket Mode
   - `LANGSMITH_API_KEY`: (Optional) For LangSmith tracing
   - `LANGSMITH_PROJECT`: (Optional) LangSmith project name (default: "app-portfolio-agent")
3. Set up the database:
   - Run `python database.py` to create and populate the database with sample data (default: `chatbot_env/apps.db`)
   - Adjust the `db_path` in `slackbot.py` and `database.py` if needed
4. Run the bot: `python slackbot.py`




## Usage
- DM the bot or mention it in a channel (e.g., `@PortfolioBot How many apps do we have?`)
- Supports follow-up questions, data exports, SQL viewing, etc.
- View the App Home for examples and tips.

## Notes
- Requires Ollama running locally (default: http://localhost:11434) with models `duckdb-nsql` and `llama3:8b`
- Caching is enabled by default for repeated SQL queries
- Error handling and logging are integrated for debugging
- The database is set up with a sample schema and data for testing purposes