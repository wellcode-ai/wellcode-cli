import json
import logging
import re

from anthropic import Anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from ..config import get_anthropic_api_key
from .models.metrics import MetricsJSONEncoder

client = Anthropic(
    # This is the default and can be omitted
    api_key=get_anthropic_api_key(),
)
console = Console()


def format_ai_response(response):
    # Try to extract content inside <analysis> tags, but proceed even if not found
    analysis_match = re.search(r"<analysis>(.*?)</analysis>", response, re.DOTALL)
    analysis_content = analysis_match.group(1) if analysis_match else response

    # Split the content into sections, either by XML-like tags or by line breaks
    sections = re.findall(r"<(\w+)>(.*?)</\1>", analysis_content, re.DOTALL)
    if not sections:
        sections = [
            ("general", para.strip())
            for para in analysis_content.split("\n")
            if para.strip()
        ]

    for section, content in sections:
        # Convert section name to title case and replace underscores with spaces
        section_title = section.replace("_", " ").title()

        # Format content as markdown for better rendering
        formatted_content = content.strip()

        # Create a panel for each section
        console.print(
            Panel(
                Markdown(formatted_content),
                title=f"[bold yellow]{section_title}[/]",
                border_style="blue",
                padding=(1, 2),
            )
        )

    # Extract and display efficiency score and justification
    efficiency_score_match = re.search(
        r"<efficiency_score>(.*?)</efficiency_score>", response, re.DOTALL
    )
    efficiency_justification_match = re.search(
        r"<efficiency_score_justification>(.*?)</efficiency_score_justification>",
        response,
        re.DOTALL,
    )

    if efficiency_score_match:
        score = efficiency_score_match.group(1).strip()
        justification = ""
        if efficiency_justification_match:
            justification = efficiency_justification_match.group(1).strip()

        console.print(
            Panel(
                f"[bold white]{score}/10[/]\n\n{justification}",
                title="[bold magenta]Efficiency Score & Justification[/]",
                border_style="magenta",
                padding=(1, 2),
            )
        )
    else:
        # Try to find a line that looks like an efficiency score
        score_line = re.search(
            r"efficiency.*?score.*?(\d+(/|\s*out of\s*)10)", response, re.IGNORECASE
        )
        justification_line = re.search(
            r"justification:?\s*(.*)", response, re.IGNORECASE
        )

        if score_line or justification_line:
            content = []
            if score_line:
                content.append(f"[bold white]{score_line.group(1)}[/]")
            if justification_line:
                content.append(f"\n{justification_line.group(1)}")

            console.print(
                Panel(
                    "\n".join(content),
                    title="[bold magenta]Efficiency Score & Justification[/]",
                    border_style="magenta",
                    padding=(1, 2),
                )
            )


def get_ai_analysis(all_metrics):
    """Generate AI analysis from all metrics sources."""
    metrics_summary = {}
    try:
        # GitHub metrics
        if "github" in all_metrics:
            github_data = all_metrics["github"]
            metrics_json = json.dumps(
                github_data, cls=MetricsJSONEncoder, indent=2, default=str
            )
            metrics_summary = {"github": json.loads(metrics_json)}

        # Linear metrics
        if "linear" in all_metrics:
            metrics_summary["linear"] = all_metrics["linear"]

        # Split metrics
        if "split" in all_metrics:
            metrics_summary["split"] = all_metrics["split"]

        if not metrics_summary:
            return "No metrics data available for analysis."

        # Create the prompt with the metrics
        prompt = f"""
You are a software development team analyst tasked with analyzing team metrics to provide insights on efficiency and areas for improvement. Your analysis should be data-driven, objective, and provide valuable insights for improving the team's performance.

Here are the detailed metrics for analysis:

{metrics_summary}

Based on these metrics, please provide:

<analysis>
<overall_efficiency>
A comprehensive assessment of the team's overall development efficiency
</overall_efficiency>

<strengths>
Key areas where the team excels, with specific metrics as evidence
</strengths>

<areas_for_improvement>
Critical areas needing attention, supported by metric data
</areas_for_improvement>

<recommendations>
Specific, actionable recommendations prioritized by potential impact
</recommendations>
</analysis>

<efficiency_score_justification>
A data-driven justification for the efficiency score
</efficiency_score_justification>

<efficiency_score>
A score from 1-10 based on industry standards
</efficiency_score>
"""

        message = client.messages.create(
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
            model="claude-3-5-sonnet-20240620",
        )

        return message.content[0].text if message.content else ""

    except Exception as e:
        logging.error(f"Unexpected error in get_ai_analysis: {str(e)}")
        logging.error("Error type:", type(e).__name__)
        import traceback

        logging.error("Traceback:", traceback.format_exc())
        return ""
