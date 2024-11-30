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
    # Extract metrics section first
    metrics_match = re.search(
        r"<metrics_extraction>(.*?)</metrics_extraction>", response, re.DOTALL
    )
    if metrics_match:
        metrics_content = metrics_match.group(1).strip()
        console.print(
            Panel(
                Markdown(metrics_content),
                title="[bold yellow]Metrics Extraction[/]",
                border_style="blue",
                padding=(1, 2),
            )
        )

    # Extract performance evaluation sections
    performance_sections = {
        "overall_efficiency": "Overall Efficiency",
        "strengths": "Strengths",
        "areas_for_improvement": "Areas for Improvement",
        "recommendations": "Recommendations",
    }

    for section_tag, section_title in performance_sections.items():
        section_match = re.search(
            f"<{section_tag}>(.*?)</{section_tag}>", response, re.DOTALL
        )
        if section_match:
            content = section_match.group(1).strip()
            console.print(
                Panel(
                    Markdown(content),
                    title=f"[bold yellow]{section_title}[/]",
                    border_style="blue",
                    padding=(1, 2),
                )
            )

    # Handle efficiency score and justification separately
    efficiency_score_match = re.search(
        r"<efficiency_score>(.*?)</efficiency_score>", response, re.DOTALL
    )
    efficiency_justification_match = re.search(
        r"<efficiency_score_justification>(.*?)</efficiency_score_justification>",
        response,
        re.DOTALL,
    )

    if efficiency_score_match or efficiency_justification_match:
        content = []
        if efficiency_score_match:
            content.append(
                f"[bold white]{efficiency_score_match.group(1).strip()}/10[/]"
            )
        if efficiency_justification_match:
            content.append(f"\n\n{efficiency_justification_match.group(1).strip()}")

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
You are an experienced software development team analyst tasked with evaluating team performance based on provided metrics. Your goal is to offer data-driven, objective insights to improve the team's efficiency and overall performance.

Here's the metrics summary you'll be analyzing:

<metrics_summary>
{metrics_summary}
</metrics_summary>

Before providing a comprehensive analysis, extract and categorize the key metrics from the summary. Wrap this step in <metrics_extraction> tags:

- List all DORA Metrics (Deployment Frequency, Lead Time for Changes, Time to Restore Service, Change Failure Rate) with their values
- List metrics related to agility in development processes
- List metrics related to feedback loop cycle times
- List metrics related to Pull Request (PR) sizes
- List metrics related to speed of first code review
- List metrics related to number of code reviewers
- List metrics related to ease of code review conversations

After extracting the metrics, provide a comprehensive analysis of the team's performance based on these metrics. Your analysis should consider the following key factors of developer efficiency:
- DORA Metrics (Deployment Frequency, Lead Time for Changes, Time to Restore Service, Change Failure Rate)
- Agility in development processes
- Feedback loop cycle times
- Pull Request (PR) sizes (ideally between 0 and 500 lines)
- Speed of first code review (aim for less than 2 hours)
- Number of code reviewers (ideally 2 people)
- Ease of code review conversations

Structure your analysis as follows:

<performance_evaluation>
<overall_efficiency>
Assess the team's overall development efficiency, considering all aspects of the provided metrics and how they interact to impact performance. Pay special attention to the DORA Metrics and other efficiency factors mentioned above.
</overall_efficiency>

<strengths>
Identify 2-3 key areas where the team excels. Support each strength with specific metrics from the summary as evidence. Consider how these strengths align with the efficiency factors mentioned earlier.
</strengths>

<areas_for_improvement>
Highlight 2-3 critical areas needing attention. Each area should be supported by relevant metric data from the summary. Focus on aspects that could significantly impact the team's efficiency according to the factors mentioned above.
</areas_for_improvement>

<recommendations>
Provide 3-5 specific, actionable recommendations prioritized by potential impact. Each recommendation should directly address an area for improvement or leverage a team strength. Ensure these recommendations align with improving DORA Metrics, agility, feedback loops, and code review practices.
</recommendations>
</performance_evaluation>

After completing the analysis, provide a justification for an efficiency score based on the data:

<efficiency_score_justification>
Synthesize the key points from your analysis, weighing both strengths and areas for improvement. Consider how the team's performance compares to industry standards or benchmarks, particularly in relation to DORA Metrics and other efficiency factors mentioned earlier. Provide a data-driven justification for the efficiency score you will assign.
</efficiency_score_justification>

Finally, assign an efficiency score:

<efficiency_score>
Based on your analysis and justification, assign a score from 1-10, where 1 represents extremely poor efficiency and 10 represents outstanding efficiency according to industry standards and the efficiency factors discussed.
</efficiency_score>

Remember to base all your assessments, recommendations, and scoring strictly on the information provided in the metrics summary. Do not introduce external information or assumptions not supported by the given data.

Example output structure (do not copy the content, only the structure):

<metrics_extraction>
[Extracted and categorized metrics]
</metrics_extraction>

<performance_evaluation>
<overall_efficiency>
[Assessment of overall efficiency]
</overall_efficiency>

<strengths>
1. [First strength with supporting metrics]
2. [Second strength with supporting metrics]
3. [Third strength with supporting metrics (if applicable)]
</strengths>

<areas_for_improvement>
1. [First area for improvement with supporting metrics]
2. [Second area for improvement with supporting metrics]
3. [Third area for improvement with supporting metrics (if applicable)]
</areas_for_improvement>

<recommendations>
1. [First recommendation]
2. [Second recommendation]
3. [Third recommendation]
4. [Fourth recommendation (if applicable)]
5. [Fifth recommendation (if applicable)]
</recommendations>
</performance_evaluation>

<efficiency_score_justification>
[Justification for the efficiency score]
</efficiency_score_justification>

<efficiency_score>
[Numeric score between 1 and 10]
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
