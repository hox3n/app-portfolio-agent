import csv
import io

from models import QueryResult, AgentState
from langchain_core.messages import HumanMessage, AIMessage


def clean_sql(sql_query: str) -> str:
    """Remove code block markers from SQL query."""
    return sql_query.replace("```sql", "").replace("```", "").strip()


def format_history(state: AgentState) -> str:
    """Format conversation history for inclusion in prompts (optimized for speed)."""
    messages = state.get("messages", [])
    if not messages or len(messages) < 3:
        return "No prior conversation."

    # Only include last 2-3 exchanges to keep context minimal
    recent_messages = messages[-4:] if len(messages) > 4 else messages
    history = []
    for i in range(0, len(recent_messages) - 1, 2):
        if i + 1 < len(recent_messages):
            user_msg = recent_messages[i]
            ai_msg = recent_messages[i + 1]
            if isinstance(user_msg, HumanMessage) and isinstance(ai_msg, AIMessage):
                # Keep context brief
                history.append(f"Q: {user_msg.content[:100]}")
                history.append(f"A: {ai_msg.content[:150]}")

    return "\n".join(history[-4:]) if history else "No prior conversation."  # Max 4 lines


def format_query_data(query_result: QueryResult, is_follow_up: bool) -> str:
    """Format query result data for display, optimized for Slack readability."""
    data = query_result["data"]
    row_count = query_result["row_count"]

    if len(data) == 1 and len(data[0]) == 1:
        value = list(data[0].values())[0]
        column_name = list(data[0].keys())[0]

        if isinstance(value, (int, float)):
            formatted_value = f"{value:,}" if isinstance(value, int) else f"{value:,.2f}"
        else:
            formatted_value = str(value)

        if "count" in column_name.lower():
            return f"**{formatted_value}** {column_name.replace('_', ' ').title()}"
        else:
            return f"**Result**: {formatted_value}"

    if len(data) == 0:
        return "No data found matching your query."

    # Handle multiple results
    prefix = "Following up, here's what I found" if is_follow_up else "Here are your results"
    response = f"{prefix} ({row_count} {'result' if row_count == 1 else 'results'}):\n\n"
    columns = query_result["column_names"]

    if len(data) <= 3 and len(columns) <= 4:
        for i, row in enumerate(data, 1):
            response += f"**{i}.** "
            row_parts = []

            for col in columns:
                value = row.get(col, "")
                col_display = col.replace('_', ' ').title()

                if isinstance(value, (int, float)):
                    if col.lower() in ['revenue', 'cost', 'in_app_revenue', 'ads_revenue', 'ua_cost']:
                        formatted_value = f"${value:,.2f}" if isinstance(value, float) else f"${value:,}"
                    elif col.lower() in ['installs']:
                        formatted_value = f"{value:,}"
                    else:
                        formatted_value = f"{value:,}" if isinstance(value, int) else f"{value:.2f}"

                else:
                    formatted_value = str(value)

                row_parts.append(f"{col_display}: {formatted_value}")

            response += " | ".join(row_parts) + "\n"

        if row_count > len(data):
            response += f"\nShowing first {len(data)} results. Use 'export as csv' to get all {row_count} records.*"

    else:
        # For larger datasets, a more compact format with code blocks is used
        response += "```\n"
        header_parts = []
        for col in columns:
            col_display = col.replace('_', ' ').title()
            if len(col_display) > 15:
                col_display = col_display[:12] + "..."
            header_parts.append(f"{col_display:<15}")
        response += " | ".join(header_parts) + "\n"
        response += "-" * (len(" | ".join(header_parts))) + "\n"

        # output of rows is limited to 8 rows for readability
        display_count = min(8, len(data))
        for row in data[:display_count]:
            row_parts = []

            for col in columns:
                value = row.get(col, "")

                if isinstance(value, (int, float)):
                    if col.lower() in ['revenue', 'cost', 'in_app_revenue', 'ads_revenue', 'ua_cost']:
                        formatted_value = f"${value:,.0f}" if value > 1000 else f"${value:.2f}"
                    elif col.lower() in ['installs'] and value > 1000:
                        formatted_value = f"{value / 1000:.1f}K" if value < 1000000 else f"{value / 1000000:.1f}M"
                    else:
                        formatted_value = f"{value:,}" if isinstance(value, int) else f"{value:.2f}"

                else:
                    formatted_value = str(value)

                if len(formatted_value) > 15:
                    formatted_value = formatted_value[:12] + "..."

                row_parts.append(f"{formatted_value:<15}")

            response += " | ".join(row_parts) + "\n"

        response += "```\n"
        if row_count > display_count:
            response += f"\nShowing {display_count} of {row_count} results. Ask me to 'export as csv' to get the complete dataset.*"

    return response


def create_csv_content(query_result: QueryResult) -> str:
    """Creates CSV content as a string."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=query_result["column_names"])
    writer.writeheader()
    writer.writerows(query_result["data"])
    return output.getvalue()