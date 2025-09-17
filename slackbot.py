import os
import time

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from agent import AppPortfolioAgent
from utils import create_csv_content

load_dotenv()

if __name__ == "__main__":
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
    LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "app-portfolio-agent")
    db_path = "chatbot_env/apps.db"  # Adjust if needed

    agent = AppPortfolioAgent(
        db_path=db_path,
        langsmith_api_key=LANGSMITH_API_KEY,
        langsmith_project=LANGSMITH_PROJECT
    )

    app = App(token=os.getenv("SLACK_BOT_TOKEN"))


    @app.event("app_mention")
    @app.event("message")
    def handle_message(event, say, client):
        if "subtype" in event and event["subtype"] != "bot_message":
            return

        # Skips messages from bots to avoid loops
        if event.get("bot_id"):
            return

        channel_id = event["channel"]
        user_id = event.get("user")
        print(f"Debug: Received message in channel {channel_id} from user {user_id}")

        message_text = event["text"].strip()
        try:
            bot_user_id = client.auth_test()["user_id"]
        except Exception as e:
            print(f"Error getting bot user ID: {e}")
            return

        is_dm = channel_id.startswith("D")
        is_mentioned = f"<@{bot_user_id}>" in message_text
        if not is_dm and not is_mentioned:
            return

        question = message_text.replace(f"<@{bot_user_id}>", "").strip()
        if not question:
            say("Hi! Ask me anything about the app portfolio analytics.", thread_ts=event.get("ts"))
            return

        session_key = f"{channel_id}_{user_id}" if not is_dm else channel_id
        state = agent.states.get(session_key, None)

        try:
            response, new_state = agent.run(question, state)
            agent.states[session_key] = new_state
            say(text=response, thread_ts=event.get("ts"), mrkdwn=True)

            # Handle CSV export if intent is export and data exists
            if (new_state.get("intent") == "export" and new_state.get("query_result", {}).get("data")):
                query_result = new_state["query_result"]
                filename = f"export_{int(time.time())}.csv"
                try:
                    csv_content = create_csv_content(query_result)
                    csv_bytes = csv_content.encode('utf-8')
                    print(f"Debug: Uploading CSV to channel {channel_id}, size: {len(csv_bytes)} bytes")

                    upload_response = client.files_upload_v2(
                        channel=channel_id,
                        content=csv_bytes,
                        filename=filename,
                        title="Exported Data",
                        initial_comment="Here's your CSV export:",
                        thread_ts=event.get("ts")
                    )
                    print(f"Debug: Upload response: {upload_response}")

                    if upload_response.get("ok"):
                        say("CSV file uploaded successfully!", thread_ts=event.get("ts"))
                    else:
                        error_detail = upload_response.get("error", "Unknown error")
                        raise Exception(f"Upload failed: {error_detail}")

                except Exception as upload_error:
                    error_msg = f"Error uploading CSV: {str(upload_error)}"
                    print(f"Debug Error: {error_msg}")
                    row_count = len(query_result.get("data", []))
                    col_count = len(query_result.get("column_names", []))
                    fallback_msg = f"{error_msg}\n\n *Data Summary*: {row_count} rows, {col_count} columns"
                    say(fallback_msg, thread_ts=event.get("ts"))

        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            print(f"Debug: Agent error: {error_msg}")
            say(error_msg, thread_ts=event.get("ts"))


    @app.event("app_home_opened")
    def update_home_tab(client, event):
        try:
            client.views_publish(
                user_id=event["user"],
                view={
                    "type": "home",
                    "callback_id": "home_view",
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Welcome to the App Portfolio Analytics Bot!* \n\nI can help you analyze app data with natural language queries."
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Example queries:*\n• How many apps do we have?\n• Which country generates the most revenue?\n• Show me iOS apps sorted by installs\n• Export this data as CSV"
                            }
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*Usage:*\n• Send me a DM\n• Mention me in a channel with `@PortfolioBot`\n• Ask follow-up questions for context-aware responses"
                            }
                        }
                    ]
                }
            )
        except Exception as e:
            print(f"Error publishing home tab: {e}")


    handler = SocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    print("Starting App Portfolio Bot...")
    print("Bot is ready to receive messages!")
    handler.start()